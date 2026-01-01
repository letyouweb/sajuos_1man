"""
Report Worker v13 - P0 Pivot: 설문 기반 RuleCardScorer 통합
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 P0 핵심 변경:
1) _select_rulecards() → RuleCardScorer.score_cards_for_section() 호출
2) survey_data가 카드 선택에 직접 반영
3) 같은 사주라도 설문에 따라 다른 카드가 선택됨
4) 섹션별 score_trace 저장
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import asyncio
import logging
import time
from datetime import date
from typing import Dict, Any, Optional, List

from app.services.supabase_service import supabase_service
from app.services.saju_engine import calc_daeun_pillars

logger = logging.getLogger(__name__)


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
        input_json = job.get("input_json") or job.get("input_data") or {}  # 🔥 P0 FIX: 호환성
        
        name = input_json.get("name", "고객")
        target_year = input_json.get("target_year", 2026)
        question = input_json.get("question", "")
        survey_data = input_json.get("survey_data") or {}
        
        await supabase_service.update_progress(job_id, 5, "running")
        
        # 🔥 P0: 사주 데이터 추출
        saju_data = self._prepare_saju_data(input_json)
        
        # 🔥🔥🔥 P0 핵심: 사주 데이터 무결성 체크 - 비어있으면 에러!
        missing_pillars = []
        for key in ["year_pillar", "month_pillar", "day_pillar"]:
            if not saju_data.get(key):
                missing_pillars.append(key)
        
        if missing_pillars:
            error_msg = f"사주 데이터 누락: {missing_pillars}. 사주 없는 사주 리포트는 상품 가치가 없습니다."
            logger.error(f"[Worker] ❌❌❌ {error_msg}")
            logger.error(f"[Worker] input_json keys: {list(input_json.keys())}")
            logger.error(f"[Worker] saju_result: {input_json.get('saju_result', {})[:200] if input_json.get('saju_result') else 'None'}")
            
            # 🔥 P0: 사주 데이터 없으면 즉시 실패 처리
            await supabase_service.fail_job(job_id, error_msg)
            return False, error_msg
        
        logger.info(f"[Worker] ✅ 사주 검증 통과: {saju_data['year_pillar']}/{saju_data['month_pillar']}/{saju_data['day_pillar']}/{saju_data.get('hour_pillar', '-')}")
        logger.info(f"[Worker] ✅ 일간: {saju_data.get('day_master', '-')} ({saju_data.get('day_master_element', '-')})")
        logger.info(f"[Worker] ✅ 생년월일시: {saju_data.get('birth_info', '-')}")
        
        # 🔥 P0: Feature Tags 생성
        feature_tags = self._build_feature_tags(saju_data)
        
        # 🔥🔥🔥 P0 핵심: RuleCardScorer로 설문 기반 카드 선택
        all_cards = self._get_all_cards_as_dict(rulestore)
        
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"🔥 [Worker] 설문 기반 RuleCard 스코어링 시작")
        logger.info(f"   survey_data: industry={survey_data.get('industry', '-')}, painPoint={survey_data.get('painPoint', '-')}, goal={survey_data.get('goal', '-')[:30] if survey_data.get('goal') else '-'}")
        logger.info(f"   feature_tags: {len(feature_tags)}개")
        logger.info(f"   전체 카드: {len(all_cards)}장")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
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
                # 🔥🔥🔥 P0 핵심: 섹션별로 RuleCardScorer 호출
                section_cards, match_summary = self._select_rulecards_for_section(
                    all_cards=all_cards,
                    section_id=section_id,
                    feature_tags=feature_tags,
                    survey_data=survey_data,
                    saju_data=saju_data  # 🔥 P0 FIX: NameError 수정
                )
                
                section_match_summaries[section_id] = match_summary
                
                # 사용된 카드 ID 수집
                for card in section_cards[:10]:
                    if card.get("id") and card["id"] not in all_used_card_ids:
                        all_used_card_ids.append(card["id"])
                
                logger.info(f"[Worker:Section:{section_id}] 카드 선택 완료: {len(section_cards)}장 | AvgScore={match_summary.get('avg_score', 0):.1f}")
                
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
                errors = section_result.get("guardrail_errors", [])
                
                body_markdown = content.get("body_markdown", "")
                # 🔥 P0-C: 빈 섹션 저장 절대 금지 - 최소 300자 보장
                if not body_markdown or len(body_markdown) < 300:
                    logger.error(f"[Worker] ⚠️ 섹션 본문 부족: {section_id} | length={len(body_markdown)}")
                    # 에러 텍스트로 채우기
                    fallback_text = f"""## {section_title}

