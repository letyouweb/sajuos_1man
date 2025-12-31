"""
RuleCard Scorer v3 - P0: 철벽 trigger 우선 매칭
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
우선순위:
1. trigger.day_master 불일치 → 즉시 탈락
2. trigger.month_branch 불일치 → 탈락
3. presence_of → tokens에 모두 존재해야 통과
4. absence_of → tokens에 하나라도 있으면 탈락
5. 통과 카드만 대상으로 tags + survey 가중치 점수
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import logging
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ScoredCard:
    card_id: str
    total_score: float
    score_trace: Dict[str, float] = field(default_factory=dict)
    matched_tags: List[str] = field(default_factory=list)


# 설문 가중치 매핑
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


class RuleCardScorer:
    """철벽 trigger 우선 매칭 스코어러"""
    
    def __init__(self, cards: List[Any]):
        self.cards = cards
    
    def score_cards(
        self,
        features: Dict[str, Any],
        survey_data: Optional[Dict] = None,
        section_id: str = "general"
    ) -> List[ScoredCard]:
        """
        카드 스코어링 (trigger 우선)
        
        Args:
            features: build_feature_tags() 결과
            survey_data: 설문 데이터
            section_id: 섹션 ID
        
        Returns:
            List[ScoredCard] 점수순 정렬
        """
        day_master = features.get("day_master")
        month_branch = features.get("month_branch")
        tokens = set(features.get("tokens", []))
        survey_tags = set(features.get("survey_tags", []))
        
        # 오행, 십성도 tokens에 추가
        for elem, cnt in features.get("elements_count", {}).items():
            if cnt > 0:
                tokens.add(elem)
        
        ten_gods = features.get("ten_gods_count")
        if ten_gods:
            for god in ten_gods.keys():
                tokens.add(god)
        
        scored = []
        
        for card in self.cards:
            score_trace = {
                "day_master": 0,
                "month_branch": 0,
                "presence": 0,
                "absence": 0,
                "tag_match": 0,
                "survey_industry": 0,
                "survey_pain": 0,
                "survey_goal": 0,
                "priority": 0,
            }
            
            # trigger 파싱
            trigger = self._parse_trigger(card)
            
            # 1. day_master 체크 (불일치 시 탈락)
            trigger_dm = trigger.get("day_master")
            if trigger_dm and day_master:
                if trigger_dm != day_master:
                    continue  # 탈락
                score_trace["day_master"] = 3.0
            
            # 2. month_branch 체크 (불일치 시 탈락)
            trigger_mb = trigger.get("month_branch")
            if trigger_mb and month_branch:
                if trigger_mb != month_branch:
                    continue  # 탈락
                score_trace["month_branch"] = 2.0
            
            # 3. presence_of 체크 (모두 존재해야 통과)
            presence = trigger.get("presence_of", [])
            if presence:
                if not all(p in tokens for p in presence):
                    continue  # 탈락
                score_trace["presence"] = len(presence) * 1.5
            
            # 4. absence_of 체크 (하나라도 있으면 탈락)
            absence = trigger.get("absence_of", [])
            if absence:
                if any(a in tokens for a in absence):
                    continue  # 탈락
                score_trace["absence"] = 1.0
            
            # === 통과한 카드만 점수 계산 ===
            
            # 5. 태그 매칭 점수
            card_tags = set(getattr(card, 'tags', []) or [])
            matched = card_tags & tokens
            score_trace["tag_match"] = len(matched) * 1.0
            
            # 6. 설문 가중치
            if survey_data:
                industry = survey_data.get("industry", "").lower()
                if industry in INDUSTRY_WEIGHTS:
                    for tag in INDUSTRY_WEIGHTS[industry]:
                        if tag in card_tags:
                            score_trace["survey_industry"] += 1.5
                
                pain = survey_data.get("painPoint", "").lower()
                if pain in PAINPOINT_WEIGHTS:
                    for tag in PAINPOINT_WEIGHTS[pain]:
                        if tag in card_tags:
                            score_trace["survey_pain"] += 2.0
                
                goal = survey_data.get("businessGoal", "").lower()
                if goal in GOAL_WEIGHTS:
                    for tag in GOAL_WEIGHTS[goal]:
                        if tag in card_tags:
                            score_trace["survey_goal"] += 1.0
            
            # 7. priority 가산
            priority = getattr(card, 'priority', 0) or 0
            score_trace["priority"] = min(priority, 10) * 0.5
            
            # 총점
            total = sum(score_trace.values())
            
            scored.append(ScoredCard(
                card_id=getattr(card, 'id', ''),
                total_score=total,
                score_trace=score_trace,
                matched_tags=list(matched)
            ))
        
        # 점수순 정렬
        scored.sort(key=lambda x: x.total_score, reverse=True)
        
        logger.info(f"[Scorer] section={section_id}, passed={len(scored)}/{len(self.cards)}")
        
        return scored
    
    def _parse_trigger(self, card) -> Dict[str, Any]:
        """trigger 파싱"""
        trigger_raw = getattr(card, 'trigger', None)
        if not trigger_raw:
            return {}
        
        if isinstance(trigger_raw, dict):
            return trigger_raw
        
        if isinstance(trigger_raw, str):
            try:
                return json.loads(trigger_raw)
            except:
                return {}
        
        return {}
    
    def get_top_k(
        self,
        features: Dict[str, Any],
        survey_data: Optional[Dict] = None,
        section_id: str = "general",
        k: int = 10
    ) -> tuple[List[ScoredCard], Dict[str, Any]]:
        """
        상위 K개 카드 + 매치 서머리 반환
        
        Returns:
            (scored_cards, match_summary)
        """
        scored = self.score_cards(features, survey_data, section_id)
        top_k = scored[:k]
        
        match_summary = {
            "section_id": section_id,
            "total_candidates": len(self.cards),
            "passed_trigger": len(scored),
            "selected": len(top_k),
            "top_ids": [c.card_id for c in top_k[:3]],
            "score_traces": {c.card_id: c.score_trace for c in top_k[:3]},
        }
        
        return top_k, match_summary


def create_scorer(cards: List[Any]) -> RuleCardScorer:
    """스코어러 생성 헬퍼"""
    return RuleCardScorer(cards)


# 🔥 P0: 호환성을 위한 심볼 추가
@dataclass
class SectionCards:
    """섹션별 카드 할당 결과"""
    section_id: str
    cards: List[Any] = field(default_factory=list)
    score_traces: Dict[str, Any] = field(default_factory=dict)


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


# 🔥 P0: 싱글톤 인스턴스 (호환성)
class RuleCardScorerSingleton:
    """싱글톤 스코어러 (cards 나중에 주입)"""
    def __init__(self):
        self.cards = []
        self._scorer = None
    
    def set_cards(self, cards: List[Any]):
        self.cards = cards
        self._scorer = RuleCardScorer(cards)
    
    def score_cards(self, features: Dict[str, Any], survey_data: Optional[Dict] = None, section_id: str = "general") -> List[ScoredCard]:
        if self._scorer is None:
            self._scorer = RuleCardScorer(self.cards)
        return self._scorer.score_cards(features, survey_data, section_id)
    
    def get_top_k(self, features: Dict[str, Any], survey_data: Optional[Dict] = None, section_id: str = "general", k: int = 10):
        if self._scorer is None:
            self._scorer = RuleCardScorer(self.cards)
        return self._scorer.get_top_k(features, survey_data, section_id, k)


# 🔥 P0: 싱글톤 export
rulecard_scorer = RuleCardScorerSingleton()
