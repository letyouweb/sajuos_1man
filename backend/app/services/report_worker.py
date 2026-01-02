"""
Report Worker v13 - P0 Pivot: 설문 기반 RuleCardScorer 통합
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 P0 핵심 변경:
1) _select_rulecards() → RuleCardScorer.score_cards_for_section() 호출
2) survey_data가 카드 선택에 직접 반영
3) 같은 사주라도 설문에 따라 다른 카드가 선택됨
4) 섹션별 score_trace 저장
5) 🔥 P0: 환각 유발 RuleCard 물리적 필터링 추가
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import asyncio
import json
import logging
import re
import time
from datetime import date
from typing import Dict, Any, Optional, List, Set

from app.services.supabase_service import supabase_service
from app.services.saju_engine import calc_daeun_pillars
from app.services.saju_analyzer import get_saju_summary  # 🔥 P0: 정답지 생성

logger = logging.getLogger(__name__)

_ALL_STEMS_BRANCHES: Set[str] = set(list("갑을병정무기경신임계자축인묘진사오미신유술해"))

# RuleCard 레벨에서 “환각 유발”을 물리적으로 차단할 키워드(문장/단어)
_FORBIDDEN_PHRASES: List[str] = [
    "걸록", "관성 충돌", "충돌 구조", "원국에서 관성", "을목", "병화", "자수"
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 P0: 대운 및 환각 필터 헬퍼 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _year_stem_is_yang(stem_ko: str) -> bool:
    """년간이 양간인지 확인 (갑병무경임)"""
    return stem_ko in ["갑", "병", "무", "경", "임"]


def _normalize_gender(g: str) -> str:
    """성별 정규화"""
    if not g:
        return ""
    g = str(g).strip().lower()
    if g in ["female", "f", "여", "여자", "여성"]:
        return "female"
    if g in ["male", "m", "남", "남자", "남성"]:
        return "male"
    return g


def _calc_age(birth_info: dict) -> int:
    """생년월일로 만 나이 계산"""
    if not birth_info:
        return 0
    y = birth_info.get("year")
    m = birth_info.get("month", 1)
    d = birth_info.get("day", 1)
    if not y:
        return 0
    try:
        today = date.today()
        age = today.year - int(y)
        if (today.month, today.day) < (int(m), int(d)):
            age -= 1
        return max(age, 0)
    except:
        return 0


def _extract_allowed_saju_chars(saju_data: Dict[str, Any]) -> Set[str]:
    """
    원국(년/월/일/시)에서 실제 등장하는 천간/지지 글자만 추출.
    예: "무오" → {"무","오"}
    """
    allowed: Set[str] = set()
    for k in ("year_pillar", "month_pillar", "day_pillar", "hour_pillar"):
        v = saju_data.get(k) or ""
        if isinstance(v, dict):
            v = v.get("ganji") or v.get("value") or ""
        v = str(v)
        for ch in v:
            if ch in _ALL_STEMS_BRANCHES:
                allowed.add(ch)
    return allowed


def _card_text_blob(card: Dict[str, Any]) -> str:
    """RuleCard의 주요 텍스트 필드를 하나로 합쳐 검사 대상 문자열을 만든다."""
    parts: List[str] = []
    for key in ("topic", "subtopic", "trigger", "mechanism", "interpretation", "action"):
        val = card.get(key)
        if val:
            parts.append(str(val))
    tags = card.get("tags")
    if isinstance(tags, list):
        parts.append(" ".join([str(x) for x in tags]))
    elif tags:
        parts.append(str(tags))
    cautions = card.get("cautions")
    if isinstance(cautions, list):
        parts.append(" ".join([str(x) for x in cautions]))
    elif cautions:
        parts.append(str(cautions))
    return " ".join(parts)


def _contains_disallowed_stems_branches(text: str, allowed_chars: Set[str]) -> List[str]:
    """
    텍스트에서 천간/지지 글자를 스캔해서,
    원국에 없는 글자가 나오면 리턴(검출 리스트).
    """
    if not text:
        return []
    found = set([ch for ch in text if ch in _ALL_STEMS_BRANCHES])
    disallowed = sorted([ch for ch in found if ch not in allowed_chars])
    return disallowed


def _filter_rulecards_for_hallucinations(all_cards: List[Dict[str, Any]], saju_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    🔥 P0: LLM에게 전달하기 전에 환각 유발 카드들을 물리적으로 제거한다.
    - 원국에 없는 천간/지지 글자가 카드 텍스트에 등장하면 제거
    - 금지어(걸록/관성충돌/을목/병화/자수 등) 포함 카드 제거
    """
    allowed_chars = _extract_allowed_saju_chars(saju_data)
    if not allowed_chars:
        logger.warning("[Worker] allowed_chars 추출 실패: 원국 간지 누락 → RuleCard 필터 생략")
        return all_cards

    filtered: List[Dict[str, Any]] = []
    dropped = 0
    for c in all_cards:
        blob = _card_text_blob(c)
        if any(p in blob for p in _FORBIDDEN_PHRASES):
            dropped += 1
            continue
        disallowed = _contains_disallowed_stems_branches(blob, allowed_chars)
        if disallowed:
            dropped += 1
            continue
        filtered.append(c)

    if dropped:
        logger.info(f"[Worker] RuleCard 물리 차단: dropped={dropped} / kept={len(filtered)} (allowed={''.join(sorted(allowed_chars))})")
    return filtered


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥🔥🔥 P0: 1인 자영업자용 섹션 스펙 (새 ID 매핑)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ONEMAN_SECTION_SPECS = [
    {"id": "exec", "title": "🌦️ 2026 비즈니스 전략 기상도", "order": 1},
    {"id": "money", "title": "💰 자본 유동성 및 현금흐름 최적화", "order": 2},
    {"id": "business", "title": "📍 시장 포지셔닝 및 상품 확장 전략", "order": 3},
    {"id": "team", "title": "🤝 조직 확장 및 파트너십 가이드", "order": 4},
    {"id": "health", "title": "🧯 오너 리스크 관리 및 번아웃 방어", "order": 5},
    {"id": "calendar", "title": "🗓️ 12개월 비즈니스 스프린트 캘린더", "order": 6},
    {"id": "sprint", "title": "🚀 향후 90일 매출 극대화 액션플랜", "order": 7},
]


