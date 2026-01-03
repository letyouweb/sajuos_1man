"""
report_worker.py
Background worker that generates premium report sections.

Router contract:
  reports.py imports `report_worker` singleton and calls
  `await report_worker.run_job(job_id, rulestore)`.

Features:
  - _ensure_dict(): Supabase JSON fields can arrive as strings
  - Physical forbidden-word rulecard filtering
  - Dynamic Truth Anchor injection
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from app.services.supabase_service import supabase_service
from app.services.report_builder import premium_report_builder
from app.services.truth_anchor import build_truth_anchor, forbidden_words_for_rulecards
from app.services.email_service import EmailService
from app.services.persona_classifier import classify_persona

logger = logging.getLogger(__name__)

# 🔥 P0: 이메일 서비스 싱글톤
email_service = EmailService()


def _ensure_dict(v: Any) -> Dict[str, Any]:
    """Convert JSON-ish values to dict safely.

    Supabase (and sometimes frontend) may store JSON columns as strings.
    This helper makes the worker tolerant to that behavior.
    
    🔥 P0 FIX: 문자열이 '{'로 시작하지 않으면 JSON 파싱 시도 안 함
    """
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        v_stripped = v.strip()
        # 🔥 P0: JSON-like 문자열만 파싱 시도 (birth_text 같은 일반 문자열 보호)
        if not v_stripped.startswith("{"):
            if v_stripped:
                logger.debug(f"[Worker] 비-JSON 문자열 (birth_text?): {v_stripped[:50]}...")
            return {}
        try:
            vv = json.loads(v_stripped)
            return vv if isinstance(vv, dict) else {}
        except Exception:
            if v_stripped:
                logger.warning(f"[Worker] JSON 파싱 실패: {v_stripped[:100]}..." if len(v_stripped) > 100 else f"[Worker] JSON 파싱 실패: {v_stripped}")
            return {}
    return {}


def _ensure_list(v: Any) -> List[Any]:
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            vv = json.loads(v)
            return vv if isinstance(vv, list) else []
        except Exception:
            return []
    return []


def _fill_survey_defaults(survey_data: Dict[str, Any]) -> Dict[str, Any]:
    """🔥 P0 FIX: survey_data가 비어있어도 거절/사과 없이 작성되도록 기본값 채우기"""
    defaults = {
        "industry": "(일반 비즈니스)",
        "revenue": "(미입력)",
        "painPoint": "(성장/수익 개선)",
        "goal": "(안정적 성장)",
        "time": "(풀타임)",
    }
    
    result = dict(survey_data)  # 복사
    
    for key, default_val in defaults.items():
        if not result.get(key):
            result[key] = default_val
    
    return result


class ReportWorker:
    """Background worker that generates premium report sections."""

    DEFAULT_SECTION_IDS = ["exec", "money", "business", "team", "health", "calendar", "sprint"]

    def __init__(self) -> None:
        # 🔥 P0: 싱글톤 인스턴스 사용 (클래스가 아님)
        self.supabase = supabase_service

    async def run_job(self, job_id: str, rulestore: Any = None) -> Tuple[bool, str]:
        """Entry point called by routers (backward compatible)."""
        try:
            await self._execute_job(job_id=job_id, rulestore=rulestore)
            return True, "success"
        except Exception as e:
            logger.exception(f"[Worker] run_job 실패: {job_id}")
            # 🔥 P0: fail_job도 async
            try:
                await self.supabase.fail_job(job_id, str(e)[:500])
            except Exception as fe:
                logger.error(f"[Worker] fail_job 호출 실패: {fe}")
            return False, str(e)

    async def _execute_job(self, job_id: str, rulestore: Any = None) -> None:
        start_ts = time.time()
        logger.info(f"[Worker] 🚀 Job 시작: {job_id}")

        # 🔥 P0 FIX: get_report_job → get_job (async)
        job = await self.supabase.get_job(job_id)
        if not job:
            raise RuntimeError(f"job not found: {job_id}")

        # P0: Supabase JSON columns can be string
        input_json = _ensure_dict(job.get("input_json") or job.get("input_data") or {})
        survey_data = _ensure_dict(input_json.get("survey_data") or input_json.get("survey") or {})
        user_question = (input_json.get("user_question") or input_json.get("question") or "").strip()
        
        # 🔥 P0 FIX: survey_data 기본값 채우기 (거절/사과 방지)
        survey_data = _fill_survey_defaults(survey_data)

        # saju_result can be nested
        saju_result = _ensure_dict(input_json.get("saju_result") or input_json.get("saju") or job.get("saju_json") or {})
        saju_data = self._prepare_saju_data(saju_result=saju_result, input_json=input_json)

        # Validate required pillars
        missing = [k for k in ("year_pillar", "month_pillar", "day_pillar") if not saju_data.get(k)]
        if missing:
            logger.error(f"[Worker] 사주 데이터 누락: {missing}. input_json keys: {list(input_json.keys())}")
            logger.error(f"[Worker] saju_result keys: {list(saju_result.keys()) if saju_result else 'EMPTY'}")
            raise ValueError(f"사주 데이터 누락: {missing}.")

        logger.info(f"[Worker] 🔍 사주 추출 완료: 년={saju_data.get('year_pillar')} 월={saju_data.get('month_pillar')} 일={saju_data.get('day_pillar')} 시={saju_data.get('hour_pillar')}")

        # target year
        target_year = input_json.get("target_year") or input_json.get("year")
        try:
            target_year = int(target_year) if target_year is not None else None
        except Exception:
            target_year = None
        if not target_year:
            target_year = time.localtime().tm_year

        # 🔥🔥🔥 user_name 다중 폴백 (호칭 처리용)
        user_name = (
            input_json.get("name")
            or input_json.get("user_name")
            or survey_data.get("name")
            or survey_data.get("user_name")
            or survey_data.get("nickname")
            or survey_data.get("이름")
            or survey_data.get("이름 (닉네임)")
            or ""
        )
        if user_name:
            logger.info(f"[Worker] 👤 사용자 이름: {user_name}")
        else:
            logger.warning(f"[Worker] ⚠️ 사용자 이름 없음 - '귀하' 사용")

        # 🔥🔥🔥 페르소나 분류 (마스터 샘플 선택용)
        persona_id = classify_persona(saju_data)
        logger.info(f"[Worker] 🎭 페르소나 분류: {persona_id}")

        # sections
        requested_sections = _ensure_list(input_json.get("sections"))
        section_ids = [s for s in requested_sections if isinstance(s, str)] or list(self.DEFAULT_SECTION_IDS)

        # rulecards (physical forbidden-word blocking)
        all_cards = self._get_all_cards(rulestore)
        all_cards = self._filter_forbidden_rulecards(all_cards=all_cards, saju_data=saju_data)

        # 진행률 업데이트 (🔥 status는 running만 사용 - DB constraint)
        await self.supabase.update_progress(job_id, 10, "running")

        # Generate each section
        completed_sections = []
        for i, section_id in enumerate(section_ids):
            try:
                await self._generate_and_save_section(
                    job_id=job_id,
                    section_id=section_id,
                    saju_data=saju_data,
                    survey_data=survey_data,
                    target_year=target_year,
                    user_question=user_question,
                    all_cards=all_cards,
                    persona_id=persona_id,
                    user_name=user_name,  # 🔥 호칭 처리용
                )
                completed_sections.append(section_id)
                # 진행률 업데이트 (10~90%)
                progress = 10 + int(80 * (i + 1) / len(section_ids))
                await self.supabase.update_progress(job_id, progress, "running")
            except Exception as e:
                logger.error(f"[Worker] 섹션 생성 실패: {section_id} | {e}")
                # Continue with other sections

        elapsed_ms = int((time.time() - start_ts) * 1000)
        
        # 🔥 P0 FIX: mark_job_done → complete_job (async)
        # saju_json도 함께 저장
        saju_json_to_save = {
            "year_pillar": saju_data.get("year_pillar"),
            "month_pillar": saju_data.get("month_pillar"),
            "day_pillar": saju_data.get("day_pillar"),
            "hour_pillar": saju_data.get("hour_pillar"),
            "day_master": saju_data.get("day_master"),
        }
        
        result_json = {
            "completed_sections": completed_sections,
            "target_year": target_year,
            "elapsed_ms": elapsed_ms,
        }
        
        await self.supabase.complete_job(
            job_id=job_id,
            result_json=result_json,
            markdown="",  # full markdown은 별도 조합
            saju_json=saju_json_to_save,
        )
        logger.info(f"[Worker] ✅ Job 완료: {job_id} ({elapsed_ms}ms, {len(completed_sections)}/{len(section_ids)} 섹션)")
        
        # 🔥🔥🔥 P0 FIX: 이메일 발송 로직 추가
        await self._send_completion_email(job=job, job_id=job_id, target_year=target_year)

    async def _send_completion_email(self, job: Dict[str, Any], job_id: str, target_year: int) -> None:
        """리포트 완료 이메일 발송"""
        try:
            input_json = _ensure_dict(job.get("input_json") or {})
            
            # 🔥 P0 FIX: DB 컬럼명은 user_email (email 아님)
            to_email = job.get("user_email") or input_json.get("email") or ""
            if not to_email:
                logger.warning(f"[Worker] 이메일 주소 없음: {job_id}")
                return
            
            # 사용자 이름
            name = input_json.get("name") or "고객"
            
            # 🔥 P0 FIX: job_id와 token 분리
            token = job.get("public_token") or job.get("token") or ""
            if not token:
                logger.warning(f"[Worker] 토큰 없음: {job_id}")
                return
            
            # 이메일 발송
            success = await email_service.send_report_complete(
                to_email=to_email,
                name=name,
                job_id=job_id,
                token=token,
                target_year=target_year,
                pdf_url=None  # PDF는 별도 생성
            )
            
            if success:
                logger.info(f"[Worker] 📧 이메일 발송 성공: {to_email}")
            else:
                logger.warning(f"[Worker] 📧 이메일 발송 실패/스킵: {to_email}")
                
        except Exception as e:
            logger.error(f"[Worker] 📧 이메일 발송 에러: {e}")
            # 이메일 발송 실패해도 job은 완료 처리

    def _prepare_saju_data(self, saju_result: Dict[str, Any], input_json: Dict[str, Any] = None) -> Dict[str, Any]:
        """사주 데이터 준비 - 다양한 경로에서 pillar 추출"""
        sr = _ensure_dict(saju_result)
        ij = _ensure_dict(input_json) if input_json else {}

        # nested saju 구조 지원 (calculate API 응답 구조)
        nested_saju = _ensure_dict(sr.get("saju") or {})

        def _extract_ganji(pillar_data) -> str:
            """pillar가 dict면 ganji 추출, 아니면 그대로 반환"""
            if not pillar_data:
                return ""
            if isinstance(pillar_data, dict):
                return pillar_data.get("ganji", "") or pillar_data.get("value", "") or ""
            return str(pillar_data) if pillar_data else ""

        # 3단계 fallback 체인:
        # 1) saju_result.saju.year_pillar (calculate API 구조)
        # 2) saju_result.year_pillar (직접 접근)
        # 3) input_json.year_pillar (top-level)
        y = _extract_ganji(nested_saju.get("year_pillar")) or _extract_ganji(sr.get("year_pillar")) or _extract_ganji(ij.get("year_pillar")) or sr.get("year") or sr.get("yearGanji") or ""
        m = _extract_ganji(nested_saju.get("month_pillar")) or _extract_ganji(sr.get("month_pillar")) or _extract_ganji(ij.get("month_pillar")) or sr.get("month") or sr.get("monthGanji") or ""
        d = _extract_ganji(nested_saju.get("day_pillar")) or _extract_ganji(sr.get("day_pillar")) or _extract_ganji(ij.get("day_pillar")) or sr.get("day") or sr.get("dayGanji") or ""
        h = _extract_ganji(nested_saju.get("hour_pillar")) or _extract_ganji(sr.get("hour_pillar")) or _extract_ganji(ij.get("hour_pillar")) or sr.get("hour") or sr.get("hourGanji") or ""

        saju_summary = _ensure_dict(sr.get("saju_summary") or sr.get("summary") or ij.get("saju_summary") or {})
        birth_info = _ensure_dict(sr.get("birth_info") or sr.get("birth") or ij.get("birth_info") or {})
        day_master = sr.get("day_master") or sr.get("dayMaster") or ij.get("day_master") or saju_summary.get("day_master") or (d[0] if d else "")

        return {
            "year_pillar": y,
            "month_pillar": m,
            "day_pillar": d,
            "hour_pillar": h,
            "day_master": day_master,
            "saju_summary": saju_summary,
            "birth_info": birth_info,
            "primary_structure": sr.get("primary_structure") or ij.get("primary_structure") or saju_summary.get("primary_structure"),
            "month_tengod": sr.get("month_tengod") or ij.get("month_tengod") or saju_summary.get("month_tengod"),
            "month_branch_ten_god": sr.get("month_branch_ten_god") or ij.get("month_branch_ten_god"),
        }

    def _get_all_cards(self, rulestore: Any) -> List[Dict[str, Any]]:
        if rulestore is None:
            return []
        if hasattr(rulestore, "get_all_cards"):
            return list(rulestore.get_all_cards())
        if hasattr(rulestore, "all_cards"):
            return list(getattr(rulestore, "all_cards"))
        if hasattr(rulestore, "cards"):
            return list(getattr(rulestore, "cards"))
        if isinstance(rulestore, list):
            return list(rulestore)
        return []

    def _filter_forbidden_rulecards(self, all_cards: List[Dict[str, Any]], saju_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """P0: 환각 유발 RuleCard 물리적 차단 (ENV로 토글, 기본 OFF)"""
        forbidden = set(forbidden_words_for_rulecards(saju_data))
        
        # 🔥 P0: 필터 비활성화 시 즉시 반환 (로그 없음)
        if not forbidden:
            return all_cards
        
        # 필터 활성화 시에만 로그
        logger.info(f"[Worker] 🔧 룰카드 필터 활성화 (금지어: {sorted(forbidden)})")

        filtered: List[Dict[str, Any]] = []
        removed_examples: List[str] = []  # 제거된 카드 예시
        
        for c in all_cards:
            if not isinstance(c, dict):
                continue
            # 카드 텍스트 전체에서 금지어 검색
            blob = " ".join([
                str(c.get("topic", "")),
                str(c.get("interpretation", "")),
                str(c.get("action", "")),
                str(c.get("mechanism", "")),
                str(c.get("tags", "")),
            ])
            matched_forbidden = [w for w in forbidden if w in blob]
            if matched_forbidden:
                if len(removed_examples) < 10:  # 최대 10개 예시
                    removed_examples.append(f"{c.get('id', 'N/A')}:{matched_forbidden}")
                continue
            filtered.append(c)

        removed = len(all_cards) - len(filtered)
        
        # 상세 로그
        logger.info(f"[Worker] 룰카드 필터: {len(all_cards)} -> {len(filtered)} ({removed}개 제거)")
        if removed_examples:
            logger.info(f"[Worker] 제거된 카드 예시: {removed_examples}")
        
        # 🔥 경고: 전체 삭제 방지
        if len(filtered) == 0 and len(all_cards) > 0:
            logger.error(f"[Worker] ⚠️ 모든 룰카드가 삭제됨! 필터 로직 점검 필요!")
            return all_cards
        
        return filtered

    async def _generate_and_save_section(
        self,
        job_id: str,
        section_id: str,
        saju_data: Dict[str, Any],
        survey_data: Dict[str, Any],
        target_year: int,
        user_question: str,
        all_cards: List[Dict[str, Any]],
        persona_id: str = "standard",
        user_name: str = "",  # 🔥 호칭 처리용
    ) -> None:
        selected_cards = self._select_rulecards_for_section(all_cards=all_cards, section_id=section_id)
        
        # 🔥 Build truth anchor for this section (survey_data 포함)
        truth_anchor = build_truth_anchor(
            saju_data=saju_data,
            target_year=target_year,
            section_id=section_id,
            survey_data=survey_data,  # 🔥 비즈니스 병목/투입시간 포함
        )

        result = await premium_report_builder.generate_single_section(
            section_id=section_id,
            saju_data=saju_data,
            rulecards=selected_cards,
            survey_data=survey_data,
            target_year=target_year,
            user_question=user_question,
            truth_anchor=truth_anchor,
            job_id=job_id,
            persona_id=persona_id,
            user_name=user_name,
        )

        # 🔥 P0 FIX: save_section도 async
        await self.supabase.save_section(job_id=job_id, section_id=section_id, content_json=result)
        logger.info(f"[Worker] 섹션 저장 완료: {section_id} ({result.get('char_count', 0)}자) | persona={persona_id} | user={user_name or '귀하'}")

    def _select_rulecards_for_section(self, all_cards: List[Dict[str, Any]], section_id: str, k: int = 24) -> List[Dict[str, Any]]:
        if not all_cards:
            return []

        picked: List[Dict[str, Any]] = []
        for c in all_cards:
            if not isinstance(c, dict):
                continue
            tags = c.get("section_tags") or c.get("tags") or []
            if isinstance(tags, str):
                tags = [tags]
            if section_id in tags:
                picked.append(c)
            if len(picked) >= k:
                break

        # Fill up to k with remaining cards
        if len(picked) < k:
            for c in all_cards:
                if not isinstance(c, dict) or c in picked:
                    continue
                picked.append(c)
                if len(picked) >= k:
                    break

        return picked


# Singleton instance expected by routers
report_worker = ReportWorker()

__all__ = ["ReportWorker", "report_worker"]
