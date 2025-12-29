"""
RuleCard Scorer - 사업가형 핵심태그 50 기반 스코어링 엔진
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
각 섹션에 가장 관련 높은 Top-100 RuleCards 선발
+ 다양성 보장 (topic 분산)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import logging
from typing import Dict, Any, List, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import random

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 사업가형 핵심 태그 50 + 가중치
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 비즈니스 컨설팅에 가장 중요한 태그들
BUSINESS_CORE_TAGS_50 = {
    # ═══ 재물/금전 관련 (15개) ═══
    "財星": 10,       # 재성 - 재물 운
    "正財": 9,        # 정재 - 안정적 수입
    "偏財": 9,        # 편재 - 투자/투기 수익
    "財庫": 10,       # 재고 - 재물 저장
    "破財": 8,        # 파재 - 재물 손실
    "損財": 8,        # 손재 - 재물 소비
    "財運": 10,       # 재운 - 재물 운세
    "投資": 9,        # 투자 관련
    "收入": 8,        # 수입 관련
    "支出": 8,        # 지출 관련
    "富貴": 9,        # 부귀 - 재물+명예
    "財多身弱": 7,    # 재다신약 - 돈은 많은데 감당 못함
    "財旺身強": 9,    # 재왕신강 - 재물+실력 겸비
    "食神生財": 10,   # 식신생재 - 창작으로 돈 벌기
    "劫財爭財": 6,    # 겁재쟁재 - 경쟁으로 재물 빼앗김
    
    # ═══ 사업/커리어 관련 (15개) ═══
    "官星": 9,        # 관성 - 직장/사회적 지위
    "正官": 8,        # 정관 - 안정적 직장
    "偏官": 8,        # 편관/칠살 - 도전적 커리어
    "印星": 9,        # 인성 - 학습/자격/후원
    "正印": 8,        # 정인 - 전통적 학업/자격
    "偏印": 8,        # 편인 - 특수 기술/창의
    "食傷": 9,        # 식상 - 창작/표현/수완
    "食神": 8,        # 식신 - 안정적 창작
    "傷官": 8,        # 상관 - 혁신/돌파
    "比劫": 7,        # 비겁 - 경쟁/협력
    "比肩": 7,        # 비견 - 동등 경쟁
    "劫財": 7,        # 겁재 - 치열한 경쟁
    "創業": 10,       # 창업 직접 관련
    "事業": 10,       # 사업 직접 관련
    "轉職": 8,        # 이직/전직
    
    # ═══ 시기/타이밍 관련 (10개) ═══
    "大運": 10,       # 대운 - 10년 주기
    "流年": 10,       # 유년 - 1년 주기
    "月運": 8,        # 월운 - 월별
    "吉時": 9,        # 길시 - 좋은 시기
    "凶時": 8,        # 흉시 - 나쁜 시기
    "開業": 9,        # 개업 시기
    "動土": 7,        # 공사/확장 시기
    "移徙": 7,        # 이사/이동 시기
    "合作": 9,        # 협력/계약 시기
    "貴人運": 10,     # 귀인운 - 조력자
    
    # ═══ 건강/에너지 관련 (5개) ═══
    "身强": 9,        # 신강 - 체력/에너지 강함
    "身弱": 8,        # 신약 - 체력/에너지 약함
    "健康": 8,        # 건강 직접
    "勞累": 7,        # 과로/피로
    "精神": 7,        # 정신력/멘탈
    
    # ═══ 관계/네트워크 관련 (5개) ═══
    "貴人": 10,       # 귀인 - 조력자
    "小人": 7,        # 소인 - 방해자
    "人脈": 9,        # 인맥 - 네트워크
    "合": 8,          # 합 - 조화/협력
    "沖": 8,          # 충 - 갈등/변화
}

# 섹션별 가중 태그 (해당 섹션에서 더 중요한 태그)
SECTION_TAG_WEIGHTS = {
    "exec": {
        "大運": 2.0, "流年": 2.0, "吉時": 1.5, "貴人運": 1.5,
        "身强": 1.5, "身弱": 1.5, "財運": 1.5, "事業": 1.5,
    },
    "money": {
        "財星": 2.0, "正財": 2.0, "偏財": 2.0, "財庫": 2.0,
        "破財": 1.8, "損財": 1.8, "投資": 1.8, "收入": 1.8,
        "食神生財": 2.0, "財旺身強": 1.8, "財多身弱": 1.5,
    },
    "business": {
        "創業": 2.0, "事業": 2.0, "官星": 1.8, "食傷": 1.8,
        "傷官": 1.5, "食神": 1.5, "轉職": 1.5, "合作": 1.5,
    },
    "team": {
        "貴人": 2.0, "人脈": 2.0, "合": 1.8, "沖": 1.5,
        "小人": 1.5, "比劫": 1.5, "比肩": 1.5, "劫財": 1.5,
    },
    "health": {
        "身强": 2.0, "身弱": 2.0, "健康": 2.0, "勞累": 1.8,
        "精神": 1.8, "印星": 1.5, "正印": 1.5,
    },
    "calendar": {
        "月運": 2.0, "流年": 2.0, "吉時": 2.0, "凶時": 1.8,
        "開業": 1.5, "動土": 1.5, "移徙": 1.5, "合作": 1.5,
    },
    "sprint": {
        "吉時": 2.0, "開業": 2.0, "合作": 1.8, "貴人": 1.8,
        "財運": 1.5, "事業": 1.5, "轉職": 1.5,
    },
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 스코어링 결과 데이터 구조
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class ScoredCard:
    """점수가 매겨진 룰카드"""
    card_id: str
    topic: str
    subtopic: str = ""
    score: float = 0.0
    matched_tags: List[str] = field(default_factory=list)
    diversity_bonus: float = 0.0
    
    @property
    def final_score(self) -> float:
        return self.score + self.diversity_bonus


@dataclass 
class SectionCards:
    """섹션별 선택된 카드들"""
    section_id: str
    cards: List[ScoredCard]
    total_cards: int
    topic_distribution: Dict[str, int]  # topic별 카드 수
    avg_score: float


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 룰카드 스코어링 엔진
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class RuleCardScorer:
    """사업가형 태그 기반 룰카드 스코어링"""
    
    def __init__(
        self,
        cards_per_section: int = 100,
        min_diversity_ratio: float = 0.3,  # 최소 다양성 (topic 분산)
    ):
        self.cards_per_section = cards_per_section
        self.min_diversity_ratio = min_diversity_ratio
    
    def score_cards_for_section(
        self,
        all_cards: List[Dict[str, Any]],
        section_id: str,
        feature_tags: List[str],
        existing_topics: Set[str] = None
    ) -> SectionCards:
        """
        특정 섹션에 대해 룰카드 스코어링 + Top-N 선택
        
        Args:
            all_cards: 전체 룰카드 목록
            section_id: 섹션 ID (exec, money, business...)
            feature_tags: 사주 기반 FeatureTags
            existing_topics: 이미 다른 섹션에서 선택된 topic들 (다양성용)
        
        Returns:
            SectionCards: 선택된 카드들 + 메타데이터
        """
        existing_topics = existing_topics or set()
        
        # 섹션별 태그 가중치 가져오기
        section_weights = SECTION_TAG_WEIGHTS.get(section_id, {})
        
        scored_cards: List[ScoredCard] = []
        
        for card in all_cards:
            card_id = card.get("id", "")
            topic = card.get("topic", "")
            subtopic = card.get("subtopic", "")
            card_tags = card.get("tags", [])
            
            if isinstance(card_tags, str):
                card_tags = [card_tags]
            
            # 1. 기본 점수: 사업가 핵심 태그 50 매칭
            base_score = 0.0
            matched_tags = []
            
            for tag in card_tags:
                if tag in BUSINESS_CORE_TAGS_50:
                    tag_score = BUSINESS_CORE_TAGS_50[tag]
                    
                    # 섹션별 가중치 적용
                    if tag in section_weights:
                        tag_score *= section_weights[tag]
                    
                    base_score += tag_score
                    matched_tags.append(tag)
            
            # 2. FeatureTags 매칭 보너스
            feature_match_count = sum(1 for ft in feature_tags if ft in card_tags)
            feature_bonus = feature_match_count * 5  # 매칭당 +5점
            
            # 3. Topic 관련성 보너스
            topic_bonus = self._get_topic_relevance(topic, section_id)
            
            # 4. 다양성 보너스 (이미 선택된 topic이 아니면 가산점)
            diversity_bonus = 0.0
            if topic and topic not in existing_topics:
                diversity_bonus = 3.0
            
            total_score = base_score + feature_bonus + topic_bonus
            
            scored_cards.append(ScoredCard(
                card_id=card_id,
                topic=topic,
                subtopic=subtopic,
                score=total_score,
                matched_tags=matched_tags,
                diversity_bonus=diversity_bonus
            ))
        
        # 5. 점수순 정렬
        scored_cards.sort(key=lambda c: c.final_score, reverse=True)
        
        # 6. 다양성 보장하면서 Top-N 선택
        selected = self._select_with_diversity(scored_cards)
        
        # 7. 통계 계산
        topic_dist = defaultdict(int)
        for card in selected:
            topic_dist[card.topic] += 1
        
        avg_score = sum(c.score for c in selected) / len(selected) if selected else 0
        
        return SectionCards(
            section_id=section_id,
            cards=selected,
            total_cards=len(selected),
            topic_distribution=dict(topic_dist),
            avg_score=avg_score
        )
    
    def _get_topic_relevance(self, topic: str, section_id: str) -> float:
        """Topic과 섹션 간 관련성 점수"""
        
        # 섹션별 관련 Topic 매핑
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
    
    def _select_with_diversity(
        self,
        scored_cards: List[ScoredCard]
    ) -> List[ScoredCard]:
        """
        다양성을 보장하면서 Top-N 선택
        
        전략:
        1. 상위 50%는 점수순으로 선택
        2. 나머지 50%는 topic 다양성 고려해서 선택
        """
        if not scored_cards:
            return []
        
        target_count = min(self.cards_per_section, len(scored_cards))
        top_half = int(target_count * 0.5)
        
        # 1. 상위 50%는 점수순
        selected = scored_cards[:top_half]
        used_topics = {c.topic for c in selected}
        
        # 2. 나머지는 다양성 고려
        remaining = scored_cards[top_half:]
        
        # Topic별로 그룹화
        by_topic: Dict[str, List[ScoredCard]] = defaultdict(list)
        for card in remaining:
            by_topic[card.topic].append(card)
        
        # 아직 선택되지 않은 topic 우선 + 라운드로빈
        unused_topics = [t for t in by_topic.keys() if t not in used_topics]
        used_topic_list = list(used_topics & set(by_topic.keys()))
        
        # 순서: 미사용 topic -> 사용 topic
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
        section_ids: List[str] = None
    ) -> Dict[str, SectionCards]:
        """
        모든 섹션에 대해 스코어링
        
        Args:
            all_cards: 전체 룰카드
            feature_tags: FeatureTags
            section_ids: 스코어링할 섹션 목록
        
        Returns:
            Dict[section_id, SectionCards]
        """
        if section_ids is None:
            section_ids = ["exec", "money", "business", "team", "health", "calendar", "sprint"]
        
        results = {}
        used_topics: Set[str] = set()
        
        for section_id in section_ids:
            section_cards = self.score_cards_for_section(
                all_cards=all_cards,
                section_id=section_id,
                feature_tags=feature_tags,
                existing_topics=used_topics
            )
            
            results[section_id] = section_cards
            
            # 사용된 topic 업데이트 (다양성 보장)
            used_topics.update(section_cards.topic_distribution.keys())
        
        return results
    
    def get_cards_for_prompt(
        self,
        section_cards: SectionCards,
        max_chars: int = 8000
    ) -> str:
        """
        프롬프트에 주입할 룰카드 텍스트 생성
        
        Args:
            section_cards: 선택된 카드들
            max_chars: 최대 문자 수
        
        Returns:
            프롬프트에 넣을 텍스트
        """
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
# 4. 유틸리티 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_business_core_tags() -> Dict[str, int]:
    """사업가형 핵심 태그 50 조회"""
    return BUSINESS_CORE_TAGS_50.copy()


def get_section_tag_weights(section_id: str) -> Dict[str, float]:
    """섹션별 태그 가중치 조회"""
    return SECTION_TAG_WEIGHTS.get(section_id, {}).copy()


# 싱글톤 인스턴스
rulecard_scorer = RuleCardScorer()
