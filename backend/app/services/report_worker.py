"""
Report Worker v13 - P0 Pivot: 설문 기반 RuleCardScorer 통합
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 P0 핵심 변경:
1) _select_rulecards() → RuleCardScorer.score_cards_for_section() 호출
2) survey_data가 카드 선택에 직접 반영
3) 같은 사주라도 설문에 따라 다른 카드가 선택됨
4) 섹션별 score_trace 저장
5) 용어 정규화 (걸록격 -> 건록격 등) 적용
6) 대운 계산 예외 처리 (계산 실패 시에도 중단 X)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import asyncio
import json
import logging
import time
from datetime import date
from typing import Dict, Any, Optional, List, Tuple

from app.services.supabase_service import supabase_service
from app.services.saju_engine import calc_daeun_pillars
from app.services.saju_analyzer import get_saju_summary  # 🔥 P0: 정답지 생성

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 P0: Supabase JSON 문자열 → dict 안전 변환
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _ensure_dict(v: Any) -> Dict:
    """Supabase/프론트에서 JSON이 문자열로 올 때 dict로 안전 변환"""
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            vv = json.loads(v)
            return vv if isinstance(vv, dict) else {}
        except Exception:
            return {}
    return {}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 P0: 생성 결과 용어 정규화 (룰카드/LLM 오타/잔존어 방지)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_NORMALIZE_REPLACEMENTS = {
    "걸록격": "건록격",
    "걸록": "건록",  # 🔥 P0: "걸록이 있다" 같은 패턴도 처리
}

def normalize_generated_text(text: str) -> str:
    """생성된 텍스트의 오타/잔존어 정규화"""
    if not text:
        return text or ""
    out = text
    for src, dst in _NORMALIZE_REPLACEMENTS.items():
        out = out.replace(src, dst)
    return out


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 P0: 대운 계산 헬퍼 함수
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 P0: 원국 팩트(십성/오행) 확정 유틸
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEM_ELEM_POLAR = {
    "갑": ("wood", "yang"), "을": ("wood", "yin"),
    "병": ("fire", "yang"), "정": ("fire", "yin"),
    "무": ("earth", "yang"), "기": ("earth", "yin"),
    "경": ("metal", "yang"), "신": ("metal", "yin"),
    "임": ("water", "yang"), "계": ("water", "yin"),
}

GENERATOR = {"wood": "fire", "fire": "earth", "earth": "metal", "metal": "water", "water": "wood"}
CONTROLS = {"wood": "earth", "earth": "water", "water": "fire", "fire": "metal", "metal": "wood"}


def _pillar_parts(p: str):
    if not p or len(p) < 2:
        return ("", "")
    return (p[0], p[1])


def _ten_god(day_stem: str, other_stem: str) -> str:
    """일간 기준 십성 계산(천간/지장간 공용)"""
    if not day_stem or not other_stem:
        return ""
    dm = STEM_ELEM_POLAR.get(day_stem)
    ot = STEM_ELEM_POLAR.get(other_stem)
    if not dm or not ot:
        return ""
    dm_elem, dm_pol = dm
    ot_elem, ot_pol = ot

    # 비겁(동일 오행)
    if ot_elem == dm_elem:
        return "비견" if ot_pol == dm_pol else "겁재"
    # 식상(내가 생)
    if GENERATOR[dm_elem] == ot_elem:
        return "식신" if ot_pol == dm_pol else "상관"
    # 재성(내가 극)
    if CONTROLS[dm_elem] == ot_elem:
        return "편재" if ot_pol == dm_pol else "정재"
    # 관성(나를 극)
    if CONTROLS[ot_elem] == dm_elem:
        return "편관" if ot_pol == dm_pol else "정관"
    # 인성(나를 생)
    if GENERATOR[ot_elem] == dm_elem:
        return "편인" if ot_pol == dm_pol else "정인"
    return ""


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
        
        finally:
            self._running_jobs.discard(job_id)
    
    async def _execute_job(self, job_id: str, rulestore: Any = None) -> tuple[bool, str]:
        """실제 Job 실행"""
        job = await supabase_service.get_job(job_id)
        if not job:
            raise ValueError(f"Job 없음: {job_id}")
        
        email = job.get("user_email", "")
        # 🔥 P0 FIX: JSON 문자열 → dict 안전 변환
        input_json_raw = job.get("input_json") or job.get("input_data") or {}
        input_json = _ensure_dict(input_json_raw)
        if not input_json and isinstance(input_json_raw, str):
            logger.warning(f"[Worker] input_json이 문자열인데 파싱 실패: {str(input_json_raw)[:120]}...")
        
        name = input_json.get("name", "고객")
        target_year = input_json.get("target_year", 2026)
        question = input_json.get("question", "")
        survey_data = _ensure_dict(input_json.get("survey_data") or {})
        
        await supabase_service.update_progress(job_id, 5, "running")
        
        # 🔥 P0: 사주 데이터 추출
        saju_data = self._prepare_saju_data(input_json)
        
        # 사주 데이터 무결성 체크
        missing_pillars = []
        for key in ["year_pillar", "month_pillar", "day_pillar"]:
            if not saju_data.get(key):
                missing_pillars.append(key)
        
        if missing_pillars:
            error_msg = f"사주 데이터 누락: {missing_pillars}."
            await supabase_service.fail_job(job_id, error_msg)
            return False, error_msg
        
        # Feature Tags 생성
        feature_tags = self._build_feature_tags(saju_data)
        all_cards = self._get_all_cards_as_dict(rulestore)
        
        sections_result = {}
        failed_sections = []
        total_sections = len(ONEMAN_SECTION_SPECS)
        all_used_card_ids = []
        used_ids: set = set()
        section_match_summaries = {}
        
        for idx, spec in enumerate(ONEMAN_SECTION_SPECS):
            section_id = spec["id"]
            section_title = spec["title"]
            
            progress = int((idx / total_sections) * 90) + 10
            await supabase_service.update_progress(job_id, progress, "running")
            
            try:
                # 섹션별 룰카드 선택
                section_cards, match_summary = self._select_rulecards_for_section(
                    all_cards=all_cards,
                    section_id=section_id,
                    feature_tags=feature_tags,
                    survey_data=survey_data,
                    saju_data=saju_data,
                    used_ids=used_ids,
                )
                
                section_match_summaries[section_id] = match_summary
                
                for card in section_cards:
                    if card.get('id'):
                        used_ids.add(card['id'])
                for card in section_cards[:10]:
                    if card.get("id") and card["id"] not in all_used_card_ids:
                        all_used_card_ids.append(card["id"])
                
                # 섹션 생성
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
                ok = section_result.get("ok", True)
                quality_warning = section_result.get("quality_warning", False)
                guardrail_errors = section_result.get("guardrail_errors", [])
                body_markdown = content.get("body_markdown", "")
                
                # 🔥 P0: 오타/잔존어 정규화 필터 적용
                body_markdown = normalize_generated_text(body_markdown)
                content["body_markdown"] = body_markdown
                
                # 빈 섹션 처리
                if not body_markdown or len(body_markdown) < 300:
                    fallback_text = f"## {section_title}\n\n이 섹션의 분석 결과를 생성하는 중 문제가 발생했습니다."
                    content["body_markdown"] = fallback_text
                
                content["match_summary"] = match_summary
                content["used_rulecard_ids"] = [c.get("id") for c in section_cards[:10]]
                
                await supabase_service.save_section(
                    job_id=job_id,
                    section_id=section_id,
                    content_json=content
                )
                
                sections_result[section_id] = content
                
                if not ok:
                    failed_sections.append({"section_id": section_id, "errors": guardrail_errors})
                elif quality_warning:
                    logger.warning(f"[Worker] 섹션 {section_id} 품질 경고: {guardrail_errors}")
                
            except Exception as e:
                logger.error(f"[Worker] 섹션 실패: {section_id} | {e}")
                failed_sections.append({"section_id": section_id, "errors": [str(e)]})
        
        # 최종 결과 저장
        result_json = {
            "name": name,
            "target_year": target_year,
            "saju_summary": {
                "year_pillar": saju_data.get("year_pillar", ""),
                "month_pillar": saju_data.get("month_pillar", ""),
                "day_pillar": saju_data.get("day_pillar", ""),
                "hour_pillar": saju_data.get("hour_pillar", ""),
                "day_master": saju_data.get("day_master", ""),
                "birth_info": saju_data.get("birth_info", ""),
            },
            "survey_data": survey_data,
            "sections": sections_result,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "failed_sections": failed_sections if failed_sections else None,
            "top_used_rulecard_ids": all_used_card_ids[:20],
            "section_match_summaries": section_match_summaries,
        }
        
        saju_json = {
            **saju_data,
            "feature_tags": feature_tags,
            "rulecards_used": all_used_card_ids[:20],
            "calculated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        markdown = self._build_markdown(result_json, saju_data)
        await supabase_service.complete_job(job_id, result_json, markdown, saju_json)
        
        try:
            await self._send_completion_email(email, name, job_id)
        except Exception as e:
            logger.warning(f"[Worker] 완료 이메일 실패: {e}")
        
        return True, ""

    def _prepare_saju_data(self, input_json: Dict) -> Dict:
        """사주 데이터 추출 및 정답지 주입"""
        # 🔥 P0: 디버그 로그 - 실제 들어오는 데이터 구조 확인
        logger.info(f"[Worker] 🔍 input_json keys: {list(input_json.keys())[:10]}")
        
        # 🔥 P0 FIX: JSON 문자열 → dict 안전 변환
        saju_result = _ensure_dict(input_json.get("saju_result") or {})
        
        # 🔥 P0: saju_result가 비어있으면 다른 경로 시도
        if not saju_result:
            # 경로 1: input_json.saju
            saju_result = _ensure_dict(input_json.get("saju") or {})
        if not saju_result:
            # 경로 2: input_json 자체가 saju_result일 수 있음
            if "year_pillar" in input_json or "day_master" in input_json:
                saju_result = input_json
        
        logger.info(f"[Worker] 🔍 saju_result keys: {list(saju_result.keys())[:10] if saju_result else 'EMPTY'}")
        
        target_year = input_json.get("target_year", 2026)
        
        def extract_ganji(pillar_data):
            if not pillar_data: return ""
            if isinstance(pillar_data, dict):
                # 다양한 키 시도: ganji, value, gan+ji
                return pillar_data.get("ganji", "") or pillar_data.get("value", "") or (pillar_data.get("gan", "") + pillar_data.get("ji", ""))
            return str(pillar_data)
        
        # 🔥 P0: 다양한 경로에서 4주 추출
        # 경로 1: saju_result.year_pillar
        year_pillar = extract_ganji(saju_result.get("year_pillar"))
        month_pillar = extract_ganji(saju_result.get("month_pillar"))
        day_pillar = extract_ganji(saju_result.get("day_pillar"))
        hour_pillar = extract_ganji(saju_result.get("hour_pillar"))
        
        # 경로 2: saju_result.saju.year_pillar (nested)
        if not year_pillar:
            nested_saju = _ensure_dict(saju_result.get("saju") or {})
            year_pillar = year_pillar or extract_ganji(nested_saju.get("year_pillar"))
            month_pillar = month_pillar or extract_ganji(nested_saju.get("month_pillar"))
            day_pillar = day_pillar or extract_ganji(nested_saju.get("day_pillar"))
            hour_pillar = hour_pillar or extract_ganji(nested_saju.get("hour_pillar"))
        
        # 경로 3: input_json 직접
        year_pillar = year_pillar or input_json.get("year_pillar", "")
        month_pillar = month_pillar or input_json.get("month_pillar", "")
        day_pillar = day_pillar or input_json.get("day_pillar", "")
        hour_pillar = hour_pillar or input_json.get("hour_pillar", "")
        
        # 경로 4: saju_result.year/month/day/hour (dict 구조)
        if not year_pillar:
            year_data = _ensure_dict(saju_result.get("year") or {})
            month_data = _ensure_dict(saju_result.get("month") or {})
            day_data = _ensure_dict(saju_result.get("day") or {})
            hour_data = _ensure_dict(saju_result.get("hour") or {})
            year_pillar = year_pillar or extract_ganji(year_data)
            month_pillar = month_pillar or extract_ganji(month_data)
            day_pillar = day_pillar or extract_ganji(day_data)
            hour_pillar = hour_pillar or extract_ganji(hour_data)
        
        logger.info(f"[Worker] 🔍 추출된 4주: 년={year_pillar} 월={month_pillar} 일={day_pillar} 시={hour_pillar}")
        
        day_master = saju_result.get("day_master", "") or (day_pillar[0] if day_pillar else "")
        day_master_element = saju_result.get("day_master_element", "")
        day_master_description = saju_result.get("day_master_description", "")
        # 🔥 P0 FIX: birth_info도 안전 변환
        birth_info = _ensure_dict(saju_result.get("birth_info") or input_json.get("birth_info") or {})
        
        # 대운 계산
        gender = _normalize_gender(input_json.get("gender") or birth_info.get("gender") or saju_result.get("gender", ""))
        age = _calc_age(birth_info)
        year_stem = year_pillar[:1] if year_pillar else ""
        
        direction = ""
        daeun_list = []
        current_daeun = None
        
        # 🔥🔥🔥 P0 핵심: 대운 계산 예외 처리 추가
        if gender and year_stem and month_pillar and age:
            try:
                is_yang_year = _year_stem_is_yang(year_stem)
                is_male = (gender == "male")
                direction = "forward" if ((is_male and is_yang_year) or (not is_male and not is_yang_year)) else "backward"
                daeun_list = calc_daeun_pillars(month_pillar, direction, count=10)
                if daeun_list:
                    start_age = int(saju_result.get('daeun_start_age') or 3)
                    idx = (age - start_age) // 10
                    if 0 <= idx < len(daeun_list):
                        current_daeun = daeun_list[idx]
            except Exception as e:
                # 대운 계산 실패해도 보고서 생성은 계속 진행
                logger.warning(f"[ReportWorker] 대운 계산 실패: {e}")
                direction = ""
                daeun_list = []
                current_daeun = None

        # ✅ P0 FIX: NameError 방지 및 saju_data 구성
        daeun_direction = direction or ""
        saju_data = {
            "year_pillar": year_pillar,
            "month_pillar": month_pillar,
            "day_pillar": day_pillar,
            "hour_pillar": hour_pillar,
            "day_master": day_master,
            "day_master_element": day_master_element,
            "day_master_description": day_master_description,
            "birth_info": birth_info,
            "saju_result": saju_result,
            "gender": gender,
            "age": age,
            "daeun_direction": daeun_direction,
            "daeun_list": daeun_list,
            "current_daeun": current_daeun,
            "target_year": target_year,
        }
        
        # ✅ P0: saju_summary(정답지) 주입
        try:
            from app.services.saju_analyzer import get_saju_summary
            saju_summary = get_saju_summary(saju_data)
            saju_data["saju_summary"] = saju_summary
            saju_data["ten_gods_present"] = saju_summary.get("ten_gods_present", [])
            saju_data["has_wealth_star"] = saju_summary.get("has_wealth_star", False)
            saju_data["elements_present"] = saju_summary.get("elements_present", [])
        except Exception as e:
            logger.warning(f"[Worker] saju_summary 생성 실패: {e}")
            
        return saju_data

    def _select_rulecards_for_section(self, all_cards, section_id, feature_tags, survey_data, saju_data, used_ids):
        """RuleCardScorer를 사용하여 설문 기반 카드 선택"""
        try:
            from app.services.rulecard_scorer import rulecard_scorer
            section_cards = rulecard_scorer.score_cards_for_section(
                all_cards=all_cards, section_id=section_id, feature_tags=feature_tags,
                survey_data=survey_data, existing_topics=set(), saju_data=saju_data
            )
            
            selected_cards = []
            for scored_card in section_cards.cards:
                card_dict = {
                    "id": scored_card.card_id, "topic": scored_card.topic, "subtopic": scored_card.subtopic,
                    "score": scored_card.final_score, "matched_tags": scored_card.matched_tags,
                    "score_trace": scored_card.score_trace.to_dict(),
                }
                for orig in all_cards:
                    if orig.get("id") == scored_card.card_id:
                        card_dict.update({k: orig.get(k) for k in ["trigger", "mechanism", "interpretation", "action", "cautions", "tags"]})
                        break
                selected_cards.append(card_dict)
            return selected_cards, {**section_cards.match_summary, "avg_score": section_cards.avg_score}
        except Exception as e:
            logger.exception(f"RuleCardScorer 실패: {e}")
            raise RuntimeError(f"RuleCardScorer 호출 실패: {e}")

    def _check_llm_quality(self, body_markdown: str, target_year: int, saju_data: Dict, min_chars: int = 600) -> List[str]:
        """🔥 P0: LLM 결과 품질 가드레일"""
        issues = []
        text = body_markdown or ""
        
        # 1) 거절/메타 문구 탐지
        rejection_phrases = [
            "죄송하지만", "죄송합니다", "분석할 수 없", "분석이 불가", "추가 정보가 필요",
            "데이터가 부족", "정보가 부족", "확인이 필요", "제공된 정보만으로는",
            "더 많은 정보", "명확하지 않", "알 수 없습니다"
        ]
        for phrase in rejection_phrases:
            if phrase in text:
                issues.append(f"거절문구:{phrase}")
                break
        
        # 2) 연도 오류 탐지 (target_year와 다른 연도가 주요 언급되면)
        wrong_years = ["2024년", "2025년", "2023년"]
        correct_year = f"{target_year}년"
        for wy in wrong_years:
            # 단순 언급은 OK, 주요 분석 대상처럼 쓰이면 문제
            if wy in text and text.count(wy) > text.count(correct_year):
                issues.append(f"연도오류:{wy}")
                break
        
        # 3) 최소 길이 미달
        if len(text) < min_chars:
            issues.append(f"길이부족:{len(text)}<{min_chars}")
        
        # 4) saju_summary에 없는 십성 단정 언급 (옵션)
        saju_summary = saju_data.get("saju_summary", {})
        ten_gods_present = saju_summary.get("ten_gods_present", [])
        if ten_gods_present:
            # 없는 십성을 "있다"고 단정하면 문제
            all_ten_gods = ["비견", "겁재", "식신", "상관", "편재", "정재", "편관", "정관", "편인", "정인"]
            missing_gods = [g for g in all_ten_gods if g not in ten_gods_present]
            for mg in missing_gods:
                # "편재가 있어", "정관이 있는" 같은 패턴
                if f"{mg}가 있" in text or f"{mg}이 있" in text or f"{mg}을 가" in text:
                    issues.append(f"환각:{mg}")
                    break
        
        return issues

    async def _generate_section(self, section_id, section_title, saju_data, rulecards, feature_tags, target_year, question, survey_data, match_summary) -> Dict:
        """섹션 본문 생성 + 🔥 P0: 품질 가드레일"""
        MAX_RETRIES = 2
        min_chars = 600  # 최소 본문 길이
        
        for attempt in range(MAX_RETRIES):
            try:
                from app.services.report_builder import premium_report_builder
                result = await premium_report_builder.regenerate_single_section(
                    section_id=section_id, saju_data=saju_data, rulecards=rulecards,
                    feature_tags=feature_tags, target_year=target_year, user_question=question, survey_data=survey_data
                )
                
                # 🔥 P0 FIX: "ok" 또는 "success" 둘 다 지원
                if not result.get("ok") and not result.get("success"):
                    if attempt < MAX_RETRIES - 1:
                        logger.warning(f"[Worker] 섹션 {section_id} 생성 실패, 재시도 {attempt+1}/{MAX_RETRIES}")
                        continue
                    return {"ok": False, "content": {"title": section_title, "body_markdown": ""}, "guardrail_errors": [result.get("error")]}
                
                section_data = result.get("section", {})
                body_markdown = section_data.get("body_markdown", "")
                
                # 🔥 P0: 품질 가드레일 체크
                quality_issues = self._check_llm_quality(body_markdown, target_year, saju_data, min_chars)
                
                if quality_issues:
                    logger.warning(f"[Worker] 섹션 {section_id} 품질 이슈: {quality_issues}")
                    if attempt < MAX_RETRIES - 1:
                        logger.info(f"[Worker] 섹션 {section_id} 재생성 시도 {attempt+2}/{MAX_RETRIES}")
                        continue
                    # 마지막 시도에서도 실패하면 이슈와 함께 반환
                    return {
                        "ok": True,  # 저장은 하되
                        "content": {**section_data, "title": section_title, "section_id": section_id},
                        "guardrail_errors": quality_issues,
                        "quality_warning": True
                    }
                
                # 성공
                return {"ok": True, "content": {**section_data, "title": section_title, "section_id": section_id}, "guardrail_errors": []}
                
            except Exception as e:
                logger.error(f"[Worker] _generate_section 예외: {e}")
                if attempt < MAX_RETRIES - 1:
                    continue
                import traceback
                logger.error(traceback.format_exc())
                return {"ok": False, "content": {"title": section_title, "body_markdown": ""}, "guardrail_errors": [str(e)]}
        
        return {"ok": False, "content": {"title": section_title, "body_markdown": ""}, "guardrail_errors": ["MAX_RETRIES 초과"]}

    def _get_all_cards_as_dict(self, rulestore: Any) -> List[Dict]:
        if not rulestore: return []
        return [self._card_to_dict(c) for c in getattr(rulestore, 'cards', [])]

    def _card_to_dict(self, card) -> Dict:
        content = getattr(card, 'content', {}) or {}
        return {
            "id": getattr(card, 'id', ''),
            "topic": getattr(card, 'topic', ''),
            "subtopic": getattr(card, 'subtopic', '') or (getattr(card, 'meta', {}) or {}).get('subtopic', ''),
            "tags": getattr(card, 'tags', []),
            "priority": getattr(card, 'priority', 0),
            "trigger": getattr(card, 'trigger', ''),
            "mechanism": getattr(card, 'mechanism', '') or content.get('mechanism', ''),
            "interpretation": getattr(card, 'interpretation', '') or content.get('interpretation', ''),
            "action": getattr(card, 'action', '') or content.get('action', ''),
            "cautions": getattr(card, 'cautions', []) or content.get('cautions', []),
        }

    def _build_feature_tags(self, saju_data: Dict) -> List[str]:
        tags = []
        for pk in ["year_pillar", "month_pillar", "day_pillar", "hour_pillar"]:
            p = saju_data.get(pk, "")
            if p and len(p) >= 2:
                tags.extend([f"천간:{p[0]}", f"지지:{p[1]}"])
        if saju_data.get("day_master"):
            tags.append(f"일간:{saju_data['day_master']}")
        return tags

    def _build_markdown(self, result_json: Dict, saju_data: Dict) -> str:
        lines = [f"# {result_json.get('name', '고객')}님의 {result_json.get('target_year', 2026)}년 1인 사업가 전략 리포트\n"]
        survey = result_json.get('survey_data', {})
        if survey:
            lines.append("## 📋 비즈니스 프로필\n")
            for k, v in {"업종": "industry", "월매출": "revenue", "핵심 병목": "painPoint", "2026 목표": "goal"}.items():
                lines.append(f"- {k}: {survey.get(v, '-')}")
            lines.append("\n---\n")
        
        sections = result_json.get("sections", {})
        for spec in ONEMAN_SECTION_SPECS:
            sec = sections.get(spec["id"], {})
            lines.extend([f"## {spec['title']}\n", sec.get("body_markdown", "내용 없음"), "\n"])
        return "\n".join(lines)

    async def _send_completion_email(self, email, name, job_id):
        if not email: return
        try:
            from app.services.email_sender import email_sender
            job = await supabase_service.get_job(job_id)
            if job and job.get("public_token"):
                await email_sender.send_report_complete(to_email=email, name=name, report_id=job_id, access_token=job["public_token"], target_year=2026)
        except Exception as e: logger.warning(f"이메일 발송 실패: {e}")

    async def _send_failure_email(self, job, error):
        email = job.get("user_email")
        if not email: return
        try:
            from app.services.email_sender import email_sender
            # 🔥 P0 FIX: JSON 문자열 → dict 안전 변환
            input_json = _ensure_dict(job.get("input_json") or job.get("input_data") or {})
            name = input_json.get("name", "고객")
            await email_sender.send_report_failed(to_email=email, name=name, report_id=job.get("id", ""), error_message=error[:200])
        except Exception as e: logger.warning(f"실패 이메일 발송 실패: {e}")

report_worker = ReportWorker()