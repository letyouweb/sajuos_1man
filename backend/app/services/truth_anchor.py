"""
truth_anchor.py
Dynamic Truth Anchor for premium reports.
Prevents LLM hallucinations by explicitly declaring allowed/forbidden stems/branches.

🔥 P0 FIX: "실패 처리됨" 톤 제거 → "대체 출력" 방식으로 변경
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
    - "0" 또는 미설정 (기본): 빈 리스트 반환 (필터 OFF)
    - "1": 오타 토큰만 반환 (걸록, 걸록격)
    """
    filter_enabled = os.getenv("RULECARD_PHYSICAL_FILTER", "0") == "1"
    
    if not filter_enabled:
        return []  # 필터 비활성화
    
    return sorted(_STATIC_FORBIDDEN_TOKENS)


def build_truth_anchor(
    saju_data: Dict[str, Any],
    target_year: Optional[int] = None,
    section_id: Optional[str] = None,
    **kwargs,
) -> str:
    """
    Dynamic truth anchor injected into prompts.
    
    🔥 P0 FIX: 
    - "실패 처리됨" 톤 제거
    - "대체 출력" 방식 적용 (정보 없으면 가정/보완 전략으로 계속 작성)
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
    
    # 재성/식상 결핍 여부
    is_missing_jaesung = summary.get("is_missing_jaesung", False)
    is_missing_shiksang = summary.get("is_missing_shiksang", False)

    # section/year context
    section_str = f"섹션: {section_id} / " if section_id else ""
    year_str = f"목표 연도: {target_year}" if target_year else "목표 연도: (미지정)"

    return f"""## 📌 원국 데이터 (Ground Truth)
- {section_str}{year_str}

### 원국 4주
- 년주: {year_pillar}
- 월주: {month_pillar}
- 일주: {day_pillar}
- 시주: {hour_pillar}
- (허용 글자: {allowed_preview})

### 확인된 십성/오행
- 십성: {', '.join(ten_present) if ten_present else '(미제공 - 일반 전략으로 작성)'}
- 오행: {', '.join(elements_present) if elements_present else '(미제공 - 일반 전략으로 작성)'}
- 격국: {primary_structure or '(미제공 - 일반 격국으로 가정)'}
- 월지 십성: {month_branch_ten_god or '(미제공)'}

### 결핍 정보 (대체 전략 필요)
- 재성 결핍: {'예 → "현금흐름 보완 전략"으로 서술' if is_missing_jaesung else '아니오'}
- 식상 결핍: {'예 → "마케팅/표현력 강화"로 서술' if is_missing_shiksang else '아니오'}

### 작성 규칙 (출력 지속)
1) **원국 외 간지 단정 금지**: 위 4주에 없는 천간/지지를 "있다"고 단정하지 마라.
2) **미확인 데이터 처리**: 정보가 없으면 "(미확인)" 또는 "[가정]" 표기 후 일반 전략으로 계속 작성.
3) **결핍 대체 서술**: 재성/식상이 없어도 "보완 전략/운영 방안"으로 현금흐름/마케팅을 말할 수 있음.
4) **오타 방지**: '걸록격' → '건록격'으로 올바르게 표기.
5) **거절 금지**: "정보 부족", "작성 불가" 등 거절 문구 없이 반드시 작성 완료.

⚠️ 중요: 불확실한 부분이 있어도 "[가정]" 표기하고 작성을 계속한다. 질문은 본문 맨 끝에만 추가.
""".strip()


__all__ = ["build_truth_anchor", "forbidden_words_for_rulecards"]
