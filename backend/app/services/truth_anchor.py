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
    survey_data: Optional[Dict[str, Any]] = None,  # 🔥 survey_data 추가
    **kwargs,
) -> str:
    """
    Dynamic truth anchor injected into prompts.
    
    🔥 P0 FIX: 
    - "실패 처리됨" 톤 제거
    - "대체 출력" 방식 적용 (정보 없으면 가정/보완 전략으로 계속 작성)
    - survey_data 포함 (비즈니스 병목/투입시간)
    """
    saju_data = saju_data or {}
    survey_data = survey_data or {}

    # 원국 4주 추출
    year_pillar = saju_data.get("year_pillar") or ""
    month_pillar = saju_data.get("month_pillar") or ""
    day_pillar = saju_data.get("day_pillar") or ""
    hour_pillar = saju_data.get("hour_pillar") or ""
    
    # 허용된 글자 (참조용)
    allowed = sorted(_extract_allowed_chars(saju_data))
    allowed_preview = ", ".join(allowed) if allowed else "(계산 누락)"

    # saju_summary에서 데이터 추출
    summary = saju_data.get("saju_summary") or {}
    if not isinstance(summary, dict):
        summary = {}

    # 🔥 팩트 앵커 텍스트 생성 (핵심)
    fact_anchor_text = build_fact_anchor_text(saju_data, survey_data)

    ten_present = summary.get("ten_gods_present") or []
    elements_count = summary.get("elements_count") or {}
    elements_present = [k for k, v in elements_count.items() if isinstance(v, (int, float)) and v > 0]

    allowed_structures = summary.get("allowed_structure_names") or []
    primary_structure = summary.get("primary_structure") or saju_data.get("primary_structure") or ""

    month_branch_ten_god = (
        saju_data.get("month_branch_ten_god") or 
        saju_data.get("month_ten_god") or 
        saju_data.get("month_tengod") or 
        summary.get("month_branch_ten_god") or
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

{fact_anchor_text}

### 작성 규칙 (출력 지속)
1) **원국 외 간지 단정 금지**: 위 4주에 없는 천간/지지를 "있다"고 단정하지 마라.
2) **미확인 데이터 처리**: 정보가 없으면 해당 항목 생략하고 일반 전략으로 계속 작성.
3) **결핍 대체 서술**: 재성/식상이 없어도 "보완 전략/운영 방안"으로 현금흐름/마케팅을 말할 수 있음.
4) **오타 방지**: '걸록격' → '건록격'으로 올바르게 표기.
5) **거절 금지**: "정보 부족", "작성 불가" 등 거절 문구 없이 반드시 작성 완료.

