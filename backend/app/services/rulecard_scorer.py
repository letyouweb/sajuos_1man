﻿"""
RuleCard Scorer v5 - P0 섹션 ID 정합 + 인터페이스 확정
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 섹션 ID는 고정된 목록(ALLOWED_SECTION_IDS)만 허용
- 카드 스코어링 인터페이스를 ReportWorker와 1:1로 맞춤
- P0: 원국 기반 철벽 필터링 (원국에 없는 오행 카드 제외)
- P0: 십성(원국/대운) 기반 철벽 필터링 (원국/대운에 없는 십성 카드 제외)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple, TypedDict

logger = logging.getLogger(__name__)


class SectionCards(TypedDict):
    """섹션별 선택 결과"""
    section_id: str
    cards: List[Dict[str, Any]]
    match_summary: Dict[str, Any]


# 허용되는 섹션 ID (P0 고정)
ALLOWED_SECTION_IDS = {
    "exec",
    "money",
    "business",
    "team",
    "health",
    "calendar",
    "sprint",
}

# 오행 표준화 (원국에 포함 여부 체크)
ELEMENT_CHARS = {
    "wood": ["갑", "을", "인", "묘"],
    "fire": ["병", "정", "사", "오"],
    "earth": ["무", "기", "진", "술", "축", "미"],
    "metal": ["경", "신", "신", "유"],
    "water": ["임", "계", "해", "자"],
}

# 섹션별 가중 태그
SECTION_WEIGHT_TAGS = {
    "exec": ["전체운", "종합", "핵심", "요약", "일간", "성향", "대운"],
    "money": ["정재", "편재", "재성", "재물", "현금", "매출", "투자", "손실"],
    "business": ["정관", "편관", "사업", "창업", "경영", "리더십", "계약", "거래"],
    "team": ["비겁", "비견", "겁재", "동업", "파트너", "직원", "관계", "협력"],
    "health": ["건강", "에너지", "스트레스", "번아웃", "체력", "질병", "휴식", "관성"],
    "calendar": ["월운", "시기", "계절", "타이밍", "길일", "흉일", "절기"],
    "sprint": ["실행", "액션", "계획", "목표", "KPI", "마일스톤", "주간"],
}


def get_survey_tag_weights(survey_data: Optional[Dict] = None) -> Dict[str, float]:
    """
    설문 데이터를 기반으로 가중치 맵 생성
    (현재는 최소 구현: 확장 가능)
    """
    if not survey_data:
        return {}

    weights: Dict[str, float] = {}

    # 예: concern_type 기반 가중치 부여
    concern_type = (survey_data.get("concern_type") or "").lower()
    if concern_type:
        weights[concern_type] = 1.2

    # 예: direction / goal / channel 등을 확장 가능
    for k, v in (survey_data.items() if isinstance(survey_data, dict) else []):
        if isinstance(v, str) and v.strip():
            weights[v.strip().lower()] = 1.1

    return weights


def get_present_elements(saju_data: Dict[str, Any]) -> Set[str]:
    """
    saju_data에서 원국 오행(wood/fire/earth/metal/water) 존재 여부 추출
    - year/month/day/hour pillar의 한글 천간/지지 문자열로 존재 판정
    """
    if not saju_data:
        return set()

    pillars = " ".join([
        saju_data.get("year_pillar", ""),
        saju_data.get("month_pillar", ""),
        saju_data.get("day_pillar", ""),
        saju_data.get("hour_pillar", ""),
    ])

    present = set()
    for element, chars in ELEMENT_CHARS.items():
        if any(ch in pillars for ch in chars):
            present.add(element)

    return present


def should_exclude_card(card: dict, present_elements: Set[str]) -> bool:
    """
    원국에 없는 오행 관련 카드인지 확인
    - 카드 텍스트/태그에 특정 오행 요소가 '강하게' 명시되어 있는데 원국에 그 오행이 없으면 제외
    """
    if not present_elements:
        return False

    # 카드에서 텍스트 추출
    title = str(card.get("title") or "")
    summary = str(card.get("summary") or "")
    body = str(card.get("body") or "")
    body_md = str(card.get("body_markdown") or "")
    tags = " ".join(card.get("tags") or [])
    txt = f"{title} {summary} {body} {body_md} {tags}"

    # 오행 키워드가 나오면 (원국에 없을 때) 제외
    # (예: "수기운이 강하다", "금이 과다" 같은 내용)
    # NOTE: 넓게 잡으면 과다 제외될 수 있어, 여기선 비교적 보수적으로 단어 포함만 체크
    for element, chars in ELEMENT_CHARS.items():
        if element in present_elements:
            continue
        if any(ch in txt for ch in chars):
            return True

    return False


class RuleCardScorer:
    """
    RuleCard Scorer (P0 인터페이스)
    """

    def score_cards_for_section(
        self,
        all_cards: List[Dict[str, Any]],
        section_id: str,
        feature_tags: List[str],
        survey_data: Optional[Dict] = None,
        existing_topics: Set[str] = None,
        saju_data: Optional[Dict] = None  # 🔥 P0: 철벽 필터링용
    ) -> SectionCards:
        """
        섹션별 카드 스코어링 (P0 인터페이스)
        """
        # P0: 섹션 ID 검증
        if section_id not in ALLOWED_SECTION_IDS:
            logger.warning(f"[Scorer] Invalid section_id: {section_id} - using default scoring")

        existing_topics = existing_topics or set()

        feature_set = set(feature_tags) if feature_tags else set()
        survey_weights = get_survey_tag_weights(survey_data)
        section_tags = set(SECTION_WEIGHT_TAGS.get(section_id, []))

        # 🔥 P0: 십성(원국/대운) 기반 철벽 필터링
        # - 카드 내용에 특정 십성이 명시되어 있는데, 원국(+현재대운)에 그 십성이 없으면 제외
        TENGOD_KEYWORDS = ["비견", "겁재", "식신", "상관", "편재", "정재", "편관", "정관", "편인", "정인", "재성", "관성", "인성", "식상"]
        allowed_tg: Set[str] = set()
        if saju_data:
            allowed_tg |= set(saju_data.get("ten_gods_present") or [])
            allowed_tg |= set(saju_data.get("daeun_ten_gods") or [])

        def _card_text(c: Dict[str, Any]) -> str:
            # NOTE: 한글 키워드가 많아서 lower()는 의미 없지만, 영어 혼합 대비로만 사용
            parts = [
                str(c.get("title", "")),
                str(c.get("summary", "")),
                str(c.get("body", "")),
                str(c.get("body_markdown", "")),
                " ".join(c.get("tags") or []),
            ]
            return " ".join(parts)

        def _disallowed_tengod(c: Dict[str, Any]) -> bool:
            if not allowed_tg:
                return False
            txt = _card_text(c)
            hits = [k for k in TENGOD_KEYWORDS if k in txt]
            if not hits:
                return False

            # "재성"은 (정재/편재)로도 간주
            if "재성" in hits:
                hits += ["정재", "편재"]

            for h in hits:
                # 상위 개념 키워드는 패스 (원국 매칭이 애매)
                if h in ["재성", "관성", "인성", "식상"]:
                    continue
                if h not in allowed_tg:
                    return True
            return False

        # 🔥 P0: 원국 철벽 필터링
        present_elements = get_present_elements(saju_data) if saju_data else set()
        filtered_cards: List[Dict[str, Any]] = []
        excluded_count = 0
        excluded_tg_count = 0

        for card in all_cards:
            if present_elements and should_exclude_card(card, present_elements):
                excluded_count += 1
                continue
            if _disallowed_tengod(card):
                excluded_tg_count += 1
                continue
            filtered_cards.append(card)

        if excluded_count > 0:
            logger.info(f"[Scorer] 🔥 철벽 필터: {excluded_count}장 제외 (원국에 없는 오행)")
        if excluded_tg_count > 0:
            logger.info(f"[Scorer] 🔥 철벽 필터: {excluded_tg_count}장 제외 (원국/대운에 없는 십성)")

        scored_cards: List[Tuple[float, Dict[str, Any]]] = []

        for card in filtered_cards:
            score = 0.0

            # 기본 점수: feature tag 매칭
            card_tags = set(card.get("tags") or [])
            common = feature_set & card_tags
            if common:
                score += 2.0 * len(common)

            # 섹션 태그 가중
            common_section = section_tags & card_tags
            if common_section:
                score += 1.5 * len(common_section)

            # 설문 기반 가중 (간단)
            for k, w in survey_weights.items():
                if k and (k in (card.get("title") or "").lower() or k in (card.get("summary") or "").lower()):
                    score += (w - 1.0) * 2.0

            # 기존 토픽 중복 패널티
            topic = (card.get("topic") or "").strip()
            if topic and topic in existing_topics:
                score -= 2.0

            # 길이/품질 보정 (body_markdown 우선)
            body_text = (card.get("body_markdown") or card.get("body") or "")
            if isinstance(body_text, str) and len(body_text) > 400:
                score += 0.4
            if isinstance(body_text, str) and len(body_text) > 900:
                score += 0.4

            scored_cards.append((score, card))

        # top_k 선별
        scored_cards.sort(key=lambda x: x[0], reverse=True)
        selected = [c for _, c in scored_cards[: max(1, min(120, len(scored_cards)))]]

        # match_summary 생성
        avg_score = round(sum(s for s, _ in scored_cards[: len(selected)]) / max(1, len(selected)), 2) if scored_cards else 0.0
        match_summary = {
            "section": section_id,
            "pool": len(all_cards),
            "filtered_pool": len(filtered_cards),
            "selected": len(selected),
            "avg_score": avg_score,
            "excluded_by_fact_check": excluded_count,
            "excluded_by_tengod": excluded_tg_count,
        }

        logger.info(f"[Scorer] section={section_id} | pool={len(all_cards)} | selected={len(selected)} | avg_score={avg_score}")

        return {
            "section_id": section_id,
            "cards": selected,
            "match_summary": match_summary,
        }
