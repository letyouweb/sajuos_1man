# -*- coding: utf-8 -*-
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Debug Router v3 - P0 Pivot: 설문 기반 엔진 검증
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 P0 핵심 추가:
- /debug/engine-survey: 같은 사주 + 다른 설문 → 다른 결과 증명
- survey_data, match_summary, score_trace 반환
- top_used_rulecard_ids 반환
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/debug", tags=["debug"])


class EngineDebugResponse(BaseModel):
    """엔진 디버그 응답"""
    pillars: dict
    derived: dict
    match_summary: dict
    raw_json: dict
    rulecard_status: dict
    validation: dict


class EngineSurveyDebugResponse(BaseModel):
    """🔥 P0: 설문 기반 엔진 디버그 응답"""
    # 입력
    birth_info: dict
    survey_data: dict
    
    # 사주 계산 결과
    pillars: dict
    
    # 파생 특징
    derived: dict
    
    # 🔥 P0 핵심: 설문 기반 매칭 결과
    match_summary: Dict[str, Any]
    
    # 🔥 P0 핵심: 사용된 룰카드 ID 목록
    top_used_rulecard_ids: List[str]
    
    # 🔥 P0 핵심: 스코어 트레이스 (점수 breakdown)
    score_traces: List[dict]
    
    # 검증
    validation: dict


