# app/services/saju_analyzer.py
"""
P0: 사주 분석 정답지 생성 모듈
- DeriveModule 기반으로 십성/오행 분포 계산
- LLM 환각 방지를 위한 Ground Truth 데이터 제공
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

ELEMENTS = ["목", "화", "토", "금", "수"]
TEN_GODS = ["비견", "겁재", "식신", "상관", "편재", "정재", "편관", "정관", "편인", "정인"]
TEN_GROUPS = ["비겁", "식상", "재성", "관성", "인성"]

# 십성 → 그룹 매핑
TEN_GOD_TO_GROUP = {
    "비견": "비겁", "겁재": "비겁",
    "식신": "식상", "상관": "식상",
    "편재": "재성", "정재": "재성",
    "편관": "관성", "정관": "관성",
    "편인": "인성", "정인": "인성",
}

# 월지 십성 → 격국 매핑
STRUCTURE_FROM_MONTH_TEN_GOD = {
    "비견": "건록격",
    "겁재": "양인격",
    "식신": "식신격",
    "상관": "상관격",
    "편재": "편재격",
    "정재": "정재격",
    "편관": "편관격",
    "정관": "정관격",
    "편인": "편인격",
    "정인": "정인격",
}

# 허용된 격국 이름들
ALLOWED_STRUCTURE_NAMES = [
    "건록격", "양인격", "식신격", "상관격",
    "편재격", "정재격", "편관격", "정관격",
    "편인격", "정인격", "종격", "화격", "외격"
]

# 천간 오행
CHEONGAN_ELEMENT = {
    "갑": "목", "을": "목",
    "병": "화", "정": "화",
    "무": "토", "기": "토",
    "경": "금", "신": "금",
    "임": "수", "계": "수"
}

# 지지 오행
JIJI_ELEMENT = {
    "자": "수", "축": "토", "인": "목", "묘": "목",
    "진": "토", "사": "화", "오": "화", "미": "토",
    "신": "금", "유": "금", "술": "토", "해": "수"
}

# 천간 음양
CHEONGAN_YIN_YANG = {
    "갑": "양", "을": "음",
    "병": "양", "정": "음",
    "무": "양", "기": "음",
    "경": "양", "신": "음",
    "임": "양", "계": "음"
}

# 오행 상생상극
ELEMENT_CYCLE = {
    "목": {"generates": "화", "conquers": "토", "conquered_by": "금", "generated_by": "수"},
    "화": {"generates": "토", "conquers": "금", "conquered_by": "수", "generated_by": "목"},
    "토": {"generates": "금", "conquers": "수", "conquered_by": "목", "generated_by": "화"},
    "금": {"generates": "수", "conquers": "목", "conquered_by": "화", "generated_by": "토"},
    "수": {"generates": "목", "conquers": "화", "conquered_by": "토", "generated_by": "금"},
}


def _get_ten_god(day_master: str, target_gan: str) -> str:
    """일간 기준 천간의 십성 계산"""
    if not day_master or not target_gan:
        return ""
    
    dm_element = CHEONGAN_ELEMENT.get(day_master, "")
    tg_element = CHEONGAN_ELEMENT.get(target_gan, "")
    
    if not dm_element or not tg_element:
        return ""
    
    dm_yy = CHEONGAN_YIN_YANG.get(day_master, "")
    tg_yy = CHEONGAN_YIN_YANG.get(target_gan, "")
    same_yy = (dm_yy == tg_yy)
    
    # 관계 결정
    if dm_element == tg_element:
        return "비견" if same_yy else "겁재"
    elif ELEMENT_CYCLE[dm_element]["generates"] == tg_element:
        return "식신" if same_yy else "상관"
    elif ELEMENT_CYCLE[dm_element]["conquers"] == tg_element:
        return "편재" if same_yy else "정재"
    elif ELEMENT_CYCLE[dm_element]["conquered_by"] == tg_element:
        return "편관" if same_yy else "정관"
    elif ELEMENT_CYCLE[dm_element]["generated_by"] == tg_element:
        return "편인" if same_yy else "정인"
    
    return ""


def _get_ten_god_from_ji(day_master: str, ji: str) -> str:
    """일간 기준 지지의 십성 계산 (지장간 본기 기준 간략화)"""
    if not day_master or not ji:
        return ""
    
    # 지장간 본기 매핑 (간략화)
    JI_MAIN_GAN = {
        "자": "계", "축": "기", "인": "갑", "묘": "을",
        "진": "무", "사": "병", "오": "정", "미": "기",
        "신": "경", "유": "신", "술": "무", "해": "임"
    }
    
    main_gan = JI_MAIN_GAN.get(ji, "")
    if not main_gan:
        return ""
    
    return _get_ten_god(day_master, main_gan)


def get_saju_summary(saju_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    P0: 사주 정답지 생성 (DeriveModule 기반)
    
    Args:
        saju_data: 평탄화된 사주 데이터
            - year_pillar, month_pillar, day_pillar, hour_pillar (각 2글자 ganji)
            - 또는 year/month/day/hour dict 구조
    
    Returns:
        saju_summary: LLM Ground Truth 데이터
    """
    # 1) 4주 ganji 추출
    year_pillar = saju_data.get("year_pillar", "")
    month_pillar = saju_data.get("month_pillar", "")
    day_pillar = saju_data.get("day_pillar", "")
    hour_pillar = saju_data.get("hour_pillar", "")
    
    # 일간 (나)
    day_master = day_pillar[0] if day_pillar else ""
    day_master_element = CHEONGAN_ELEMENT.get(day_master, "")
    
    # 2) 오행 카운트
    elements_count = {e: 0 for e in ELEMENTS}
    
    all_chars = year_pillar + month_pillar + day_pillar + hour_pillar
    for ch in all_chars:
        elem = CHEONGAN_ELEMENT.get(ch) or JIJI_ELEMENT.get(ch)
        if elem and elem in elements_count:
            elements_count[elem] += 1
    
    # 3) 십성 카운트
    ten_gods_count = {tg: 0 for tg in TEN_GODS}
    ten_gods_list = []
    
    if day_master:
        # 년간
        if year_pillar:
            tg = _get_ten_god(day_master, year_pillar[0])
            if tg:
                ten_gods_count[tg] += 1
                ten_gods_list.append({"position": "년간", "ten_god": tg})
        # 년지
        if len(year_pillar) > 1:
            tg = _get_ten_god_from_ji(day_master, year_pillar[1])
            if tg:
                ten_gods_count[tg] += 1
                ten_gods_list.append({"position": "년지", "ten_god": tg})
        
        # 월간
        if month_pillar:
            tg = _get_ten_god(day_master, month_pillar[0])
            if tg:
                ten_gods_count[tg] += 1
                ten_gods_list.append({"position": "월간", "ten_god": tg})
        # 월지
        if len(month_pillar) > 1:
            month_ji_tg = _get_ten_god_from_ji(day_master, month_pillar[1])
            if month_ji_tg:
                ten_gods_count[month_ji_tg] += 1
                ten_gods_list.append({"position": "월지", "ten_god": month_ji_tg})
        
        # 일지 (일간은 나 자신이므로 스킵)
        if len(day_pillar) > 1:
            tg = _get_ten_god_from_ji(day_master, day_pillar[1])
            if tg:
                ten_gods_count[tg] += 1
                ten_gods_list.append({"position": "일지", "ten_god": tg})
        
        # 시간
        if hour_pillar:
            tg = _get_ten_god(day_master, hour_pillar[0])
            if tg:
                ten_gods_count[tg] += 1
                ten_gods_list.append({"position": "시간", "ten_god": tg})
        # 시지
        if len(hour_pillar) > 1:
            tg = _get_ten_god_from_ji(day_master, hour_pillar[1])
            if tg:
                ten_gods_count[tg] += 1
                ten_gods_list.append({"position": "시지", "ten_god": tg})
    
    # 4) 십성 그룹 분포
    ten_gods_distribution = {g: 0 for g in TEN_GROUPS}
    for tg, cnt in ten_gods_count.items():
        grp = TEN_GOD_TO_GROUP.get(tg)
        if grp:
            ten_gods_distribution[grp] += cnt
    
    # 5) 격국 판단 (월지 십성 기준)
    primary_structure = None
    if month_pillar and len(month_pillar) > 1 and day_master:
        month_ji_tg = _get_ten_god_from_ji(day_master, month_pillar[1])
        primary_structure = STRUCTURE_FROM_MONTH_TEN_GOD.get(month_ji_tg)
    
    # 6) 결과 조립
    summary = {
        "day_master": day_master,
        "day_master_element": day_master_element,
        "elements_count": elements_count,
        "ten_gods_count": ten_gods_count,
        "ten_gods_distribution": ten_gods_distribution,
        "ten_gods_list": ten_gods_list,
        "primary_structure": primary_structure,
        "allowed_structure_names": ALLOWED_STRUCTURE_NAMES,
        # P0: 환각 방지 플래그
        "is_missing_shiksang": ten_gods_distribution.get("식상", 0) == 0,
        "is_missing_jaesung": ten_gods_distribution.get("재성", 0) == 0,
        "is_missing_gwansung": ten_gods_distribution.get("관성", 0) == 0,
        "is_missing_insung": ten_gods_distribution.get("인성", 0) == 0,
        "is_missing_bigeop": ten_gods_distribution.get("비겁", 0) == 0,
        # 원국 존재 십성 목록
        "ten_gods_present": [tg for tg, cnt in ten_gods_count.items() if cnt > 0],
        "elements_present": [e for e, cnt in elements_count.items() if cnt > 0],
        "has_wealth_star": ten_gods_distribution.get("재성", 0) > 0,
    }
    
    logger.info(f"[SajuAnalyzer] 정답지 생성: day_master={day_master} | 재성={ten_gods_distribution.get('재성', 0)} | 식상={ten_gods_distribution.get('식상', 0)}")
    
    return summary


def get_elements_present_str(saju_summary: Dict) -> str:
    """원국에 있는 오행 문자열"""
    return ", ".join(saju_summary.get("elements_present", []))


def get_ten_gods_present_str(saju_summary: Dict) -> str:
    """원국에 있는 십성 문자열"""
    return ", ".join(saju_summary.get("ten_gods_present", []))
