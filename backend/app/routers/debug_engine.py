"""
SajuOS Debug Engine Router
- 매칭 디버그 엔드포인트
- 콘텐츠 주입 검증용
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/debug", tags=["Debug Engine"])


@router.get("/match")
async def debug_match(
    birth: str = Query(..., description="생년월일 YYYY-MM-DD"),
    time: Optional[str] = Query(None, description="생시 HH:MM"),
    target_year: int = Query(2026, description="대상 년도")
):
    """
    매칭 디버그 엔드포인트
    - pillars (년/월/일/시)
    - feature_tags_count + 샘플
    - 섹션별 top_cards
    """
    from datetime import datetime
    
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
    from app.services.calc_module import calc_module
    try:
        pillars = await calc_module.calculate_pillars(year, month, day, hour, minute)
    except Exception as e:
        raise HTTPException(500, f"Pillars calculation failed: {e}")
    
    pillars_dict = {
        "year": {"ganji": pillars.year.ganji, "gan": pillars.year.gan, "ji": pillars.year.ji},
        "month": {"ganji": pillars.month.ganji, "gan": pillars.month.gan, "ji": pillars.month.ji},
        "day": {"ganji": pillars.day.ganji, "gan": pillars.day.gan, "ji": pillars.day.ji},
        "hour": {"ganji": pillars.hour.ganji, "gan": pillars.hour.gan, "ji": pillars.hour.ji} if pillars.hour else None
    }
    
    # 4. feature_tags 생성
    from app.services.feature_tags_no_time import build_feature_tags_no_time_from_pillars
    try:
        feature_tags = build_feature_tags_no_time_from_pillars(pillars.to_dict())
    except Exception as e:
        feature_tags = []
        logger.warning(f"Feature tags error: {e}")
    
    # 5. RuleCards 매칭
    from fastapi import Request
    from app.main import app
    
    rulestore = app.state.rulestore
    if not rulestore:
        raise HTTPException(500, "RuleCards not loaded")
    
    # 섹션별 매칭
    from app.services.report_builder import PREMIUM_SECTIONS
    
    section_results = {}
    for section_id, spec in PREMIUM_SECTIONS.items():
        matched = []
        
        for card in rulestore.cards:
            # 태그 매칭
            card_tags = set(card.tags)
            feature_set = set(feature_tags)
            matched_tags = card_tags & feature_set
            
            if matched_tags:
                interp = card.interpretation or card.content.get("interpretation", "") or ""
                matched.append({
                    "id": card.id,
                    "score": len(matched_tags),
                    "matched_tags": list(matched_tags)[:5],
                    "interpretation_preview": interp[:100] if interp else "[EMPTY]"
                })
        
        # 상위 5개만
        matched.sort(key=lambda x: x["score"], reverse=True)
        section_results[section_id] = matched[:5]
    
    # 6. 콘텐츠 주입 검증
    content_check = {
        "total_cards": len(rulestore.cards),
        "cards_with_interpretation": sum(1 for c in rulestore.cards if c.interpretation),
        "cards_with_mechanism": sum(1 for c in rulestore.cards if c.mechanism),
        "cards_with_action": sum(1 for c in rulestore.cards if c.action),
    }
    
    return {
        "pillars": pillars_dict,
        "feature_tags": {
            "count": len(feature_tags),
            "sample": feature_tags[:30]
        },
        "sections": section_results,
        "content_check": content_check,
        "rulestore_source": getattr(rulestore, "source", "unknown")
    }


@router.get("/rulecard/{card_id}")
async def get_rulecard(card_id: str):
    """특정 RuleCard 상세 조회"""
    from app.main import app
    
    rulestore = app.state.rulestore
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
                "mechanism": card.mechanism or card.content.get("mechanism", ""),
                "interpretation": card.interpretation or card.content.get("interpretation", ""),
                "action": card.action or card.content.get("action", ""),
                "cautions": card.cautions or card.content.get("cautions", []),
            }
    
    raise HTTPException(404, f"RuleCard not found: {card_id}")


@router.get("/stats")
async def get_stats():
    """RuleCards 통계"""
    from app.main import app
    
    rulestore = app.state.rulestore
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