@router.get("/engine-survey", response_model=EngineSurveyDebugResponse)
async def debug_engine_with_survey(
    request: Request,
    birth_year: int = Query(..., description="출생 연도", ge=1900, le=2100),
    birth_month: int = Query(..., description="출생 월", ge=1, le=12),
    birth_day: int = Query(..., description="출생 일", ge=1, le=31),
    birth_hour: Optional[int] = Query(None, description="출생 시 (0-23)", ge=0, le=23),
    target_year: int = Query(2026, description="분석 연도"),
    # 🔥 P0: 설문 5문항
    industry: str = Query("", description="업종 (예: IT/SaaS, 커머스, 컨설팅)"),
    revenue: str = Query("under_1000", description="월매출 범위"),
    painPoint: str = Query("lead", description="핵심 병목 (lead/conversion/operations/funding/mental/direction)"),
    goal: str = Query("", description="2026 목표 (예: 월매출 5000만원)"),
    time: str = Query("30_50", description="주당 투입 시간")
):
    """
    🔥 **P0: 설문 기반 엔진 디버그**
    
    **목적**: 같은 사주라도 설문(industry/painPoint/goal)에 따라 
    선택되는 룰카드가 달라지는 것을 증명
    
    **테스트 방법**:
    ```bash
    # Case 1: 카페 사업자
    GET /api/v1/debug/engine-survey?birth_year=1988&birth_month=5&birth_day=15&industry=카페&painPoint=lead&goal=월매출500만원
    
    # Case 2: 개발자 (같은 생년월일)
    GET /api/v1/debug/engine-survey?birth_year=1988&birth_month=5&birth_day=15&industry=개발&painPoint=operations&goal=팀확장
    
    # → top_used_rulecard_ids가 달라야 함!
    ```
    
    **반환**:
    - `survey_data`: 입력된 설문 데이터
    - `match_summary`: 섹션별 매칭 결과 + 설문 가중치 적용 여부
    - `top_used_rulecard_ids`: 선택된 룰카드 ID Top 20
    - `score_traces`: Top 10 카드의 점수 breakdown
    """
    try:
        from app.services.calc_module import calc_module
        from app.services.derive_module import derive_module
        from app.services.rulecard_scorer import rulecard_scorer, get_survey_tag_weights
        
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"🔥 [Debug:Survey] 설문 기반 엔진 테스트")
        logger.info(f"   생년월일: {birth_year}-{birth_month:02d}-{birth_day:02d} {birth_hour}시")
        logger.info(f"   설문: industry={industry}, painPoint={painPoint}, goal={goal}")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        # 설문 데이터 구성
        survey_data = {
            "industry": industry,
            "revenue": revenue,
            "painPoint": painPoint,
            "goal": goal,
            "time": time
        }
        
        # ━━━ STEP 1: Calc 모듈 ━━━
        pillars = await calc_module.calculate_pillars(
            birth_year=birth_year,
            birth_month=birth_month,
            birth_day=birth_day,
            birth_hour=birth_hour,
            birth_minute=0
        )
        pillars_dict = pillars.to_dict()
        
        year_ganji = pillars.year.ganji if pillars.year else ""
        month_ganji = pillars.month.ganji if pillars.month else ""
        day_ganji = pillars.day.ganji if pillars.day else ""
        hour_ganji = pillars.hour.ganji if pillars.hour else ""
        
        logger.info(f"✅ 사주: {year_ganji} {month_ganji} {day_ganji} {hour_ganji}")
        
        # ━━━ STEP 2: Derive 모듈 ━━━
        features = derive_module.derive_features(pillars, target_year=target_year)
        
        # FeatureTags 생성
        feature_tags = []
        for pillar in [year_ganji, month_ganji, day_ganji, hour_ganji]:
            if pillar and len(pillar) >= 2:
                feature_tags.append(f"천간:{pillar[0]}")
                feature_tags.append(f"지지:{pillar[1]}")
        if features.day_master:
            feature_tags.append(f"일간:{features.day_master}")
        
        # ━━━ STEP 3: 룰카드 로드 (RuleStore에서) ━━━
        rulestore = getattr(request.app.state, "rulestore", None)
        all_cards = []
        
        if rulestore and hasattr(rulestore, 'cards'):
            all_cards = [
                {
                    "id": getattr(card, 'id', ''),
                    "topic": getattr(card, 'topic', ''),
                    "subtopic": getattr(card, 'subtopic', ''),
                    "tags": getattr(card, 'tags', []),
                    "priority": getattr(card, 'priority', 0),
                }
                for card in rulestore.cards
            ]
        
        logger.info(f"✅ 룰카드 로드: {len(all_cards)}장")
        
        if len(all_cards) == 0:
            # 룰카드 로드 실패 시에도 응답 반환 (빈 결과)
            return EngineSurveyDebugResponse(
                birth_info={
                    "year": birth_year,
                    "month": birth_month,
                    "day": birth_day,
                    "hour": birth_hour,
                    "target_year": target_year
                },
                survey_data=survey_data,
                pillars=pillars_dict,
                derived={
                    "day_master": features.day_master,
                    "day_master_element": features.day_master_element,
                    "structure": features.structure,
                    "feature_tags": feature_tags
                },
                match_summary={"error": "룰카드 로드 실패", "total_cards": 0},
                top_used_rulecard_ids=[],
                score_traces=[],
                validation={
                    "pillars_valid": bool(year_ganji and month_ganji and day_ganji),
                    "rulecard_loaded": False,
                    "survey_applied": False,
                    "all_passed": False
                }
            )
        
        # ━━━ STEP 4: 🔥 P0 설문 기반 스코어링 ━━━
        section_results = rulecard_scorer.score_all_sections(
            all_cards=all_cards,
            feature_tags=feature_tags,
            survey_data=survey_data,
            section_ids=["exec", "money", "business"]  # 주요 3섹션만 테스트
        )
        
        # match_summary 구성
        match_summary = {
            "survey_applied": bool(industry or painPoint or goal),
            "survey_tag_weights": get_survey_tag_weights(survey_data),
            "sections": {}
        }
        
        all_used_ids = []
        all_traces = []
        
        for section_id, section_cards in section_results.items():
            match_summary["sections"][section_id] = section_cards.match_summary
            
            # Top 카드 ID 수집
            for card in section_cards.cards[:10]:
                if card.card_id not in all_used_ids:
                    all_used_ids.append(card.card_id)
            
            # Top 5 카드의 score_trace 수집
            for card in section_cards.cards[:5]:
                all_traces.append({
                    "section": section_id,
                    "card_id": card.card_id,
                    "topic": card.topic,
                    "final_score": round(card.final_score, 2),
                    "score_trace": card.score_trace.to_dict()
                })
        
        # Top 20 카드 ID
        top_used_rulecard_ids = all_used_ids[:20]
        
        # Top 10 스코어 트레이스
        score_traces = sorted(all_traces, key=lambda x: x["final_score"], reverse=True)[:10]
        
        # ━━━ STEP 5: 검증 ━━━
        pillars_valid = bool(year_ganji and month_ganji and day_ganji)
        survey_applied = bool(industry or painPoint or goal)
        
        # 설문이 적용되었는지 확인: industry_match, pain_match, goal_match 중 하나라도 > 0
        survey_score_applied = any(
            trace.get("score_trace", {}).get("industry_match", 0) > 0 or
            trace.get("score_trace", {}).get("pain_match", 0) > 0 or
            trace.get("score_trace", {}).get("goal_match", 0) > 0
            for trace in score_traces
        )
        
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"✅ 설문 기반 엔진 테스트 완료")
        logger.info(f"   사주 유효: {pillars_valid}")
        logger.info(f"   설문 적용: {survey_applied} (스코어 반영: {survey_score_applied})")
        logger.info(f"   선택 카드: {len(top_used_rulecard_ids)}개")
        logger.info(f"   Top 3 IDs: {top_used_rulecard_ids[:3]}")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        return EngineSurveyDebugResponse(
            birth_info={
                "year": birth_year,
                "month": birth_month,
                "day": birth_day,
                "hour": birth_hour,
                "target_year": target_year
            },
            survey_data=survey_data,
            pillars=pillars_dict,
            derived={
                "day_master": features.day_master,
                "day_master_element": features.day_master_element,
                "structure": features.structure,
                "is_strong_self": features.is_strong_self,
                "feature_tags": feature_tags
            },
            match_summary=match_summary,
            top_used_rulecard_ids=top_used_rulecard_ids,
            score_traces=score_traces,
            validation={
                "pillars_valid": pillars_valid,
                "rulecard_loaded": len(all_cards) > 0,
                "survey_applied": survey_applied,
                "survey_score_reflected": survey_score_applied,
                "all_passed": pillars_valid and len(all_cards) > 0
            }
        )
    
    except Exception as e:
        logger.error(f"❌ [Debug:Survey] 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "type": type(e).__name__}
        )


