"""
truth_anchor.py
Dynamic Truth Anchor for premium reports.
Prevents LLM hallucinations by explicitly declaring allowed/forbidden stems/branches.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# 천간/지지 전체 글자셋
_ALL_STEMS_BRANCHES: Set[str] = set(list("갑을병정무기경신임계자축인묘진사오미신유술해"))

# 흔한 오타/환각 유발 토큰(고정)
_STATIC_FORBIDDEN_TOKENS = {
    "걸록격", "걸록",  # 건록격 오타
}


def _extract_allowed_chars(saju_data: Dict[str, Any]) -> Set[str]:
    """사주 원국에서 실제로 등장하는 천간/지지 글자 추출"""
    y = saju_data.get("year_pillar") or ""
    m = saju_data.get("month_pillar") or ""
    d = saju_data.get("day_pillar") or ""
    h = saju_data.get("hour_pillar") or ""

    pillars = [p for p in (y, m, d, h) if isinstance(p, str) and p]
    joined = "".join(pillars)
    return {ch for ch in joined if ch in _ALL_STEMS_BRANCHES}


def forbidden_words_for_rulecards(saju_data: Dict[str, Any]) -> List[str]:
    """Return a conservative forbidden-token list for physical rulecard blocking.

    - Always blocks known typos like 걸록격
    - Additionally blocks common hallucinated stem/branch words that are NOT present in the chart
      (e.g., "자수", "을목")

    Note: This is intentionally conservative; it targets only obvious tokens.
    """
    saju_data = saju_data or {}
    allowed = _extract_allowed_chars(saju_data)

    # Map a few frequent patterns into concrete forbidden tokens if those stems/branches are absent.
    stem_word = {
        "갑": "갑목", "을": "을목", "병": "병화", "정": "정화", "무": "무토",
        "기": "기토", "경": "경금", "신": "신금", "임": "임수", "계": "계수",
    }
    branch_word = {
        "자": "자수", "축": "축토", "인": "인목", "묘": "묘목", "진": "진토",
        "사": "사화", "오": "오화", "미": "미토", "신": "신금", "유": "유금",
        "술": "술토", "해": "해수",
    }

    candidates = []
    for ch, w in {**stem_word, **branch_word}.items():
        if ch not in allowed:
            candidates.append(w)

    # reduce to a small set to avoid overblocking
    forbidden = set(_STATIC_FORBIDDEN_TOKENS)
    forbidden.update(candidates)

    return sorted(forbidden)


def build_truth_anchor(
    saju_data: Dict[str, Any],
    target_year: Optional[int] = None,
    section_id: Optional[str] = None,
    **kwargs,  # 호환성을 위해 추가 인자 무시
) -> str:
    """Dynamic truth anchor injected into prompts.

    - Only allow stems/branches that appear in the chart
    - Forbid explicitly mentioning absent stems/branches
    - Forbid inventing ten-gods/elements/structures not present in saju_summary

    Parameters:
        saju_data: 사주 데이터 dict (year_pillar, month_pillar 등 포함)
        target_year: 목표 연도 (예: 2026)
        section_id: 섹션 ID (optional)
        **kwargs: 호환성을 위한 추가 인자 (무시됨)
    """
    saju_data = saju_data or {}

    allowed = sorted(_extract_allowed_chars(saju_data))
    allowed_set = set(allowed)
    forbidden = sorted([ch for ch in _ALL_STEMS_BRANCHES if ch not in allowed_set])

    allowed_preview = "".join(allowed) if allowed else "(unknown)"
    forbidden_preview = "".join(forbidden[:14]) + ("…" if len(forbidden) > 14 else "")

    summary = saju_data.get("saju_summary") or {}
    if not isinstance(summary, dict):
        summary = {}

    ten_present = summary.get("ten_gods_present") or []
    elements_count = summary.get("elements_count") or {}
    elements_present = [k for k, v in elements_count.items() if isinstance(v, (int, float)) and v > 0]

    allowed_structures = summary.get("allowed_structure_names") or []
    primary_structure = summary.get("primary_structure") or saju_data.get("primary_structure") or ""

    month_branch_ten_god = saju_data.get("month_branch_ten_god") or saju_data.get("month_ten_god") or saju_data.get("month_tengod") or ""

    # Safety: show a couple of forbidden examples (word-form) to reduce hallucinations
    forbidden_words = forbidden_words_for_rulecards(saju_data)
    example_words = ", ".join(forbidden_words[:6]) if forbidden_words else "(none)"

    # section/year context
    section_str = f"섹션: {section_id} / " if section_id else ""
    year_str = f"목표 연도: {target_year}" if target_year else "목표 연도: (미지정)"

    return f"""## 🚨 ZERO TOLERANCE RULES (절대 준수)
- {section_str}{year_str}

1) **허용 글자만 언급**: 이 원국에서 언급 가능한 천간/지지 = [{allowed_preview}] 뿐이다.
2) **금지 글자 언급 금지**: [{forbidden_preview}] 및 허용 밖 글자는 절대 언급하지 마라.
3) **상상 금지**: 지장간/숨은 글자/추론으로 '있다'고 단정 금지.
4) **오타 금지**: '걸록격' 사용 금지. (건록격으로 표기)
5) **월지 십성 고정**: 엔진 제공 월지 십성 = `{month_branch_ten_god or '(미제공)'}` (미제공이면 단정 금지)
6) **데이터 정합성**
   - '있다'고 단정 가능한 십성: {', '.join(ten_present) if ten_present else '(none)'}
   - 실제로 존재하는 오행: {', '.join(elements_present) if elements_present else '(unknown)'}
   - 허용된 격국: {', '.join(allowed_structures[:12]) if allowed_structures else '(unknown)'}
   - 최우선 격국: {primary_structure or '(unknown)'}

[룰카드 차단 예시 토큰]
- 다음 같은 토큰은 (원국에 없으면) 사용 금지: {example_words}
""".strip()


__all__ = ["build_truth_anchor", "forbidden_words_for_rulecards"]
