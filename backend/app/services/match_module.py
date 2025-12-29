# -*- coding: utf-8 -*-
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3️⃣ MATCH 모듈 - 룰카드 매칭 엔진 MVP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ELEM→TEN→STRU→SURV→APPL 순서로 필터링 후 점수화
섹션별 Top N(5~8) 카드 선택
matched_rule_ids, match_scores, fired_triggers 저장
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import logging
import json
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from app.services.derive_module import SajuFeatures
from app.services.rulecards_store import RuleCardStore, RuleCard

logger = logging.getLogger(__name__)


# 섹션 우선순위 및 Top N 설정
SECTION_CONFIG = {
    "ELEM": {"priority": 1, "top_n": 8},
    "TEN": {"priority": 2, "top_n": 8},
    "STRU": {"priority": 3, "top_n": 8},
    "SURV": {"priority": 4, "top_n": 5},
    "APPL": {"priority": 5, "top_n": 5}
}


@dataclass
class MatchedCard:
    """매칭된 룰카드"""
    card_id: str
    topic: str
    score: float
    fired_triggers: List[str]
    interpretation: str
    mechanism: Optional[str] = None
    action: Optional[str] = None
    score_details: Optional[Dict[str, float]] = None  # 🔥 점수 상세 추가


@dataclass
class SectionMatch:
    """섹션별 매칭 결과"""
    section_id: str
    cards: List[MatchedCard]
    avg_score: float


