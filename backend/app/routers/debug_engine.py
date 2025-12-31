"""
SajuOS Debug Engine Router - P0
- 매칭 디버그 엔드포인트
- 콘텐츠 주입 검증용
- score_trace 포함
"""
from fastapi import APIRouter, Query, HTTPException, Request
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/debug", tags=["Debug Engine"])


@router.get("/engine-survey")
async def debug_engine_survey(
    raw: Request,
    birth: str = Query(..., description="생년월일 YYYY-MM-DD"),
    time: Optional[str] = Query(None, description="생시 HH:MM"),
    target_year: int = Query(2026, description="대상 년도"),
    industry: Optional[str] = Query(None, description="업종"),
    painPoint: Optional[str] = Query(None, description="병목 (lead/conversion/operations/funding/retention)"),
    businessGoal: Optional[str] = Query(None, description="목표 (growth/stability/expansion/exit)")
):
    """
    P0 디버그: 매칭 엔진 + 설문 기반 결과 검증
    
    Returns:
        pillars, features, match_summary, score_traces, survey_data
    """
    from datetime import datetime
    from app.services.calc_module import calc_module
    from app.services.feature_tags import build_feature_tags, get_matching_tokens
    from app.services.rulecard_scorer import RuleCardScorer
    from app.services.report_builder import PREMIUM_SECTIONS
    
    # 1. birth 파싱
    try:
        birth_date = datetime.strptime(birth, "%Y-%m-%d")
        year = birth_date.year
        month = birth_date.month
        day = birth_date.day
    except ValueError:
        raise HTTPException(400, "Invalid birth format. Use YYYY-MM-DD")
    
    # 2. time 파싱
    hour = None
    minute = 0
    if time:
        try:
            parts = time.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        except:
            pass
    
    # 3. 사주 계산
    try:
        pillars = await calc_module.calculate_pillars(year, month, day, hour, minute)
    except Exception as e:
        raise HTTPException(500, f"Pillars calculation failed: {e}")
    
    pillars_dict = pillars.to_dict()
    pillars_str = f"{pillars.year.ganji} {pillars.month.ganji} {pillars.day.ganji}"
    if pillars.hour:
        pillars_str += f" {pillars.hour.ganji}"
    
    # 4. survey_data 구성
    survey_data = {}
    if industry:
        survey_data["industry"] = industry
    if painPoint:
        survey_data["painPoint"] = painPoint
    if businessGoal:
        survey_data["businessGoal"] = businessGoal
    
    # 5. feature_tags 생성 (단일 소스)
    features = build_feature_tags(pillars_dict, survey_data if survey_data else None)
    feature_tokens = get_matching_tokens(features)
    
    # 6. RuleCards 매칭
    rulestore = getattr(raw.app.state, "rulestore", None)
    if not rulestore:
        raise HTTPException(500, "RuleCards not loaded")
    
    # 7. 섹션별 매칭 + score_trace
    match_summary = {}
    score_traces = {}
    
    scorer = RuleCardScorer(rulestore.cards)
    
    for section_id in PREMIUM_SECTIONS.keys():
        top_k, summary = scorer.get_top_k(features, survey_data if survey_data else None, section_id, k=5)
        
        match_summary[section_id] = {
            "count": summary["passed_trigger"],
            "selected": summary["selected"],
            "top_ids": summary["top_ids"]
        }
        
        if summary["score_traces"]:
            score_traces[section_id] = summary["score_traces"]
    
    # 8. 콘텐츠 주입 검증
    content_check = {
        "total_cards": len(rulestore.cards),
        "cards_with_interpretation": sum(1 for c in rulestore.cards if c.interpretation),
        "cards_with_mechanism": sum(1 for c in rulestore.cards if c.mechanism),
        "cards_with_action": sum(1 for c in rulestore.cards if c.action),
    }
    
    return {
        "pillars": pillars_str,
        "features": {
            "day_master": features.get("day_master"),
            "month_branch": features.get("month_branch"),
            "tokens_count": len(feature_tokens),
            "tokens_sample": feature_tokens[:20],
            "elements_count": features.get("elements_count"),
            "ten_gods_count": features.get("ten_gods_count"),
            "survey_tags": features.get("survey_tags")
        },
        "match_summary": match_summary,
        "score_traces": score_traces,
        "survey_data": survey_data,
        "content_check": content_check,
        "rulestore_source": getattr(rulestore, "source", "unknown")
    }


@router.get("/match")
async def debug_match(
    raw: Request,
    birth: str = Query(..., description="생년월일 YYYY-MM-DD"),
    time: Optional[str] = Query(None, description="생시 HH:MM"),
    target_year: int = Query(2026, description="대상 년도")
):
    """간단한 매칭 디버그"""
    return await debug_engine_survey(
        raw=raw,
        birth=birth,
        time=time,
        target_year=target_year,
        industry=None,
        painPoint=None,
        businessGoal=None
    )


@router.get("/rulecard/{card_id}")
async def get_rulecard(card_id: str, raw: Request):
    """특정 RuleCard 상세 조회"""
    rulestore = getattr(raw.app.state, "rulestore", None)
    if not rulestore:
        raise HTTPException(500, "RuleCards not loaded")
    
    for card in rulestore.cards:
        if card.id == card_id:
            return {
                "id": card.id,
                "topic": card.topic,
                "priority": card.priority,
                "tags": card.tags,
                "trigger": card.trigger,
                "mechanism": card.mechanism or (card.content or {}).get("mechanism", ""),
                "interpretation": card.interpretation or (card.content or {}).get("interpretation", ""),
                "action": card.action or (card.content or {}).get("action", ""),
                "cautions": card.cautions or (card.content or {}).get("cautions", []),
            }
    
    raise HTTPException(404, f"RuleCard not found: {card_id}")


@router.get("/stats")
async def get_stats(raw: Request):
    """RuleCards 통계"""
    rulestore = getattr(raw.app.state, "rulestore", None)
    if not rulestore:
        raise HTTPException(500, "RuleCards not loaded")
    
    topic_counts = {}
    for card in rulestore.cards:
        topic_counts[card.topic] = topic_counts.get(card.topic, 0) + 1
    
    return {
        "total_cards": len(rulestore.cards),
        "source": getattr(rulestore, "source", "unknown"),
        "topics": topic_counts,
        "idf_tokens": len(rulestore.idf),
        "content_stats": {
            "with_interpretation": sum(1 for c in rulestore.cards if c.interpretation),
            "with_mechanism": sum(1 for c in rulestore.cards if c.mechanism),
            "with_action": sum(1 for c in rulestore.cards if c.action),
        }
    }
