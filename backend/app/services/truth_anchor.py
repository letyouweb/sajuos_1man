"""
truth_anchor.py
Dynamic Truth Anchor for premium reports.
Prevents LLM hallucinations by explicitly declaring allowed/forbidden stems/branches.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# 천간/지지 전체 글자셋 (참조용)
_ALL_STEMS = set(list("갑을병정무기경신임계"))
_ALL_BRANCHES = set(list("자축인묘진사오미신유술해"))
_ALL_STEMS_BRANCHES = _ALL_STEMS | _ALL_BRANCHES

# 🔥 P0: 오타 토큰 (필터 활성화 시에만 사용)
_STATIC_FORBIDDEN_TOKENS = {"걸록격", "걸록"}


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
    """
    🔥 P0 FIX: RuleCard 물리적 차단용 금지어 - ENV로 토글
    
    ENV: RULECARD_PHYSICAL_FILTER
    - "0" 또는 미설정 (기본값): 빈 리스트 반환 (필터 OFF)
    - "1": 오타 토큰만 반환 (걸록, 걸록격)
    
    운영 환경에서는 기본 OFF로 두고, 필요 시에만 활성화.
    LLM 환각 방지는 Truth Anchor 프롬프트에서 처리함.
    """
    # ENV 토글: 기본 OFF
    filter_enabled = os.getenv("RULECARD_PHYSICAL_FILTER", "0") == "1"
    
    if not filter_enabled:
        return []  # 필터 비활성화
    
    # 필터 활성화 시: 오타 토큰만 반환
    return sorted(_STATIC_FORBIDDEN_TOKENS)


def build_truth_anchor(
    saju_data: Dict[str, Any],
    target_year: Optional[int] = None,
    section_id: Optional[str] = None,
    **kwargs,
) -> str:
    """
    Dynamic truth anchor injected into prompts.
    
    🔥 P0 FIX: "금지 글자" 규칙 제거
    → "원국 4주에 제공된 간지 외 추가 생성 금지"로 변경
    
    Parameters:
        saju_data: 사주 데이터 dict (year_pillar, month_pillar 등 포함)
        target_year: 목표 연도 (예: 2026)
        section_id: 섹션 ID (optional)
    """
    saju_data = saju_data or {}

    # 원국 4주 추출
    year_pillar = saju_data.get("year_pillar") or "(미제공)"
    month_pillar = saju_data.get("month_pillar") or "(미제공)"
    day_pillar = saju_data.get("day_pillar") or "(미제공)"
    hour_pillar = saju_data.get("hour_pillar") or "(미제공)"
    
    # 허용된 글자 (참조용)
    allowed = sorted(_extract_allowed_chars(saju_data))
    allowed_preview = ", ".join(allowed) if allowed else "(추출 불가)"

    # saju_summary에서 데이터 추출
    summary = saju_data.get("saju_summary") or {}
    if not isinstance(summary, dict):
        summary = {}

    ten_present = summary.get("ten_gods_present") or []
    elements_count = summary.get("elements_count") or {}
    elements_present = [k for k, v in elements_count.items() if isinstance(v, (int, float)) and v > 0]

    allowed_structures = summary.get("allowed_structure_names") or []
    primary_structure = summary.get("primary_structure") or saju_data.get("primary_structure") or ""

    month_branch_ten_god = (
        saju_data.get("month_branch_ten_god") or 
        saju_data.get("month_ten_god") or 
        saju_data.get("month_tengod") or 
        ""
    )

    # section/year context
    section_str = f"섹션: {section_id} / " if section_id else ""
    year_str = f"목표 연도: {target_year}" if target_year else "목표 연도: (미지정)"

    return f"""## 🚨 ZERO TOLERANCE RULES (절대 준수)
- {section_str}{year_str}

### 원국 4주 (Ground Truth)
- 년주: {year_pillar}
- 월주: {month_pillar}
- 일주: {day_pillar}
- 시주: {hour_pillar}
- (허용 글자: {allowed_preview})

### 절대 금지 사항
1) **원국 외 간지 생성 금지**: 위 4주에 없는 천간/지지를 원국에 "있다"고 단정하지 마라.
2) **지장간/숨은 글자 추론 금지**: 지장간이나 숨은 오행으로 "있다"고 확대 해석 금지.
3) **오타 금지**: '걸록격' → '건록격'으로 올바르게 표기.
4) **월지 십성 고정**: 엔진 제공 월지 십성 = `{month_branch_ten_god or '(미제공)'}` (미제공이면 단정 금지)

### 데이터 정합성
- '있다'고 단정 가능한 십성: {', '.join(ten_present) if ten_present else '(엔진 미제공)'}
- 실제 존재하는 오행: {', '.join(elements_present) if elements_present else '(엔진 미제공)'}
- 허용된 격국: {', '.join(allowed_structures[:10]) if allowed_structures else '(엔진 미제공)'}
- 최우선 격국: {primary_structure or '(엔진 미제공)'}

[중요] 위 원국 4주에 없는 간지를 원국에 있는 것처럼 서술하면 실패 처리됨.
""".strip()


__all__ = ["build_truth_anchor", "forbidden_words_for_rulecards"]