⚠️ 중요: 불확실한 부분이 있어도 생략하고 작성을 계속한다. 질문은 본문 맨 끝에만 추가.
""".strip()


def build_fact_anchor_text(
    saju_data: Dict[str, Any],
    survey_data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    🔥🔥🔥 P0: 팩트 앵커 텍스트 서버에서 생성
    
    - LLM이 계산하지 않고 이 텍스트만 참조하도록 함
    - "(미확인)" 대신 "데이터 없음(입력/계산 누락)" 명시
    - survey_data의 비즈니스 정보도 포함
    """
    saju_data = saju_data or {}
    survey_data = survey_data or {}
    
    # saju_summary 추출
    summary = saju_data.get("saju_summary") or {}
    if not isinstance(summary, dict):
        summary = {}
    
    # === 원국 4주 ===
    year_pillar = saju_data.get("year_pillar") or "데이터 없음(입력 누락)"
    month_pillar = saju_data.get("month_pillar") or "데이터 없음(입력 누락)"
    day_pillar = saju_data.get("day_pillar") or "데이터 없음(입력 누락)"
    hour_pillar = saju_data.get("hour_pillar") or "시간 미입력"
    
    # 허용 글자
    allowed = sorted(_extract_allowed_chars(saju_data))
    allowed_str = ", ".join(allowed) if allowed else "계산 누락"
    
    # === 일간 정보 ===
    day_master = summary.get("day_master") or saju_data.get("day_master") or ""
    day_master_element = summary.get("day_master_element") or saju_data.get("day_master_element") or ""
    
    if day_master and day_master_element:
        day_master_str = f"{day_master}({day_master_element})"
    elif day_master:
        day_master_str = day_master
    else:
        day_master_str = "데이터 없음(계산 누락)"
    
    # === 오행 분포 ===
    elements_count = summary.get("elements_count") or {}
    if elements_count:
        elements_lines = []
        for elem in ["목", "화", "토", "금", "수"]:
            cnt = elements_count.get(elem, 0)
            elements_lines.append(f"{elem}({cnt})")
        elements_str = ", ".join(elements_lines)
    else:
        elements_str = "데이터 없음(계산 누락)"
    
    elements_present = summary.get("elements_present") or [k for k, v in elements_count.items() if v > 0]
    elements_present_str = ", ".join(elements_present) if elements_present else "없음"
    
    # === 십성 분포 ===
    ten_gods_present = summary.get("ten_gods_present") or []
    ten_gods_str = ", ".join(ten_gods_present) if ten_gods_present else "데이터 없음(계산 누락)"
    
    ten_gods_distribution = summary.get("ten_gods_distribution") or {}
    if ten_gods_distribution:
        dist_lines = []
        for grp in ["비겁", "식상", "재성", "관성", "인성"]:
            cnt = ten_gods_distribution.get(grp, 0)
            dist_lines.append(f"{grp}({cnt})")
        ten_gods_dist_str = ", ".join(dist_lines)
    else:
        ten_gods_dist_str = "데이터 없음(계산 누락)"
    
    # === 격국 정보 ===
    primary_structure = summary.get("primary_structure") or saju_data.get("primary_structure") or ""
    primary_structure_str = primary_structure if primary_structure else "데이터 없음(계산 누락)"
    
    # 월지 십성
    month_branch_ten_god = (
        saju_data.get("month_branch_ten_god") or
        saju_data.get("month_ten_god") or
        summary.get("month_branch_ten_god") or
        ""
    )
    # ten_gods_list에서 월지 찾기
    if not month_branch_ten_god:
        for tg_info in summary.get("ten_gods_list", []):
            if tg_info.get("position") == "월지":
                month_branch_ten_god = tg_info.get("ten_god", "")
                break
    
    month_branch_str = month_branch_ten_god if month_branch_ten_god else "데이터 없음(계산 누락)"
    
    # === 결핍 정보 ===
    is_missing_jaesung = summary.get("is_missing_jaesung", False)
    is_missing_shiksang = summary.get("is_missing_shiksang", False)
    is_missing_gwansung = summary.get("is_missing_gwansung", False)
    is_missing_insung = summary.get("is_missing_insung", False)
    
    missing_list = []
    if is_missing_jaesung:
        missing_list.append("재성(현금흐름 보완 전략 필요)")
    if is_missing_shiksang:
        missing_list.append("식상(마케팅/표현력 강화 필요)")
    if is_missing_gwansung:
        missing_list.append("관성(조직/권위 보완 필요)")
    if is_missing_insung:
        missing_list.append("인성(학습/지원 확보 필요)")
    
    missing_str = ", ".join(missing_list) if missing_list else "없음"
    
    # === Survey 비즈니스 정보 ===
    pain_point = survey_data.get("painPoint") or survey_data.get("pain_point") or survey_data.get("고민") or ""
    business_goal = survey_data.get("businessGoal") or survey_data.get("goal") or survey_data.get("목표") or ""
    time_available = survey_data.get("time") or survey_data.get("timeAvailable") or survey_data.get("투입시간") or ""
    industry = survey_data.get("industry") or survey_data.get("업종") or ""
    
    survey_section = ""
    if pain_point or business_goal or time_available or industry:
        survey_lines = ["### 비즈니스 컨텍스트"]
        if industry:
            survey_lines.append(f"- 업종: {industry}")
        if pain_point:
            survey_lines.append(f"- 핵심 병목: {pain_point}")
        if business_goal:
            survey_lines.append(f"- 목표: {business_goal}")
        if time_available:
            survey_lines.append(f"- 투입 가능 시간: {time_available}")
        survey_section = "\n".join(survey_lines)
    
    # === 최종 조립 ===
    return f"""### 원국 4주 (정답)
- 년주: {year_pillar}
- 월주: {month_pillar}
- 일주: {day_pillar}
- 시주: {hour_pillar}
- 허용 글자: {allowed_str}

### 일간 (나)
- 일간: {day_master_str}

### 오행 분포 (정답)
- 분포: {elements_str}
- 존재 오행: {elements_present_str}

### 십성 분포 (정답)
- 존재 십성: {ten_gods_str}
- 그룹별 분포: {ten_gods_dist_str}
- 월지 십성: {month_branch_str}

### 격국 (정답)
- 격국: {primary_structure_str}

### 결핍 정보 (대체 전략 필요)
- 결핍 항목: {missing_str}

{survey_section}"""


__all__ = ["build_truth_anchor", "forbidden_words_for_rulecards", "build_fact_anchor_text"]
