"""
RuleCard Scorer v2 - P0 Pivot: 설문 5문항 가중치 + 스코어 트레이스
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 P0 핵심 변경:
1. industry/painPoint/goal 설문 기반 가중치 추가
2. 같은 사주라도 설문에 따라 선택 카드가 달라짐
3. score_trace로 점수 breakdown 제공
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import logging
from typing import Dict, Any, List, Set, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import random

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 사업가형 핵심 태그 50 + 가중치
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BUSINESS_CORE_TAGS_50 = {
    # ═══ 재물/금전 관련 (15개) ═══
    "財星": 10, "正財": 9, "偏財": 9, "財庫": 10, "破財": 8,
    "損財": 8, "財運": 10, "投資": 9, "收入": 8, "支出": 8,
    "富貴": 9, "財多身弱": 7, "財旺身強": 9, "食神生財": 10, "劫財爭財": 6,
    
    # ═══ 사업/커리어 관련 (15개) ═══
    "官星": 9, "正官": 8, "偏官": 8, "印星": 9, "正印": 8,
    "偏印": 8, "食傷": 9, "食神": 8, "傷官": 8, "比劫": 7,
    "比肩": 7, "劫財": 7, "創業": 10, "事業": 10, "轉職": 8,
    
    # ═══ 시기/타이밍 관련 (10개) ═══
    "大運": 10, "流年": 10, "月運": 8, "吉時": 9, "凶時": 8,
    "開業": 9, "動土": 7, "移徙": 7, "合作": 9, "貴人運": 10,
    
    # ═══ 건강/에너지 관련 (5개) ═══
    "身强": 9, "身弱": 8, "健康": 8, "勞累": 7, "精神": 7,
    
    # ═══ 관계/네트워크 관련 (5개) ═══
    "貴人": 10, "小人": 7, "人脈": 9, "合": 8, "沖": 8,
}

# 섹션별 가중 태그
SECTION_TAG_WEIGHTS = {
    "exec": {"大運": 2.0, "流年": 2.0, "吉時": 1.5, "貴人運": 1.5, "身强": 1.5, "身弱": 1.5, "財運": 1.5, "事業": 1.5},
    "money": {"財星": 2.0, "正財": 2.0, "偏財": 2.0, "財庫": 2.0, "破財": 1.8, "損財": 1.8, "投資": 1.8, "收入": 1.8, "食神生財": 2.0, "財旺身強": 1.8, "財多身弱": 1.5},
    "business": {"創業": 2.0, "事業": 2.0, "官星": 1.8, "食傷": 1.8, "傷官": 1.5, "食神": 1.5, "轉職": 1.5, "合作": 1.5},
    "team": {"貴人": 2.0, "人脈": 2.0, "合": 1.8, "沖": 1.5, "小人": 1.5, "比劫": 1.5, "比肩": 1.5, "劫財": 1.5},
    "health": {"身强": 2.0, "身弱": 2.0, "健康": 2.0, "勞累": 1.8, "精神": 1.8, "印星": 1.5, "正印": 1.5},
    "calendar": {"月運": 2.0, "流年": 2.0, "吉時": 2.0, "凶時": 1.8, "開業": 1.5, "動土": 1.5, "移徙": 1.5, "合作": 1.5},
    "sprint": {"吉時": 2.0, "開業": 2.0, "合作": 1.8, "貴人": 1.8, "財運": 1.5, "事業": 1.5, "轉職": 1.5},
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 🔥 P0: 설문 기반 가중치 태그 매핑
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 업종 → 관련 태그 + 가중치
INDUSTRY_TAG_WEIGHTS: Dict[str, Dict[str, float]] = {
    # IT/테크
    "it": {"創業": 2.0, "事業": 1.5, "食傷": 1.8, "傷官": 1.5, "印星": 1.3},
    "saas": {"創業": 2.0, "事業": 1.5, "食傷": 1.8, "收入": 2.0, "傷官": 1.5},
    "개발": {"創業": 1.5, "印星": 2.0, "食傷": 1.8, "傷官": 1.5},
    "ai": {"創業": 2.0, "印星": 2.0, "食傷": 1.8, "傷官": 1.5},
    "플랫폼": {"創業": 2.0, "事業": 2.0, "財運": 1.8, "合作": 1.5},
    
    # 커머스
    "커머스": {"財星": 2.0, "正財": 2.0, "偏財": 1.8, "投資": 1.5, "收入": 2.0, "財庫": 1.5},
    "쇼핑몰": {"財星": 2.0, "正財": 2.0, "偏財": 1.8, "投資": 1.5, "收入": 2.0},
    "온라인": {"財星": 1.8, "正財": 1.8, "偏財": 1.5, "收入": 1.8},
    
    # 서비스
    "컨설팅": {"官星": 2.0, "正官": 1.8, "人脈": 2.0, "貴人": 1.8, "印星": 1.5},
    "교육": {"印星": 2.0, "正印": 2.0, "人脈": 1.5, "食神": 1.8},
    "코칭": {"印星": 2.0, "人脈": 1.8, "食神": 1.5, "貴人": 1.5},
    
    # 요식업
    "카페": {"財星": 1.8, "食神": 2.0, "收入": 1.5, "勞累": 1.5, "投資": 1.3},
    "음식점": {"財星": 1.8, "食神": 2.0, "收入": 1.5, "勞累": 1.5},
    "식당": {"財星": 1.8, "食神": 2.0, "收入": 1.5, "勞累": 1.5},
    
    # 콘텐츠
    "콘텐츠": {"食傷": 2.0, "傷官": 2.0, "食神": 1.8, "創業": 1.5, "收入": 1.5},
    "유튜브": {"食傷": 2.0, "傷官": 2.0, "人脈": 1.8, "創業": 1.5},
    "크리에이터": {"食傷": 2.0, "傷官": 2.0, "人脈": 1.5},
    
    # 부동산/투자
    "부동산": {"財星": 2.0, "正財": 2.0, "偏財": 2.0, "財庫": 2.0, "投資": 2.0},
    "투자": {"偏財": 2.0, "財星": 2.0, "投資": 2.0, "財庫": 1.8, "大運": 1.5},
}

# 병목 → 관련 태그 + 가중치
PAINPOINT_TAG_WEIGHTS: Dict[str, Dict[str, float]] = {
    "lead": {"人脈": 2.5, "貴人": 2.0, "官星": 1.5, "食傷": 1.8, "傷官": 1.5, "合作": 1.5},
    "conversion": {"財星": 2.0, "正財": 2.0, "食神生財": 2.5, "合作": 1.5, "吉時": 1.5},
    "operations": {"印星": 2.0, "正印": 2.0, "官星": 1.5, "勞累": 1.8, "精神": 1.5},
    "funding": {"財星": 2.5, "財庫": 2.5, "破財": 2.0, "損財": 1.8, "偏財": 1.5, "投資": 2.0},
    "mental": {"身弱": 2.5, "勞累": 2.5, "精神": 2.0, "健康": 2.0, "印星": 1.5},
    "direction": {"大運": 2.5, "流年": 2.0, "官星": 1.8, "印星": 1.5, "轉職": 2.0},
}

# 목표 키워드 → 관련 태그 + 가중치
GOAL_TAG_WEIGHTS: Dict[str, Dict[str, float]] = {
    "매출": {"財星": 2.5, "正財": 2.0, "財運": 2.0, "收入": 2.0, "食神生財": 2.0},
    "수익": {"財星": 2.5, "正財": 2.0, "財運": 2.0, "收入": 2.0},
    "돈": {"財星": 2.5, "偏財": 2.0, "財庫": 2.0, "財運": 2.0},
    "월매출": {"財星": 2.5, "正財": 2.0, "財運": 2.0, "收入": 2.0, "月運": 1.5},
    "확장": {"官星": 2.0, "事業": 2.0, "合作": 2.0, "投資": 1.8, "大運": 1.5},
    "스케일": {"官星": 2.0, "事業": 2.0, "合作": 2.0, "投資": 1.8},
    "성장": {"官星": 2.0, "事業": 2.0, "大運": 2.0, "流年": 1.5},
    "팀": {"比劫": 2.0, "比肩": 2.0, "合作": 2.5, "人脈": 1.8, "官星": 1.5},
    "채용": {"比劫": 2.0, "合作": 2.0, "人脈": 2.0, "官星": 1.5},
    "브랜드": {"印星": 2.5, "正印": 2.0, "官星": 1.8, "食傷": 1.5},
    "인지도": {"印星": 2.0, "官星": 2.0, "食傷": 1.8, "人脈": 1.5},
    "자동화": {"印星": 2.5, "正印": 2.0, "食神": 1.8, "官星": 1.5},
    "시스템": {"印星": 2.5, "正印": 2.0, "官星": 1.5},
    "안정": {"正財": 2.5, "財庫": 2.0, "身强": 2.0, "印星": 1.5},
    "워라밸": {"身强": 2.5, "健康": 2.0, "精神": 2.0, "印星": 1.5},
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 스코어링 결과 데이터 구조
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class ScoreTrace:
    """🔥 P0: 점수 breakdown (디버깅/투명성)"""
    priority: float = 0.0
    tag_match: float = 0.0
    section_bonus: float = 0.0
    feature_match: float = 0.0
    industry_match: float = 0.0
    pain_match: float = 0.0
    goal_match: float = 0.0
    diversity_bonus: float = 0.0
    
    @property
    def total(self) -> float:
        return (
            self.priority + self.tag_match + self.section_bonus +
            self.feature_match + self.industry_match + self.pain_match +
            self.goal_match + self.diversity_bonus
        )
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "priority": round(self.priority, 2),
            "tag_match": round(self.tag_match, 2),
            "section_bonus": round(self.section_bonus, 2),
            "feature_match": round(self.feature_match, 2),
            "industry_match": round(self.industry_match, 2),
            "pain_match": round(self.pain_match, 2),
            "goal_match": round(self.goal_match, 2),
            "diversity_bonus": round(self.diversity_bonus, 2),
            "total": round(self.total, 2),
        }


@dataclass
class ScoredCard:
    """점수가 매겨진 룰카드"""
    card_id: str
    topic: str
    subtopic: str = ""
    score: float = 0.0
    matched_tags: List[str] = field(default_factory=list)
    score_trace: ScoreTrace = field(default_factory=ScoreTrace)
    
    @property
    def final_score(self) -> float:
        return self.score_trace.total


@dataclass 
class SectionCards:
    """섹션별 선택된 카드들"""
    section_id: str
    cards: List[ScoredCard]
    total_cards: int
    topic_distribution: Dict[str, int]
    avg_score: float
    # 🔥 P0: 디버깅용 match_summary
    match_summary: Dict[str, Any] = field(default_factory=dict)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 🔥 P0: 설문 기반 스코어링 엔진
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class RuleCardScorer:
    """사업가형 태그 + 설문 기반 룰카드 스코어링"""
    
    def __init__(
        self,
        cards_per_section: int = 100,
        min_diversity_ratio: float = 0.3,
    ):
        self.cards_per_section = cards_per_section
        self.min_diversity_ratio = min_diversity_ratio
    
    def score_cards_for_section(
        self,
        all_cards: List[Dict[str, Any]],
        section_id: str,
        feature_tags: List[str],
        survey_data: Optional[Dict[str, Any]] = None,
        existing_topics: Set[str] = None
    ) -> SectionCards:
        """
        🔥 P0: 설문 가중치 반영 스코어링
        
        Args:
            all_cards: 전체 룰카드
            section_id: 섹션 ID
            feature_tags: 사주 기반 FeatureTags
            survey_data: 🔥 P0 설문 데이터 (industry, painPoint, goal 포함)
            existing_topics: 다른 섹션에서 선택된 topic들
        """
        existing_topics = existing_topics or set()
        survey_data = survey_data or {}
        
        # 섹션별 태그 가중치
        section_weights = SECTION_TAG_WEIGHTS.get(section_id, {})
        
        # 🔥 P0: 설문 데이터 추출
        industry = (survey_data.get("industry") or "").lower()
        pain_point = survey_data.get("painPoint") or survey_data.get("primary_bottleneck") or ""
        goal = (survey_data.get("goal") or survey_data.get("goal_detail") or "").lower()
        
        # 🔥 P0: 설문 기반 가중치 태그 수집
        industry_weights = {}
        for keyword, weights in INDUSTRY_TAG_WEIGHTS.items():
            if keyword in industry:
                for tag, weight in weights.items():
                    industry_weights[tag] = max(industry_weights.get(tag, 0), weight)
        
        pain_weights = PAINPOINT_TAG_WEIGHTS.get(pain_point, {})
        
        goal_weights = {}
        for keyword, weights in GOAL_TAG_WEIGHTS.items():
            if keyword in goal:
                for tag, weight in weights.items():
                    goal_weights[tag] = max(goal_weights.get(tag, 0), weight)
        
        scored_cards: List[ScoredCard] = []
        match_counts = {
            "total": 0,
            "industry_matched": 0,
            "pain_matched": 0,
            "goal_matched": 0,
            "feature_matched": 0,
            "section_matched": 0,
        }
        
        for card in all_cards:
            card_id = card.get("id", "")
            topic = card.get("topic", "")
            subtopic = card.get("subtopic", "")
            card_tags = card.get("tags", [])
            priority = card.get("priority", 0)
            
            if isinstance(card_tags, str):
                card_tags = [card_tags]
            
            trace = ScoreTrace()
            matched_tags = []
            
            # 1. Priority 점수
            trace.priority = float(priority) * 0.5
            
            # 2. 기본 비즈니스 태그 매칭
            for tag in card_tags:
                if tag in BUSINESS_CORE_TAGS_50:
                    base_score = BUSINESS_CORE_TAGS_50[tag]
                    
                    # 섹션별 가중치 적용
                    if tag in section_weights:
                        base_score *= section_weights[tag]
                        match_counts["section_matched"] += 1
                    
                    trace.tag_match += base_score
                    matched_tags.append(tag)
            
            # 3. 🔥🔥🔥 P0 핵심: FeatureTags 매칭 (사주 기반) - 가중치 10배 폭등!
            # 사주 원국과 맞지 않는 카드는 절대 1등이 될 수 없음
            for ft in feature_tags:
                if ft.lower() in [t.lower() for t in card_tags]:
                    trace.feature_match += 50.0  # 🔥 5.0 → 50.0 (10배 증가)
                    match_counts["feature_matched"] += 1
            
            # 4. 🔥 P0: 업종 가중치
            for tag in card_tags:
                if tag in industry_weights:
                    bonus = industry_weights[tag] * 3.0  # 업종 매칭 보너스
                    trace.industry_match += bonus
                    if bonus > 0:
                        match_counts["industry_matched"] += 1
            
            # 5. 🔥 P0: 병목 가중치
            for tag in card_tags:
                if tag in pain_weights:
                    bonus = pain_weights[tag] * 3.0  # 병목 매칭 보너스
                    trace.pain_match += bonus
                    if bonus > 0:
                        match_counts["pain_matched"] += 1
            
            # 6. 🔥 P0: 목표 가중치
            for tag in card_tags:
                if tag in goal_weights:
                    bonus = goal_weights[tag] * 3.0  # 목표 매칭 보너스
                    trace.goal_match += bonus
                    if bonus > 0:
                        match_counts["goal_matched"] += 1
            
            # 7. 다양성 보너스
            if topic and topic not in existing_topics:
                trace.diversity_bonus = 3.0
            
            match_counts["total"] += 1
            
            scored_cards.append(ScoredCard(
                card_id=card_id,
                topic=topic,
                subtopic=subtopic,
                score=trace.total,
                matched_tags=matched_tags,
                score_trace=trace
            ))
        
        # 점수순 정렬
        scored_cards.sort(key=lambda c: c.final_score, reverse=True)
        
        # 다양성 보장하면서 Top-N 선택
        selected = self._select_with_diversity(scored_cards)
        
        # 통계 계산
        topic_dist = defaultdict(int)
        for card in selected:
            topic_dist[card.topic] += 1
        
        avg_score = sum(c.score for c in selected) / len(selected) if selected else 0
        
        # 🔥 P0: match_summary 생성
        match_summary = {
            "section_id": section_id,
            "total_cards": len(all_cards),
            "selected_cards": len(selected),
            "survey_applied": bool(industry or pain_point or goal),
            "industry": industry,
            "painPoint": pain_point,
            "goal": goal[:50] if goal else "",
            "match_counts": match_counts,
            "top_5_cards": [
                {
                    "id": c.card_id,
                    "score": round(c.final_score, 2),
                    "trace": c.score_trace.to_dict()
                }
                for c in selected[:5]
            ]
        }
        
        logger.info(
            f"[RuleCardScorer:{section_id}] "
            f"Total={len(all_cards)} → Selected={len(selected)} | "
            f"Survey: industry={bool(industry)}, pain={bool(pain_point)}, goal={bool(goal)} | "
            f"AvgScore={avg_score:.1f}"
        )
        
        return SectionCards(
            section_id=section_id,
            cards=selected,
            total_cards=len(selected),
            topic_distribution=dict(topic_dist),
            avg_score=avg_score,
            match_summary=match_summary
        )
    
    def _get_topic_relevance(self, topic: str, section_id: str) -> float:
        """Topic과 섹션 간 관련성 점수"""
        section_topics = {
            "exec": ["운세", "종합", "대운", "길흉", "총론"],
            "money": ["재물", "재운", "금전", "투자", "재정"],
            "business": ["사업", "직업", "커리어", "창업", "진로"],
            "team": ["인간관계", "대인", "협력", "귀인", "소인"],
            "health": ["건강", "체력", "에너지", "컨디션"],
            "calendar": ["월운", "일진", "시기", "날짜"],
            "sprint": ["실행", "계획", "액션", "단기"],
        }
        
        relevant_topics = section_topics.get(section_id, [])
        for rel_topic in relevant_topics:
            if rel_topic in topic:
                return 5.0
        return 0.0
    
    def _select_with_diversity(self, scored_cards: List[ScoredCard]) -> List[ScoredCard]:
        """다양성을 보장하면서 Top-N 선택"""
        if not scored_cards:
            return []
        
        target_count = min(self.cards_per_section, len(scored_cards))
        top_half = int(target_count * 0.5)
        
        # 상위 50%는 점수순
        selected = scored_cards[:top_half]
        used_topics = {c.topic for c in selected}
        
        # 나머지는 다양성 고려
        remaining = scored_cards[top_half:]
        
        by_topic: Dict[str, List[ScoredCard]] = defaultdict(list)
        for card in remaining:
            by_topic[card.topic].append(card)
        
        unused_topics = [t for t in by_topic.keys() if t not in used_topics]
        used_topic_list = list(used_topics & set(by_topic.keys()))
        topic_order = unused_topics + used_topic_list
        
        while len(selected) < target_count:
            added_any = False
            for topic in topic_order:
                if len(selected) >= target_count:
                    break
                if by_topic[topic]:
                    card = by_topic[topic].pop(0)
                    selected.append(card)
                    added_any = True
            if not added_any:
                break
        
        return selected
    
    def score_all_sections(
        self,
        all_cards: List[Dict[str, Any]],
        feature_tags: List[str],
        survey_data: Optional[Dict[str, Any]] = None,
        section_ids: List[str] = None
    ) -> Dict[str, SectionCards]:
        """모든 섹션에 대해 스코어링"""
        if section_ids is None:
            section_ids = ["exec", "money", "business", "team", "health", "calendar", "sprint"]
        
        results = {}
        used_topics: Set[str] = set()
        
        for section_id in section_ids:
            section_cards = self.score_cards_for_section(
                all_cards=all_cards,
                section_id=section_id,
                feature_tags=feature_tags,
                survey_data=survey_data,
                existing_topics=used_topics
            )
            results[section_id] = section_cards
            used_topics.update(section_cards.topic_distribution.keys())
        
        return results
    
    def get_cards_for_prompt(
        self,
        section_cards: SectionCards,
        max_chars: int = 8000
    ) -> str:
        """프롬프트에 주입할 룰카드 텍스트 생성"""
        lines = [
            f"=== {section_cards.section_id.upper()} 섹션 관련 RuleCards ({section_cards.total_cards}장) ===",
            f"평균 관련도 점수: {section_cards.avg_score:.1f}",
            f"Topic 분포: {dict(section_cards.topic_distribution)}",
            "",
        ]
        
        current_len = sum(len(l) for l in lines)
        
        for card in section_cards.cards:
            card_text = f"[{card.card_id}] ({card.topic}/{card.subtopic}) 점수:{card.score:.1f} 태그:{','.join(card.matched_tags[:5])}"
            
            if current_len + len(card_text) > max_chars:
                lines.append(f"... 외 {len(section_cards.cards) - len(lines) + 4}장 (문자 제한으로 생략)")
                break
            
            lines.append(card_text)
            current_len += len(card_text)
        
        return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. 유틸리티 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_business_core_tags() -> Dict[str, int]:
    """사업가형 핵심 태그 50 조회"""
    return BUSINESS_CORE_TAGS_50.copy()


def get_section_tag_weights(section_id: str) -> Dict[str, float]:
    """섹션별 태그 가중치 조회"""
    return SECTION_TAG_WEIGHTS.get(section_id, {}).copy()


def get_survey_tag_weights(survey_data: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """
    🔥 P0: 설문 데이터에서 추출한 가중치 태그 조회
    """
    result = {
        "industry_weights": {},
        "pain_weights": {},
        "goal_weights": {},
    }
    
    industry = (survey_data.get("industry") or "").lower()
    pain_point = survey_data.get("painPoint") or survey_data.get("primary_bottleneck") or ""
    goal = (survey_data.get("goal") or survey_data.get("goal_detail") or "").lower()
    
    for keyword, weights in INDUSTRY_TAG_WEIGHTS.items():
        if keyword in industry:
            for tag, weight in weights.items():
                result["industry_weights"][tag] = max(
                    result["industry_weights"].get(tag, 0), weight
                )
    
    result["pain_weights"] = PAINPOINT_TAG_WEIGHTS.get(pain_point, {})
    
    for keyword, weights in GOAL_TAG_WEIGHTS.items():
        if keyword in goal:
            for tag, weight in weights.items():
                result["goal_weights"][tag] = max(
                    result["goal_weights"].get(tag, 0), weight
                )
    
    return result


# 싱글톤 인스턴스
rulecard_scorer = RuleCardScorer()