@router.get("/engine", response_model=EngineDebugResponse)
async def debug_engine(
    birth_year: int = Query(..., description="출생 연도", ge=1900, le=2100),
    birth_month: int = Query(..., description="출생 월", ge=1, le=12),
    birth_day: int = Query(..., description="출생 일", ge=1, le=31),
    birth_hour: Optional[int] = Query(None, description="출생 시 (0-23)", ge=0, le=23),
    target_year: int = Query(2026, description="분석 연도", ge=2020, le=2100)
):
    """
    🔍 **SajuOS V1.0 하이브리드 엔진 디버그 엔드포인트**
    
    **목적**: Calc→Derive→Match 흐름이 실제로 작동하는지 증명
    """
    try:
        from app.services.calc_module import calc_module
        from app.services.derive_module import derive_module
        from app.services.match_module import match_module
        
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"🔍 [Debug] 엔진 테스트 시작")
        logger.info(f"   입력: {birth_year}-{birth_month:02d}-{birth_day:02d} {birth_hour}시")
        logger.info(f"   분석년도: {target_year}년")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        # STEP 1: Calc
        pillars = await calc_module.calculate_pillars(
            birth_year=birth_year,
            birth_month=birth_month,
            birth_day=birth_day,
            birth_hour=birth_hour,
            birth_minute=0
        )
        
        pillars_dict = pillars.to_dict()
        year_ganji = pillars.year.ganji if pillars.year else ""
        month_ganji = pillars.month.ganji if pillars.month else ""
        day_ganji = pillars.day.ganji if pillars.day else ""
        hour_ganji = pillars.hour.ganji if pillars.hour else ""
        
        logger.info(f"✅ Calc 완료: {year_ganji} {month_ganji} {day_ganji} {hour_ganji}")
        
        pillars_valid = all([
            pillars.year is not None,
            pillars.month is not None,
            pillars.day is not None,
            year_ganji and year_ganji != "?",
            month_ganji and month_ganji != "?",
            day_ganji and day_ganji != "?"
        ])
        
        # STEP 2: Derive
        features = derive_module.derive_features(pillars, target_year=target_year)
        features_dict = features.to_dict()
        
        logger.info(f"✅ Derive 완료: 일간={features.day_master}")
        
        # STEP 3: Match
        if not match_module.loaded or not match_module.store:
            backend_path = Path(__file__).parent.parent.parent
            rulecards_path = backend_path / "data" / "sajuos_master_db.jsonl"
            
            if not rulecards_path.exists():
                rulecards_path = backend_path / "data" / "rulecards.jsonl"
            if not rulecards_path.exists():
                rulecards_path = backend_path / "temp_rulecards.jsonl"
            
            if rulecards_path.exists():
                match_module.load_rulecards(str(rulecards_path))
        
        total_cards = len(match_module.store.cards) if match_module.store else 0
        by_topic = match_module.store.by_topic if match_module.store else {}
        
        if total_cards == 0:
            raise RuntimeError("룰카드 로드 실패: 0장")
        
        matches = match_module.match_all_sections(features)
        
        # Match Summary
        match_summary = {}
        total_matched_cards = 0
        
        for section_id, section_match in matches.items():
            card_count = len(section_match.cards)
            total_matched_cards += card_count
            
            top_cards_with_scores = [
                {
                    "card_id": card.card_id,
                    "score": round(card.score, 2),
                    "score_details": card.score_details
                }
                for card in section_match.cards[:5]
            ]
            
            match_summary[section_id] = {
                "count": card_count,
                "top_cards": top_cards_with_scores,
                "avg_score": round(section_match.avg_score, 2)
            }
        
        matches_valid = all([len(sm.cards) > 0 for sm in matches.values()])
        scores_valid = all([sm.avg_score > 0 for sm in matches.values()])
        
        # Raw JSON
        raw_json = match_module.generate_raw_json(features, matches)
        raw_json_compact = {
            "matched_rule_ids": raw_json["matched_rule_ids"],
            "match_scores": raw_json["match_scores"],
            "fired_triggers": {k: v[:3] for k, v in raw_json["fired_triggers"].items()},
            "total_matched": len(raw_json["matched_rule_ids"]),
            "features_summary": {
                "day_master": features.day_master,
                "day_master_element": features.day_master_element,
                "structure": features.structure,
                "dominant_ten_god": features.dominant_ten_god,
                "is_strong_self": features.is_strong_self
            }
        }
        
        validation = {
            "pillars_valid": pillars_valid,
            "pillars_year": year_ganji or "N/A",
            "pillars_month": month_ganji or "N/A",
            "pillars_day": day_ganji or "N/A",
            "pillars_hour": hour_ganji or "N/A",
            "matches_valid": matches_valid,
            "scores_valid": scores_valid,
            "total_matched_cards": total_matched_cards,
            "rulecards_loaded": total_cards,
            "all_checks_passed": all([pillars_valid, matches_valid, scores_valid, total_cards > 0, total_matched_cards > 0])
        }
        
        logger.info(f"✅ 엔진 테스트 완료: {validation['all_checks_passed']}")
        
        return EngineDebugResponse(
            pillars=pillars_dict,
            derived={
                "day_master": features.day_master,
                "day_master_element": features.day_master_element,
                "day_master_yin_yang": features.day_master_yin_yang,
                "is_strong_self": features.is_strong_self,
                "strong_elements": features.strong_elements,
                "weak_elements": features.weak_elements,
                "element_count": features.element_count,
                "dominant_ten_god": features.dominant_ten_god,
                "ten_gods_count": features.ten_gods_count,
                "ten_gods": features.ten_gods[:10],
                "structure": features.structure,
                "structure_desc": features.structure_desc,
                "timing_year": features.timing_year,
                "year_luck_element": features.year_luck_element,
                "is_favorable_year": features.is_favorable_year,
                "timing_desc": features.timing_desc
            },
            match_summary=match_summary,
            raw_json=raw_json_compact,
            rulecard_status={
                "loaded": match_module.loaded,
                "total_cards": total_cards,
                "by_topic": {k: len(v) for k, v in by_topic.items()},
                "idf_tokens": len(match_module.store.idf) if match_module.store else 0
            },
            validation=validation
        )
    
    except Exception as e:
        logger.error(f"❌ [Debug] 엔진 테스트 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": str(e), "type": type(e).__name__})


@router.get("/health")
async def health_check():
    """🏥 헬스 체크"""
    from app.services.match_module import match_module
    
    return {
        "status": "ok",
        "rulecard_loaded": match_module.loaded,
        "total_cards": len(match_module.store.cards) if match_module.store else 0,
        "modules": {
            "calc": "available",
            "derive": "available",
            "match": "loaded" if match_module.loaded else "not_loaded"
        }
    }


@router.get("/survey-form-spec")
async def get_survey_form_spec():
    """🔥 P0: 프론트엔드용 설문 폼 스펙 반환"""
    from app.services.survey_intake import SURVEY_FORM_SPEC
    return SURVEY_FORM_SPEC
