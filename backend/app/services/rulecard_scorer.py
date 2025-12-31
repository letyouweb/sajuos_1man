"""
RuleCard Scorer v4 - P0 호환성 완전 보장
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
report_worker.py가 기대하는 인터페이스 100% 준수
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import logging
import json
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 설문 가중치 매핑
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INDUSTRY_WEIGHTS = {
    "it": ["창업", "사업", "식상", "상관", "인성"],
    "saas": ["창업", "사업", "식상", "수입"],
    "커머스": ["재성", "정재", "편재", "투자", "수입"],
    "컨설팅": ["관성", "정관", "인맥", "귀인"],
    "교육": ["인성", "정인", "인맥", "식신"],
    "콘텐츠": ["식상", "상관", "식신", "창업"],
    "부동산": ["재성", "정재", "편재", "재고", "투자"],
}

PAINPOINT_WEIGHTS = {
    "lead": ["인맥", "귀인", "관성", "합작"],
    "conversion": ["재성", "정재", "식신생재", "합작"],
    "operations": ["인성", "정인", "관성"],
    "funding": ["재성", "재고", "파재", "손재", "투자"],
    "retention": ["비겁", "비견", "겁재", "인맥", "합"],
    "marketing": ["식상", "상관", "인맥", "귀인"],
}

GOAL_WEIGHTS = {
    "growth": ["창업", "사업", "재운", "대운"],
    "stability": ["정재", "정관", "정인", "신강"],
    "expansion": ["편재", "편관", "식상", "합작"],
    "exit": ["재고", "재성", "대운", "유년"],
}


def get_survey_tag_weights(survey_data: Optional[Dict] = None) -> Dict[str, float]:
    """설문 기반 태그 가중치 반환"""
    if not survey_data:
        return {}
    
    weights = {}
    
    industry = survey_data.get("industry", "").lower()
    if industry in INDUSTRY_WEIGHTS:
        for tag in INDUSTRY_WEIGHTS[industry]:
            weights[tag] = weights.get(tag, 0) + 1.5
    
    pain = survey_data.get("painPoint", "").lower()
    if pain in PAINPOINT_WEIGHTS:
        for tag in PAINPOINT_WEIGHTS[pain]:
            weights[tag] = weights.get(tag, 0) + 2.0
    
    goal = survey_data.get("businessGoal", "").lower()
    if goal in GOAL_WEIGHTS:
        for tag in GOAL_WEIGHTS[goal]:
            weights[tag] = weights.get(tag, 0) + 1.0
    
    return weights


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ScoreTrace 클래스 (report_worker 호환)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@dataclass
class ScoreTrace:
    """점수 breakdown (to_dict 메서드 필수)"""
    base_score: float = 0.0
    tag_match_score: float = 0.0
    survey_score: float = 0.0
    priority_score: float = 0.0
    section_boost: float = 0.0
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "base_score": self.base_score,
            "tag_match_score": self.tag_match_score,
            "survey_score": self.survey_score,
            "priority_score": self.priority_score,
            "section_boost": self.section_boost,
            "total": self.base_score + self.tag_match_score + self.survey_score + self.priority_score + self.section_boost
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ScoredCard 클래스 (report_worker 호환)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@dataclass
class ScoredCard:
    """스코어링된 카드 (report_worker 인터페이스 준수)"""
    card_id: str
    topic: str
    subtopic: str
    final_score: float
    matched_tags: List[str] = field(default_factory=list)
    score_trace: ScoreTrace = field(default_factory=ScoreTrace)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SectionCards 클래스 (report_worker 호환)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@dataclass
class SectionCards:
    """섹션별 카드 선택 결과 (report_worker 인터페이스 준수)"""
    cards: List[ScoredCard] = field(default_factory=list)
    match_summary: Dict[str, Any] = field(default_factory=dict)
    avg_score: float = 0.0
    total_cards: int = 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RuleCardScorer 메인 클래스
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class RuleCardScorer:
    """RuleCard 스코어러 (report_worker 인터페이스 준수)"""
    
    def __init__(self, cards: List[Any] = None):
        self.cards = cards or []
    
    def set_cards(self, cards: List[Any]):
        """카드 주입"""
        self.cards = cards
    
    def score_cards_for_section(
        self,
        all_cards: List[Dict[str, Any]],
        section_id: str,
        feature_tags: List[str],
        survey_data: Optional[Dict] = None,
        existing_topics: Set[str] = None
    ) -> SectionCards:
        """
        섹션별 카드 스코어링 (report_worker 호환 인터페이스)
        
        Args:
            all_cards: 전체 룰카드 리스트 (dict)
            section_id: 섹션 ID
            feature_tags: 피처 태그 리스트
            survey_data: 설문 데이터
            existing_topics: 이미 사용된 토픽 (중복 방지)
        
        Returns:
            SectionCards 객체
        """
        if existing_topics is None:
            existing_topics = set()
        
        feature_set = set(feature_tags)
        survey_weights = get_survey_tag_weights(survey_data)
        
        scored_cards = []
        
        for card in all_cards:
            card_id = card.get("id", card.get("_id", ""))
            topic = card.get("topic", "GENERAL")
            subtopic = card.get("subtopic", "")
            card_tags = set(card.get("tags", []))
            priority = float(card.get("priority", 0))
            
            # 태그 매칭
            matched = card_tags & feature_set
            
            # 점수 계산
            trace = ScoreTrace()
            trace.base_score = 1.0
            trace.tag_match_score = len(matched) * 2.0
            trace.priority_score = min(priority, 10) * 0.5
            
            # 설문 가중치
            for tag in card_tags:
                if tag in survey_weights:
                    trace.survey_score += survey_weights[tag]
            
            # 섹션 부스트 (토픽 매칭)
            if section_id.lower() in topic.lower():
                trace.section_boost = 3.0
            
            final_score = trace.base_score + trace.tag_match_score + trace.survey_score + trace.priority_score + trace.section_boost
            
            scored_cards.append(ScoredCard(
                card_id=card_id,
                topic=topic,
                subtopic=subtopic,
                final_score=final_score,
                matched_tags=list(matched),
                score_trace=trace
            ))
        
        # 점수순 정렬
        scored_cards.sort(key=lambda x: x.final_score, reverse=True)
        
        # 상위 20개 선택
        selected = scored_cards[:20]
        
        # 통계
        avg_score = sum(c.final_score for c in selected) / len(selected) if selected else 0.0
        
        match_summary = {
            "section_id": section_id,
            "total_pool": len(all_cards),
            "selected_count": len(selected),
            "top_tags": list(feature_set)[:10],
            "survey_applied": bool(survey_data),
        }
        
        logger.info(f"[Scorer] section={section_id} | pool={len(all_cards)} | selected={len(selected)} | avg_score={avg_score:.1f}")
        
        return SectionCards(
            cards=selected,
            match_summary=match_summary,
            avg_score=avg_score,
            total_cards=len(selected)
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 호환용 싱글톤 (구버전 코드 호환)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class RuleCardScorerSingleton(RuleCardScorer):
    """싱글톤 스코어러 (호환성)"""
    pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 싱글톤 export
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
rulecard_scorer = RuleCardScorerSingleton()
