"""
truth_anchor.py
- Dynamic Truth Anchor generator to prevent LLM hallucinations.
- Keeps the model in "writer" role: it may only paraphrase engine facts + selected rulecards.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple


# --- utilities ----------------------------------------------------------------

def _safe_str(v: Any) -> str:
    return "" if v is None else str(v)

def _chars_from_pillar(p: str) -> Set[str]:
    """
    Pillar strings can be like '무오', '정사', '기유' etc.
    We treat each Korean char as a "fact token".
    """
    p = _safe_str(p).strip()
    return set(p) if p else set()

def _extract_allowed_chars(saju_data: Dict[str, Any]) -> Set[str]:
    allowed: Set[str] = set()
    for k in ("year_pillar", "month_pillar", "day_pillar", "hour_pillar"):
        allowed |= _chars_from_pillar(saju_data.get(k, ""))
    return allowed

def _extract_present_sets(saju_data: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """
    Returns (ten_gods_present, elements_present) from saju_summary if available.
    """
    summary = saju_data.get("saju_summary") or {}
    ten_gods_present = summary.get("ten_gods_present") or saju_data.get("ten_gods_present") or []
    elements_count = summary.get("elements_count") or {}
    elements_present = [k for k, v in elements_count.items() if isinstance(v, (int, float)) and v > 0]
    # ensure list[str]
    ten_gods_present = [str(x) for x in ten_gods_present if x is not None]
    elements_present = [str(x) for x in elements_present if x is not None]
    return ten_gods_present, elements_present


# --- public API ----------------------------------------------------------------

def forbidden_words_for_rulecards() -> List[str]:
    """
    P0 forbidden strings that frequently cause hallucination or obvious wrong claims.
    (We keep it short to avoid over-filtering.)
    """
    return [
        "자수",
        "을목",
        "병화",
        "걸록",
        "관성 충돌",
        "비견이 월지",
        "월지 비견",
        "병화가 많",
        "을목이 강",
    ]


def build_truth_anchor(
    saju_data: Dict[str, Any],
    *,
    target_year: Optional[int] = None,
    force_gyeok: Optional[str] = None,
    force_month_tengod: Optional[str] = None,
) -> str:
    """
    Build a strict, dynamic "truth anchor" block.
    This is meant to be inserted at the TOP of system prompts.
    """
    allowed_chars = sorted(_extract_allowed_chars(saju_data))
    ten_gods_present, elements_present = _extract_present_sets(saju_data)

    # known hard constraints (user complaints)
    hard_forbidden = ["자(子)", "을(乙)", "병(丙)", "걸록격"]
    month_pillar = _safe_str(saju_data.get("month_pillar"))
    day_master = _safe_str(saju_data.get("day_master"))
    # If the engine already computed a month ten-god, pass it; else keep generic.
    month_tengod = force_month_tengod or _safe_str(saju_data.get("month_tengod"))  # optional

    gyeok = force_gyeok or _safe_str(saju_data.get("primary_structure"))  # optional

    year_line = f"{target_year}년" if isinstance(target_year, int) else "해당 연도"

    return f"""
## 🚨 ZERO TOLERANCE RULES (절대 준수 / 위반=실패)

### 0) 너의 역할
- 너는 **명리학자가 아니다.** 너는 엔진이 준 '팩트 + 룰카드'를 **비즈니스 문장으로 편집**하는 작가다.
- **추론/창조 금지**: 제공 데이터에 없는 오행/십성/격국/충합/지장간을 네 지식으로 만들지 마라.

### 1) 사실 고정 (엔진 확정)
- 원국(연/월/일/시): {saju_data.get("year_pillar","")}/{saju_data.get("month_pillar","")}/{saju_data.get("day_pillar","")}/{saju_data.get("hour_pillar","")}
- 일간: {day_master}
- 월주: {month_pillar}
- (가능하면) 격국: {gyeok or "엔진값이 없으면 '격국' 단정 금지"}
- (가능하면) 월지 십성: {month_tengod or "엔진값이 없으면 단정 금지"}

### 2) 존재/비존재 규칙
- **이 보고서에서 사용 가능한 글자(원국에 실제로 존재):** {allowed_chars}
- 아래는 대표 금지 예시다: {hard_forbidden}
- 위 '사용 가능한 글자' 목록에 없는 글자/십성/오행은 **'있다'고 말하면 안 된다.**

### 3) Ground Truth (정답지)
- 오행 존재: {elements_present if elements_present else "saju_summary 없으면 단정 금지"}
- 십성 존재: {ten_gods_present if ten_gods_present else "saju_summary 없으면 단정 금지"}

### 4) 용어 강제
- 반드시 **'건록격(建祿格)'** 표기를 사용하라. **'걸록격'은 오타**이며 사용 금지.
- {year_line} 관련 문장은 **{year_line}** 기준으로만 쓴다. 다른 연도(특히 2025 등)로 바꿔치기 금지.

### 5) 출력 규칙
- 문장 톤: 단호/실무/전략.
- 근거 구조: (원국/룰카드 구조) → (현장에서의 발현) → (실행 액션).
""".strip()


__all__ = ["build_truth_anchor", "forbidden_words_for_rulecards"]