class ReportWorker:
    """백그라운드 리포트 생성 워커 - P0 Pivot"""
    
    _running_jobs: set = set()
    
    async def run_job(self, job_id: str, rulestore: Any = None) -> None:
        """Job 실행"""
        if job_id in self._running_jobs:
            logger.warning(f"[Worker] 이미 실행 중: {job_id}")
            return
        
        self._running_jobs.add(job_id)
        start_time = time.time()
        
        if rulestore:
            card_count = len(getattr(rulestore, 'cards', [])) if hasattr(rulestore, 'cards') else 0
            logger.info(f"[Worker] RuleStore 수신: total={card_count}장")
        else:
            logger.warning(f"[Worker] ⚠️ RuleStore가 None!")
        
        try:
            success, error_msg = await self._execute_job(job_id, rulestore)
            elapsed = int((time.time() - start_time) * 1000)
            
            if success:
                logger.info(f"[Worker] ✅ Job 완료: {job_id} ({elapsed}ms)")
            else:
                logger.error(f"[Worker] ❌ Job 실패: {job_id} | {error_msg}")
            
        except Exception as e:
            logger.error(f"[Worker] ❌ Job 실패: {job_id} | {e}")
            try:
                await supabase_service.fail_job(job_id, str(e)[:500])
            except:
                pass
            
            try:
                job = await supabase_service.get_job(job_id)
                if job:
                    await self._send_failure_email(job, str(e))
            except Exception as email_err:
                logger.warning(f"[Worker] 실패 이메일 발송 실패: {email_err}")
        
        finally:
            self._running_jobs.discard(job_id)
    
    async def _execute_job(self, job_id: str, rulestore: Any = None) -> tuple[bool, str]:
        """실제 Job 실행"""
        job = await supabase_service.get_job(job_id)
        if not job:
            raise ValueError(f"Job 없음: {job_id}")
        
        email = job.get("user_email", "")
        input_json = job.get("input_json") or job.get("input_data") or {}
        
        name = input_json.get("name", "고객")
        target_year = input_json.get("target_year", 2026)
        question = input_json.get("question", "")
        survey_data = input_json.get("survey_data") or {}
        
        await supabase_service.update_progress(job_id, 5, "running")
        
        saju_data = self._prepare_saju_data(input_json)
        
        missing_pillars = []
        for key in ["year_pillar", "month_pillar", "day_pillar"]:
            if not saju_data.get(key):
                missing_pillars.append(key)
        
        if missing_pillars:
            error_msg = f"사주 데이터 누락: {missing_pillars}. 사주 없는 사주 리포트는 상품 가치가 없습니다."
            logger.error(f"[Worker] ❌❌❌ {error_msg}")
            await supabase_service.fail_job(job_id, error_msg)
            return False, error_msg
        
        logger.info(f"[Worker] ✅ 사주 검증 통과: {saju_data['year_pillar']}/{saju_data['month_pillar']}/{saju_data['day_pillar']}/{saju_data.get('hour_pillar', '-')}")
        
        feature_tags = self._build_feature_tags(saju_data)
        all_cards = self._get_all_cards_as_dict(rulestore)
        
        sections_result = {}
        failed_sections = []
        total_sections = len(ONEMAN_SECTION_SPECS)
        all_used_card_ids = []
        section_match_summaries = {}
        
        for idx, spec in enumerate(ONEMAN_SECTION_SPECS):
            section_id = spec["id"]
            section_title = spec["title"]
            
            progress = int((idx / total_sections) * 90) + 10
            await supabase_service.update_progress(job_id, progress, "running")
            
            try:
                # 🔥🔥🔥 P0 핵심: RuleCardScorer로 설문 기반 카드 선택
                section_cards, match_summary = self._select_rulecards_for_section(
                    all_cards=all_cards,
                    section_id=section_id,
                    feature_tags=feature_tags,
                    survey_data=survey_data,
                    saju_data=saju_data
                )
                
                section_match_summaries[section_id] = match_summary
                
                for card in section_cards[:10]:
                    if card.get("id") and card["id"] not in all_used_card_ids:
                        all_used_card_ids.append(card["id"])
                
                section_result = await self._generate_section(
                    section_id=section_id,
                    section_title=section_title,
                    saju_data=saju_data,
                    rulecards=section_cards,
                    feature_tags=feature_tags,
                    target_year=target_year,
                    question=question,
                    survey_data=survey_data,
                    match_summary=match_summary
                )
                
                content = section_result.get("content", {})
                body_markdown = content.get("body_markdown", "")
                if not body_markdown or len(body_markdown) < 300:
                    fallback_text = f"## {section_title}\n\n데이터 부족으로 상세 분석이 제한됩니다. 고객센터로 문의해 주세요. 오류 코드: SECTION_EMPTY_{section_id}"
                    content["body_markdown"] = fallback_text
                
                content["match_summary"] = match_summary
                content["used_rulecard_ids"] = [c.get("id") for c in section_cards[:10]]
                
                await supabase_service.save_section(job_id=job_id, section_id=section_id, content_json=content)
                sections_result[section_id] = content
                
            except Exception as e:
                logger.error(f"[Worker] 섹션 실패: {section_id} | {e}")
                failed_sections.append({"section_id": section_id, "errors": [str(e)]})
        
        result_json = {
            "name": name,
            "target_year": target_year,
            "saju_summary": saju_data,
            "survey_data": survey_data,
            "sections": sections_result,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "failed_sections": failed_sections or None,
            "top_used_rulecard_ids": all_used_card_ids[:20],
            "section_match_summaries": section_match_summaries,
        }
        
        markdown = self._build_markdown(result_json, saju_data)
        await supabase_service.complete_job(job_id, result_json, markdown, saju_data)
        
        try:
            await self._send_completion_email(email, name, job_id)
        except Exception as e:
            logger.warning(f"[Worker] 완료 이메일 실패: {e}")
        
        return True, ""
    
    def _get_all_cards_as_dict(self, rulestore: Any) -> List[Dict]:
        if not rulestore: return []
        all_cards = getattr(rulestore, 'cards', [])
        return [self._card_to_dict(c) for c in all_cards]
    
    def _select_rulecards_for_section(
        self,
        all_cards: List[Dict],
        section_id: str,
        feature_tags: List[str],
        survey_data: Dict,
        saju_data: Dict
    ) -> tuple[List[Dict], Dict]:
        """
        🔥🔥🔥 P0 핵심: RuleCardScorer를 사용하여 설문 기반 카드 선택
        """
        try:
            from app.services.rulecard_scorer import rulecard_scorer

            # 🔥 P0: 환각 유발 RuleCard “물리 차단”
            filtered_cards = _filter_rulecards_for_hallucinations(all_cards, saju_data)
            if not filtered_cards:
                logger.warning("[Worker] RuleCard 필터 결과 0장 → 원본 all_cards로 되돌림")
                filtered_cards = all_cards

            id_map = {c.get("id"): c for c in filtered_cards if isinstance(c, dict) and c.get("id") is not None}
            
            section_cards = rulecard_scorer.score_cards_for_section(
                all_cards=filtered_cards,
                section_id=section_id,
                feature_tags=feature_tags,
                survey_data=survey_data,
                existing_topics=set(),
                saju_data=saju_data
            )
            
            selected_cards = []
            for scored_card in section_cards.cards:
                card_dict = {
                    "id": scored_card.card_id,
                    "topic": scored_card.topic,
                    "subtopic": scored_card.subtopic,
                    "score": scored_card.final_score,
                    "matched_tags": scored_card.matched_tags,
                    "score_trace": scored_card.score_trace.to_dict(),
                }
                # 원본 카드에서 추가 필드 복사 (O(1))
                orig_card = id_map.get(scored_card.card_id) or {}
                card_dict.update({
                    "trigger": orig_card.get("trigger", ""),
                    "mechanism": orig_card.get("mechanism", ""),
                    "interpretation": orig_card.get("interpretation", ""),
                    "action": orig_card.get("action", ""),
                    "cautions": orig_card.get("cautions", []),
                    "tags": orig_card.get("tags", [])
                })
                selected_cards.append(card_dict)
            
            match_summary = section_cards.match_summary
            match_summary.update({"avg_score": section_cards.avg_score, "total_selected": section_cards.total_cards})
            return selected_cards, match_summary
            
        except Exception as e:
            logger.exception(f"[Worker] RuleCardScorer 호출 실패: {e}")
            raise RuntimeError(f"RuleCardScorer 호출 실패: {e}") from e

    async def _generate_section(self, section_id: str, section_title: str, saju_data: Dict, rulecards: List, feature_tags: List, target_year: int, question: str, survey_data: Dict = None, match_summary: Dict = None) -> Dict[str, Any]:
        try:
            from app.services.report_builder import premium_report_builder
            result = await premium_report_builder.regenerate_single_section(
                section_id=section_id, saju_data=saju_data, rulecards=rulecards,
                feature_tags=feature_tags, target_year=target_year, user_question=question, survey_data=survey_data
            )
            if not result.get("success"):
                return {"ok": False, "content": {"title": section_title, "body_markdown": ""}, "guardrail_errors": [result.get("error")]}
            
            section_data = result.get("section", {})
            content = {"title": section_title, "section_id": section_id, "body_markdown": section_data.get("body_markdown", ""), **section_data}
            return {"ok": bool(content["body_markdown"]), "content": content, "guardrail_errors": []}
        except Exception as e:
            return {"ok": False, "content": {"title": section_title, "body_markdown": ""}, "guardrail_errors": [str(e)]}

    def _prepare_saju_data(self, input_json: Dict) -> Dict:
        saju_result = input_json.get("saju_result") or {}
        extract = lambda p: p.get("ganji", "") if isinstance(p, dict) else (str(p) if p else "")
        pillars = {k: extract(saju_result.get(k)) for k in ["year_pillar", "month_pillar", "day_pillar", "hour_pillar"]}
        
        birth_info = saju_result.get("birth_info", {})
        gender = _normalize_gender(input_json.get("gender") or birth_info.get("gender") or saju_result.get("gender", ""))
        age = _calc_age(birth_info)
        
        # 대운 계산
        direction, daeun_list, current_daeun = None, [], None
        if gender and pillars["year_pillar"] and pillars["month_pillar"] and age:
            is_yang = _year_stem_is_yang(pillars["year_pillar"][:1])
            direction = "forward" if ((gender == "male" and is_yang) or (gender == "female" and not is_yang)) else "backward"
            daeun_list = calc_daeun_pillars(pillars["month_pillar"], direction, count=10)
            if daeun_list:
                idx = (age - 3) // 10
                if 0 <= idx < len(daeun_list): current_daeun = daeun_list[idx]
        
        return {**pillars, "day_master": saju_result.get("day_master"), "birth_info": birth_info, "gender": gender, "age": age, "daeun_direction": direction, "daeun_list": daeun_list, "current_daeun": current_daeun}

    def _build_feature_tags(self, saju_data: Dict) -> List[str]:
        tags = []
        for k in ["year_pillar", "month_pillar", "day_pillar", "hour_pillar"]:
            p = saju_data.get(k, "")
            if len(p) >= 2: tags.extend([f"천간:{p[0]}", f"지지:{p[1]}"])
        if saju_data.get("day_master"): tags.append(f"일간:{saju_data['day_master']}")
        return tags

    def _card_to_dict(self, card) -> Dict:
        content = getattr(card, 'content', {}) or {}
        return {"id": getattr(card, 'id', ''), "topic": getattr(card, 'topic', ''), "subtopic": getattr(card, 'subtopic', '') or (getattr(card, 'meta', {}) or {}).get('subtopic', ''), "tags": getattr(card, 'tags', []), "priority": getattr(card, 'priority', 0), "trigger": getattr(card, 'trigger', ''), "mechanism": getattr(card, 'mechanism', '') or content.get('mechanism', ''), "interpretation": getattr(card, 'interpretation', '') or content.get('interpretation', ''), "action": getattr(card, 'action', '') or content.get('action', ''), "cautions": getattr(card, 'cautions', []) or content.get('cautions', [])}

    def _build_markdown(self, result_json: Dict, saju_data: Dict) -> str:
        lines = [f"# {result_json.get('name', '고객')}님의 {result_json.get('target_year', 2026)}년 1인 사업가 전략 리포트\n"]
        if result_json.get("survey_data"):
            lines.append("## 📋 비즈니스 프로필\n")
            for k, v in result_json["survey_data"].items(): lines.append(f"- {k}: {v}")
            lines.append("\n---\n")
        lines.append("## 📜 사주 원국\n")
        for k in ["year_pillar", "month_pillar", "day_pillar", "hour_pillar"]: lines.append(f"- {k}: {saju_data.get(k, '-')}")
        lines.append("\n---\n")
        sections = result_json.get("sections", {})
        for spec in ONEMAN_SECTION_SPECS:
            lines.append(f"## {spec['title']}\n{sections.get(spec['id'], {}).get('body_markdown', '내용 없음')}\n")
        return "\n".join(lines)

    async def _send_completion_email(self, email: str, name: str, job_id: str):
        if not email: return
        try:
            from app.services.email_sender import email_sender
            job = await supabase_service.get_job(job_id)
            if job and job.get("public_token"):
                await email_sender.send_report_complete(to_email=email, name=name, report_id=job_id, access_token=job["public_token"], target_year=2026)
        except Exception as e: logger.warning(f"이메일 발송 실패: {e}")

    async def _send_failure_email(self, job: Dict, error: str):
        email = job.get("user_email")
        if email:
            try:
                from app.services.email_sender import email_sender
                await email_sender.send_report_failed(to_email=email, name=(job.get("input_json") or {}).get("name", "고객"), report_id=job.get("id", ""), error_message=error[:200])
            except Exception as e: logger.warning(f"실패 이메일 발송 실패: {e}")

report_worker = ReportWorker()