class MatchModule:
    """
    룰카드 매칭 엔진 MVP
    
    Features:
    1. 룰카드 로드 (JSONL)
    2. 트리거 기반 필터링 (trigger/triggers 필드 통일)
    3. 점수화 (IDF + 우선순위)
    4. 섹션별 Top N 선택
    5. Raw JSON 생성 (matched_rule_ids, match_scores, fired_triggers)
    """
    
    def __init__(self):
        self.store: Optional[RuleCardStore] = None
        self.loaded = False
    
    def load_rulecards(self, jsonl_path: str) -> None:
        """
        룰카드 JSONL 로드
        
        Args:
            jsonl_path: JSONL 파일 경로
        """
        if not Path(jsonl_path).exists():
            raise FileNotFoundError(f"룰카드 파일 없음: {jsonl_path}")
        
        self.store = RuleCardStore(jsonl_path)
        self.store.load()
        self.loaded = True
        
        logger.info(f"[MatchModule] 룰카드 로드 완료: {len(self.store.cards)}장")
    
    def match_all_sections(
        self,
        features: SajuFeatures
    ) -> Dict[str, SectionMatch]:
        """
        전체 섹션 매칭
        
        Args:
            features: 사주 특징
        
        Returns:
            Dict[섹션ID, 매칭결과]
        """
        if not self.loaded or not self.store:
            raise RuntimeError("룰카드가 로드되지 않았습니다. load_rulecards()를 먼저 호출하세요.")
        
        logger.info("[MatchModule] 전체 섹션 매칭 시작")
        
        results = {}
        
        # 섹션별 매칭
        for section_id, config in SECTION_CONFIG.items():
            matches = self._match_section(section_id, config, features)
            results[section_id] = matches
            logger.info(f"  - {section_id}: {len(matches.cards)}장, 평균점수: {matches.avg_score:.2f}")
        
        return results
    
    def _match_section(
        self,
        section_id: str,
        config: Dict[str, Any],
        features: SajuFeatures
    ) -> SectionMatch:
        """
        단일 섹션 매칭
        
        Args:
            section_id: 섹션 ID (ELEM, TEN, STRU 등)
            config: 섹션 설정
            features: 사주 특징
        
        Returns:
            SectionMatch: 매칭 결과
        """
        top_n = config["top_n"]
        
        # 1. 트리거 키워드 생성
        trigger_keywords = self._generate_trigger_keywords(section_id, features)
        
        # 2. 카드 필터링 및 점수화
        scored_cards = []
        
        for card in self.store.cards:
            # 토픽 필터링 (섹션과 관련된 토픽만)
            if not self._is_relevant_topic(section_id, card.topic):
                continue
            
            # 트리거 매칭 (개선된 스코어링)
            fired_triggers, score, score_details = self._match_triggers(card, trigger_keywords)
            
            if score > 0:
                scored_cards.append({
                    "card": card,
                    "score": score,
                    "fired_triggers": fired_triggers,
                    "score_details": score_details  # 🔥 점수 상세 저장
                })
        
        # 3. 점수순 정렬 및 Top N 선택
        scored_cards.sort(key=lambda x: x["score"], reverse=True)
        top_cards = scored_cards[:top_n]
        
        # 4. MatchedCard 객체 생성
        matched_cards = [
            MatchedCard(
                card_id=item["card"].id,
                topic=item["card"].topic,
                score=item["score"],
                fired_triggers=item["fired_triggers"],
                interpretation=item["card"].interpretation or "",
                mechanism=item["card"].mechanism,
                action=item["card"].action,
                score_details=item.get("score_details")  # 🔥 점수 상세 추가
            )
            for item in top_cards
        ]
        
        # 5. 평균 점수 계산
        avg_score = sum(c.score for c in matched_cards) / len(matched_cards) if matched_cards else 0.0
        
        return SectionMatch(
            section_id=section_id,
            cards=matched_cards,
            avg_score=avg_score
        )
    
    def _generate_trigger_keywords(
        self,
        section_id: str,
        features: SajuFeatures
    ) -> List[str]:
        """
        섹션별 트리거 키워드 생성 (개선된 버전)
        
        Args:
            section_id: 섹션 ID
            features: 사주 특징
        
        Returns:
            List[str]: 트리거 키워드 목록
        """
        keywords = []
        
        if section_id == "ELEM":
            # 오행 키워드 - 모든 오행 및 조합
            keywords.extend(features.strong_elements)
            keywords.extend(features.weak_elements)
            keywords.append(features.day_master_element)
            
            # 오행 조합 (강한 오행끼리)
            if len(features.strong_elements) >= 2:
                keywords.append(f"{features.strong_elements[0]}{features.strong_elements[1]}")
            
            # 일간 오행 + 다른 오행들
            for elem in features.element_count.keys():
                if elem != features.day_master_element:
                    keywords.append(f"{features.day_master_element}{elem}")
        
        elif section_id == "TEN":
            # 십성 키워드 - 모든 십성 (빈도수 높은 순)
            keywords.append(features.dominant_ten_god)
            # 모든 십성 추가 (상위 10개)
            keywords.extend([tg["name"] for tg in features.ten_gods[:10]])
            
            # 십성 조합
            if len(features.ten_gods) >= 2:
                top_two = [tg["name"] for tg in features.ten_gods[:2]]
                keywords.append(f"{top_two[0]}{top_two[1]}")
        
        elif section_id == "STRU":
            # 구조 키워드
            keywords.append(features.structure)
            
            # 신강/신약
            if features.is_strong_self:
                keywords.append("신강")
            else:
                keywords.append("신약")
            
            # 십성 기반 패턴
            for tengod, count in features.ten_gods_count.items():
                if count >= 2:
                    keywords.append(f"{tengod}다")
                    keywords.append(tengod)
            
            # 주도 십성 + 신강/신약 조합
            strength = "신강" if features.is_strong_self else "신약"
            keywords.append(f"{strength}{features.dominant_ten_god}")
        
        elif section_id == "SURV":
            # 생존 키워드
            keywords.extend(["생존", "안정"])
            
            # 신강/신약 기반
            if features.is_strong_self:
                keywords.extend(["자립", "주도", "독립"])
            else:
                keywords.extend(["협력", "지원", "보완"])
            
            # 오행 기반 특성
            if "금" in features.strong_elements or "금" in features.day_master_element:
                keywords.extend(["방어", "규율"])
            if "수" in features.strong_elements or "수" in features.day_master_element:
                keywords.extend(["적응", "유연"])
            if "목" in features.strong_elements or "목" in features.day_master_element:
                keywords.extend(["성장", "확장"])
            if "화" in features.strong_elements or "화" in features.day_master_element:
                keywords.extend(["표현", "열정"])
            if "토" in features.strong_elements or "토" in features.day_master_element:
                keywords.extend(["균형", "조화"])
        
        elif section_id == "APPL":
            # 응용 키워드
            keywords.append(features.day_master)
            keywords.append(features.day_master_element)
            
            # 일간 + 모든 오행 조합
            for elem in features.element_count.keys():
                keywords.append(f"{features.day_master}{elem}")
            
            # 실전/활용 키워드
            keywords.extend(["실전", "활용", "응용"])
            
            # 구조 기반
            keywords.append(features.structure)
        
        # 중복 제거
        return list(set(keywords))
    
    def _is_relevant_topic(self, section_id: str, topic: str) -> bool:
        """
        섹션과 토픽의 관련성 확인
        
        Args:
            section_id: 섹션 ID
            topic: 카드 토픽
        
        Returns:
            bool: 관련 있으면 True
        """
        # 토픽 매핑
        topic_mapping = {
            "ELEM": ["ELEMENTS", "ELEM"],
            "TEN": ["TEN_GODS", "TEN"],
            "STRU": ["STRUCTURE", "STRU"],
            "SURV": ["GENERAL", "SURV"],
            "APPL": ["GENERAL", "APPL", "CAREER", "WEALTH", "LOVE"]
        }
        
        return topic in topic_mapping.get(section_id, [])
    
    def _match_triggers(
        self,
        card: RuleCard,
        trigger_keywords: List[str]
    ) -> tuple[List[str], float, Dict[str, float]]:
        """
        트리거 매칭 및 점수 계산 (개선된 랭킹 시스템)
        
        **점수 구성**:
        - base_score: Priority (0-10)
        - tag_match_score: 태그 매칭 점수 (IDF 가중치)
        - year_boost: 2026년 관련 부스트
        - goal_match: 목표/관심사 매칭 부스트
        
        Args:
            card: 룰카드
            trigger_keywords: 트리거 키워드 목록
        
        Returns:
            (발화된 트리거 목록, 최종 점수, 점수 상세)
        """
        fired_triggers = []
        
        # 1. Base Score: Priority (0-10)
        base_score = card.priority
        
        # 2. 카드 트리거 추출
        card_triggers = self._extract_card_triggers(card)
        
        # 3. 키워드 매칭
        for keyword in trigger_keywords:
            for card_trigger in card_triggers:
                if keyword in card_trigger or card_trigger in keyword:
                    fired_triggers.append(card_trigger)
        
        # 매칭 실패시 0점
        if not fired_triggers:
            return [], 0.0, {}
        
        # 4. Tag Match Score: IDF 가중치 적용
        idf_score = sum(
            self.store.idf.get(trigger, 1.0)
            for trigger in fired_triggers
        )
        tag_match_score = idf_score / len(fired_triggers) if fired_triggers else 0
        
        # 5. Year Boost: 2026년 관련 키워드
        year_boost = 0.0
        year_keywords = ["2026", "병오", "화", "타이밍"]
        for keyword in year_keywords:
            if any(keyword in t for t in card_triggers):
                year_boost += 1.0
        
        # 6. Goal Match: 비즈니스/커리어 관련 부스트
        goal_boost = 0.0
        goal_keywords = ["career", "business", "money", "wealth", "사업", "재물", "직업"]
        card_text = f"{card.topic} {' '.join(card_triggers)} {card.interpretation or ''}"
        for keyword in goal_keywords:
            if keyword.lower() in card_text.lower():
                goal_boost += 0.5
        
        # 7. 최종 점수 계산
        final_score = (
            base_score * 1.0 +           # Priority 기본 가중치
            tag_match_score * 2.0 +       # Tag Match 중요도 높음
            year_boost * 0.5 +            # Year Boost
            goal_boost * 0.3              # Goal Match
        )
        
        # 점수 상세 (디버깅/추적용)
        score_details = {
            "base_score": base_score,
            "tag_match_score": tag_match_score,
            "year_boost": year_boost,
            "goal_boost": goal_boost,
            "final_score": final_score
        }
        
        return list(set(fired_triggers)), final_score, score_details
    
    def _extract_card_triggers(self, card: RuleCard) -> List[str]:
        """
        카드에서 트리거 추출 (trigger/triggers 필드 통일)
        
        Args:
            card: 룰카드
        
        Returns:
            List[str]: 트리거 목록
        """
        triggers = []
        
        # trigger 필드가 문자열일 경우
        if isinstance(card.trigger, str):
            try:
                parsed = json.loads(card.trigger)
                if isinstance(parsed, list):
                    triggers.extend(parsed)
                elif isinstance(parsed, dict):
                    # dict인 경우 values 추출
                    for v in parsed.values():
                        if isinstance(v, list):
                            triggers.extend(v)
                        elif isinstance(v, str):
                            triggers.append(v)
            except:
                # JSON 파싱 실패시 문자열 그대로 사용
                triggers.append(card.trigger)
        
        # trigger 필드가 리스트일 경우
        elif isinstance(card.trigger, list):
            triggers.extend(card.trigger)
        
        # tags도 트리거로 활용
        if card.tags:
            triggers.extend(card.tags)
        
        return triggers
    
    def generate_raw_json(
        self,
        features: SajuFeatures,
        matches: Dict[str, SectionMatch]
    ) -> Dict[str, Any]:
        """
        Raw JSON 생성 (matched_rule_ids, match_scores, fired_triggers 포함)
        
        Args:
            features: 사주 특징
            matches: 섹션별 매칭 결과
        
        Returns:
            Dict: Raw JSON 데이터
        """
        # 전체 매칭된 카드 ID 목록
        matched_rule_ids = []
        match_scores = {}
        fired_triggers_all = {}
        
        for section_id, section_match in matches.items():
            for card in section_match.cards:
                matched_rule_ids.append(card.card_id)
                match_scores[card.card_id] = card.score
                fired_triggers_all[card.card_id] = card.fired_triggers
        
        raw_json = {
            "features": asdict(features),
            "matched_rule_ids": matched_rule_ids,
            "match_scores": match_scores,
            "fired_triggers": fired_triggers_all,
            "section_matches": {
                section_id: {
                    "cards": [asdict(c) for c in section_match.cards],
                    "avg_score": section_match.avg_score
                }
                for section_id, section_match in matches.items()
            }
        }
        
        return raw_json
    
    def sanitize_content(self, content: str) -> str:
        """
        고객용 콘텐츠 정제 (RC-#### 같은 내부 토큰 제거)
        
        Args:
            content: 원본 콘텐츠
        
        Returns:
            str: 정제된 콘텐츠
        """
        # RC-#### 패턴 제거
        sanitized = re.sub(r'RC-[0-9a-fA-F]{4,}', '', content)
        
        # 내부 메타 정보 제거
        sanitized = re.sub(r'\[INTERNAL:.*?\]', '', sanitized)
        sanitized = re.sub(r'\[DEBUG:.*?\]', '', sanitized)
        
        # 공백 정리
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        return sanitized


# 싱글톤 인스턴스
match_module = MatchModule()