이 섹션의 분석 결과를 생성하는 중 문제가 발생했습니다.

### 임시 안내
- 현재 사주 분석 엔진이 해당 섹션에 대한 충분한 데이터를 확보하지 못했습니다.
- 잠시 후 다시 시도해 주시거나, 고객센터로 문의해 주세요.
- 분석에 사용된 룰카드: {len(section_cards)}장

### 다음 단계
1. 페이지를 새로고침해 보세요
2. 문제가 지속되면 support@sajuos.com으로 연락해 주세요
3. 곧 정상적인 분석 결과로 업데이트됩니다

---
*이 메시지는 자동 생성되었습니다. 오류 코드: SECTION_EMPTY_{section_id}*
"""
                    content["body_markdown"] = fallback_text
                    body_markdown = fallback_text
                
                # 🔥 P0: match_summary도 content에 포함
                content["match_summary"] = match_summary
                content["used_rulecard_ids"] = [c.get("id") for c in section_cards[:10]]
                
                await supabase_service.save_section(
                    job_id=job_id,
                    section_id=section_id,
                    content_json=content
                )
                
                sections_result[section_id] = content
                
                logger.info(f"[Worker] 섹션 완료: {section_id} | {len(body_markdown)}자 | ok={ok}")
                
                if not ok:
                    failed_sections.append({"section_id": section_id, "errors": errors})
                
            except Exception as e:
                logger.error(f"[Worker] 섹션 실패: {section_id} | {e}")
                failed_sections.append({
                    "section_id": section_id,
                    "errors": [f"Exception: {str(e)[:100]}"]
                })
        
        # 결과 JSON 생성
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
            # 🔥 P0: 설문 데이터 저장
            "survey_data": survey_data,
            "sections": sections_result,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "failed_sections": failed_sections if failed_sections else None,
            # 🔥 P0: 사용된 룰카드 ID (전체)
            "top_used_rulecard_ids": all_used_card_ids[:20],
            # 🔥 P0: 섹션별 match_summary
            "section_match_summaries": section_match_summaries,
        }
        
        saju_json = {
            "year_pillar": saju_data.get("year_pillar", ""),
            "month_pillar": saju_data.get("month_pillar", ""),
            "day_pillar": saju_data.get("day_pillar", ""),
            "hour_pillar": saju_data.get("hour_pillar", ""),
            "day_master": saju_data.get("day_master", ""),
            "day_master_element": saju_data.get("day_master_element", ""),
            "day_master_description": saju_data.get("day_master_description", ""),
            "birth_info": saju_data.get("birth_info", ""),
            "feature_tags": feature_tags,
            "rulecards_used": all_used_card_ids[:20],
            "survey_data": survey_data,
            "calculated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        markdown = self._build_markdown(result_json, saju_data)
        
        await supabase_service.complete_job(job_id, result_json, markdown, saju_json)
        
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"✅ [Worker] Job 완료: {job_id}")
        logger.info(f"   사주: {saju_json['year_pillar']}/{saju_json['month_pillar']}/{saju_json['day_pillar']}/{saju_json['hour_pillar']}")
        logger.info(f"   설문: {survey_data.get('industry', '-')} / {survey_data.get('painPoint', '-')}")
        logger.info(f"   사용 카드: {len(all_used_card_ids)}개")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        try:
            await self._send_completion_email(email, name, job_id)
        except Exception as e:
            logger.warning(f"[Worker] 완료 이메일 실패: {e}")
        
        return True, ""
    
    def _get_all_cards_as_dict(self, rulestore: Any) -> List[Dict]:
        """RuleStore에서 모든 카드를 dict 리스트로 추출"""
        if not rulestore:
            return []
        
        all_cards = getattr(rulestore, 'cards', [])
        if not all_cards:
            return []
        
        return [self._card_to_dict(c) for c in all_cards]
    
    def _select_rulecards_for_section(
        self,
        all_cards: List[Dict],
        section_id: str,
        feature_tags: List[str],
        survey_data: Dict,
        saju_data: Dict  # 🔥 P0 FIX: NameError 수정
    ) -> tuple[List[Dict], Dict]:
        """
        🔥🔥🔥 P0 핵심: RuleCardScorer를 사용하여 설문 기반 카드 선택
        
        Returns:
            (선택된 카드 리스트, match_summary)
        """
        try:
            from app.services.rulecard_scorer import rulecard_scorer
            
            # 🔥 P0: RuleCardScorer 호출 - survey_data 전달!
            section_cards = rulecard_scorer.score_cards_for_section(
                all_cards=all_cards,
                section_id=section_id,
                feature_tags=feature_tags,
                survey_data=survey_data,
                existing_topics=set(),
                saju_data=saju_data  # 🔥 P0: 철벽 필터링용
            )
            
            # SectionCards 객체에서 데이터 추출
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
                # 원본 카드에서 추가 필드 복사
                for orig_card in all_cards:
                    if orig_card.get("id") == scored_card.card_id:
                        card_dict["trigger"] = orig_card.get("trigger", "")
                        card_dict["mechanism"] = orig_card.get("mechanism", "")
                        card_dict["interpretation"] = orig_card.get("interpretation", "")
                        card_dict["action"] = orig_card.get("action", "")
                        card_dict["cautions"] = orig_card.get("cautions", [])
                        card_dict["tags"] = orig_card.get("tags", [])
                        break
                selected_cards.append(card_dict)
            
            match_summary = section_cards.match_summary
            match_summary["avg_score"] = section_cards.avg_score
            match_summary["total_selected"] = section_cards.total_cards
            
            return selected_cards, match_summary
            
        except Exception as e:
            logger.exception(f"[Worker] RuleCardScorer 호출 실패 - job FAILED로 처리: {e}")
            # 🔥 P0: Fallback 금지, 즉시 raise
            raise RuntimeError(f"RuleCardScorer 호출 실패: {e}") from e
    
    def _fallback_select_rulecards(self, all_cards: List[Dict], feature_tags: List[str]) -> tuple[List[Dict], Dict]:
        """Fallback: RuleCardScorer 실패 시 단순 선택"""
        if not all_cards:
            return [], {"fallback": True, "reason": "no_cards"}
        
        if not feature_tags:
            sorted_cards = sorted(all_cards, key=lambda c: c.get('priority', 0), reverse=True)
            return sorted_cards[:50], {"fallback": True, "reason": "no_feature_tags"}
        
        matched = []
        feature_set = set(t.lower() for t in feature_tags)
        
        for card in all_cards:
            card_tags = card.get('tags', [])
            card_tags_lower = set(t.lower() for t in card_tags)
            if feature_set & card_tags_lower:
                matched.append(card)
        
        if matched:
            sorted_matched = sorted(matched, key=lambda c: c.get('priority', 0), reverse=True)
            return sorted_matched[:50], {"fallback": True, "reason": "tag_match", "matched": len(matched)}
        
        sorted_cards = sorted(all_cards, key=lambda c: c.get('priority', 0), reverse=True)
        return sorted_cards[:50], {"fallback": True, "reason": "priority_only"}
    
    async def _generate_section(
        self,
        section_id: str,
        section_title: str,
        saju_data: Dict,
        rulecards: List,
        feature_tags: List,
        target_year: int,
        question: str,
        survey_data: Dict = None,
        match_summary: Dict = None
    ) -> Dict[str, Any]:
        """섹션 생성 - survey_data 포함"""
        try:
            from app.services.report_builder import premium_report_builder
            
            logger.info(f"[Worker:Section:{section_id}] 생성 시작 | Cards={len(rulecards)}장 | Title={section_title}")
            
            result = await premium_report_builder.regenerate_single_section(
                section_id=section_id,
                saju_data=saju_data,
                rulecards=rulecards,
                feature_tags=feature_tags,
                target_year=target_year,
                user_question=question,
                survey_data=survey_data  # 🔥 P0: survey_data 전달
            )
            
            if not result.get("success"):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"[Worker:Section:{section_id}] 생성 실패: {error_msg}")
                return {
                    "ok": False,
                    "content": {"title": section_title, "body_markdown": "", "error": error_msg},
                    "guardrail_errors": [error_msg]
                }
            
            section_data = result.get("section", {})
            body_markdown = section_data.get("body_markdown", "")
            
            if body_markdown:
                logger.info(f"[Worker:Section:{section_id}] ✅ body_markdown={len(body_markdown)}자")
            else:
                logger.warning(f"[Worker:Section:{section_id}] ⚠️ body_markdown 비어있음!")
            
            content = {
                "title": section_title,  # 🔥 P0: 1인 자영업자용 타이틀
                "section_id": section_id,
                "body_markdown": body_markdown,
                "confidence": section_data.get("confidence", "MEDIUM"),
                "diagnosis": section_data.get("diagnosis"),
                "hypotheses": section_data.get("hypotheses"),
                "strategy_options": section_data.get("strategy_options"),
                "recommended_strategy": section_data.get("recommended_strategy"),
                "kpis": section_data.get("kpis"),
                "risks": section_data.get("risks"),
                "annual_theme": section_data.get("annual_theme"),
                "monthly_plans": section_data.get("monthly_plans"),
                "quarterly_milestones": section_data.get("quarterly_milestones"),
                "peak_months": section_data.get("peak_months"),
                "risk_months": section_data.get("risk_months"),
                "mission_statement": section_data.get("mission_statement"),
                "phase_1_offer": section_data.get("phase_1_offer"),
                "phase_2_funnel": section_data.get("phase_2_funnel"),
                "phase_3_content": section_data.get("phase_3_content"),
                "phase_4_automation": section_data.get("phase_4_automation"),
                "milestones": section_data.get("milestones"),
                "risk_scenarios": section_data.get("risk_scenarios"),
            }
            
            return {
                "ok": bool(body_markdown),
                "content": content,
                "guardrail_errors": [] if body_markdown else ["EMPTY_BODY_MARKDOWN"]
            }
            
        except Exception as e:
            logger.error(f"[Worker:Section:{section_id}] 예외: {e}")
            return {
                "ok": False,
                "content": {"title": section_title, "body_markdown": "", "error": str(e)[:200]},
                "guardrail_errors": [f"Exception: {str(e)[:100]}"]
            }
    
    def _prepare_saju_data(self, input_json: Dict) -> Dict:
        """사주 데이터 추출"""
        saju_result = input_json.get("saju_result") or {}
        
        def extract_ganji(pillar_data):
            if not pillar_data:
                return ""
            if isinstance(pillar_data, dict):
                return pillar_data.get("ganji", "")
            if isinstance(pillar_data, str):
                return pillar_data
            return ""
        
        year_pillar = extract_ganji(saju_result.get("year_pillar"))
        month_pillar = extract_ganji(saju_result.get("month_pillar"))
        day_pillar = extract_ganji(saju_result.get("day_pillar"))
        hour_pillar = extract_ganji(saju_result.get("hour_pillar"))
        
        saju_nested = saju_result.get("saju") or {}
        if not year_pillar and saju_nested:
            year_pillar = extract_ganji(saju_nested.get("year_pillar"))
        if not month_pillar and saju_nested:
            month_pillar = extract_ganji(saju_nested.get("month_pillar"))
        if not day_pillar and saju_nested:
            day_pillar = extract_ganji(saju_nested.get("day_pillar"))
        if not hour_pillar and saju_nested:
            hour_pillar = extract_ganji(saju_nested.get("hour_pillar"))
        
        if not year_pillar:
            year_pillar = input_json.get("year_pillar", "")
        if not month_pillar:
            month_pillar = input_json.get("month_pillar", "")
        if not day_pillar:
            day_pillar = input_json.get("day_pillar", "")
        if not hour_pillar:
            hour_pillar = input_json.get("hour_pillar", "")
        
        day_master = saju_result.get("day_master", "")
        if not day_master and saju_nested:
            day_master = saju_nested.get("day_master", "")
        
        day_master_element = saju_result.get("day_master_element", "")
        day_master_description = saju_result.get("day_master_description", "")
        birth_info = saju_result.get("birth_info", {})
        if isinstance(birth_info, str):
            birth_info = {}
        
        # 🔥 P0: 대운 계산 (서버 확정값)
        survey_data = input_json.get("survey_data") or {}
        gender = _normalize_gender(
            input_json.get("gender") or 
            birth_info.get("gender") or 
            survey_data.get("gender") or 
            saju_result.get("gender", "")
        )
        
        age = _calc_age(birth_info)
        if not age and birth_info.get("year"):
            try:
                age = date.today().year - int(birth_info.get("year"))
            except:
                age = 0
        
        year_stem = year_pillar[:1] if year_pillar else ""
        
        direction = None
        daeun_list = []
        current_daeun = None
        
        if gender and year_stem and month_pillar and age:
            is_yang_year = _year_stem_is_yang(year_stem)
            is_male = (gender == "male")
            # 양남음녀=순행, 음남양녀=역행
            direction = "forward" if ((is_male and is_yang_year) or ((not is_male) and (not is_yang_year))) else "backward"
            daeun_list = calc_daeun_pillars(month_pillar, direction, count=10)
            if daeun_list:
                start_age = 3  # 대운 시작 나이
                idx = (age - start_age) // 10
                if 0 <= idx < len(daeun_list):
                    current_daeun = daeun_list[idx]
            
            logger.info(f"[Worker] 🔥 대운 계산: gender={gender} | age={age} | direction={direction} | current_daeun={current_daeun}")
        else:
            logger.warning(f"[Worker] ⚠️ 대운 계산 불가: gender={gender} | year_stem={year_stem} | month_pillar={month_pillar} | age={age}")
        
        return {
            "year_pillar": year_pillar,
            "month_pillar": month_pillar,
            "day_pillar": day_pillar,
            "hour_pillar": hour_pillar,
            "day_master": day_master,
            "day_master_element": day_master_element,
            "day_master_description": day_master_description,
            "birth_info": birth_info,
            "saju_result": saju_result,
            # 🔥 P0: 대운 정보 추가
            "gender": gender,
            "age": age,
            "daeun_direction": direction,
            "daeun_list": daeun_list,
            "current_daeun": current_daeun,
        }
    
    def _build_feature_tags(self, saju_data: Dict) -> List[str]:
        """Feature Tags 생성"""
        tags = []
        
        for pillar_key in ["year_pillar", "month_pillar", "day_pillar", "hour_pillar"]:
            pillar = saju_data.get(pillar_key, "")
            if pillar and len(pillar) >= 2:
                tags.append(f"천간:{pillar[0]}")
                tags.append(f"지지:{pillar[1]}")
        
        if saju_data.get("day_master"):
            tags.append(f"일간:{saju_data['day_master']}")
        
        return tags
    
    def _card_to_dict(self, card) -> Dict:
        """RuleCard를 dict로 변환 (content dict fallback 포함)"""
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
    
    def _build_markdown(self, result_json: Dict, saju_data: Dict) -> str:
        """마크다운 생성"""
        lines = []
        
        name = result_json.get('name', '고객')
        target_year = result_json.get('target_year', 2026)
        survey_data = result_json.get('survey_data', {})
        
        lines.append(f"# {name}님의 {target_year}년 1인 사업가 전략 리포트\n")
        
        # 설문 요약
        if survey_data:
            lines.append("## 📋 비즈니스 프로필\n")
            lines.append(f"- 업종: {survey_data.get('industry', '-')}")
            lines.append(f"- 월매출: {survey_data.get('revenue', '-')}")
            lines.append(f"- 핵심 병목: {survey_data.get('painPoint', '-')}")
            lines.append(f"- 2026 목표: {survey_data.get('goal', '-')}")
            lines.append(f"- 주당 시간: {survey_data.get('time', '-')}")
            lines.append("\n---\n")
        
        # 사주 요약
        lines.append("## 📜 사주 원국\n")
        lines.append(f"- 년주: {saju_data.get('year_pillar', '-')}")
        lines.append(f"- 월주: {saju_data.get('month_pillar', '-')}")
        lines.append(f"- 일주: {saju_data.get('day_pillar', '-')}")
        lines.append(f"- 시주: {saju_data.get('hour_pillar', '-') or '미입력'}")
        lines.append(f"- 일간: {saju_data.get('day_master', '-')} ({saju_data.get('day_master_element', '')})")
        lines.append("\n---\n")
        
        # 섹션별 내용
        sections = result_json.get("sections", {})
        for spec in ONEMAN_SECTION_SPECS:
            section = sections.get(spec["id"], {})
            lines.append(f"## {spec['title']}\n")
            body = section.get("body_markdown", "") or section.get("summary", "내용 없음")
            lines.append(body)
            lines.append("\n")
        
        return "\n".join(lines)
    
    async def _send_completion_email(self, email: str, name: str, job_id: str):
        """완료 이메일"""
        if not email:
            return
        
        try:
            from app.services.email_sender import email_sender
            
            job = await supabase_service.get_job(job_id)
            if not job:
                return
            
            access_token = job.get("public_token", "")
            if not access_token:
                logger.error(f"[Worker] ⚠️ public_token이 NULL! job_id={job_id}")
                return
            
            await email_sender.send_report_complete(
                to_email=email,
                name=name,
                report_id=job_id,
                access_token=access_token,
                target_year=2026
            )
            logger.info(f"[Worker] ✅ 완료 이메일 발송: {email}")
        except Exception as e:
            logger.warning(f"이메일 발송 실패: {e}")
    
    async def _send_failure_email(self, job: Dict, error: str):
        """실패 이메일"""
        email = job.get("user_email", "")
        if not email:
            return
        
        try:
            from app.services.email_sender import email_sender
            input_json = job.get("input_json") or job.get("input_data") or {}  # 🔥 P0 FIX: 호환성
            name = input_json.get("name", "고객")
            job_id = job.get("id", "")
            
            await email_sender.send_report_failed(
                to_email=email,
                name=name,
                report_id=job_id,
                error_message=error[:200]
            )
            logger.info(f"[Worker] 실패 이메일 발송: {email}")
        except Exception as e:
            logger.warning(f"실패 이메일 발송 실패: {e}")


report_worker = ReportWorker()
