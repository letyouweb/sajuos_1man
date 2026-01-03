"""
persona_classifier.py
사주 데이터 기반 페르소나 분류

페르소나 종류:
- standard: 기본 (폴백)
- fire_dominant: 화(火) 과다
- water_dominant: 수(水) 과다
- wood_dominant: 목(木) 과다
- metal_dominant: 금(金) 과다
- earth_dominant: 토(土) 과다
- balanced: 오행 균형
- entrepreneur: 창업가 성향 (정재/편재 강함)
- leader: 리더 성향 (정관/편관 강함)
- creative: 창작자 성향 (식신/상관 강함)
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def classify_persona(saju_data: Dict[str, Any]) -> str:
    """
    사주 데이터 기반 페르소나 분류
    
    Args:
        saju_data: 사주 데이터 (saju_summary, elements_count 등 포함)
        
    Returns:
        persona_id: 페르소나 ID (예: "fire_dominant", "standard")
    """
    try:
        # saju_summary에서 정보 추출
        saju_summary = saju_data.get("saju_summary") or {}
        elements_count = saju_summary.get("elements_count") or {}
        ten_gods = saju_summary.get("ten_gods_present") or []
        day_master = saju_data.get("day_master") or ""
        
        # 오행 개수
        fire = elements_count.get("fire", 0) or elements_count.get("화", 0)
        water = elements_count.get("water", 0) or elements_count.get("수", 0)
        wood = elements_count.get("wood", 0) or elements_count.get("목", 0)
        metal = elements_count.get("metal", 0) or elements_count.get("금", 0)
        earth = elements_count.get("earth", 0) or elements_count.get("토", 0)
        
        total = fire + water + wood + metal + earth
        
        # 오행 과다 체크 (50% 이상이면 dominant)
        if total > 0:
            if fire / total >= 0.4:
                return "fire_dominant"
            if water / total >= 0.4:
                return "water_dominant"
            if wood / total >= 0.4:
                return "wood_dominant"
            if metal / total >= 0.4:
                return "metal_dominant"
            if earth / total >= 0.4:
                return "earth_dominant"
        
        # 십신 기반 성향 체크
        ten_gods_set = set(ten_gods)
        
        # 창업가 성향: 정재/편재 강함
        wealth_gods = {"정재", "편재", "正財", "偏財"}
        if len(ten_gods_set & wealth_gods) >= 2:
            return "entrepreneur"
        
        # 리더 성향: 정관/편관 강함
        authority_gods = {"정관", "편관", "正官", "偏官"}
        if len(ten_gods_set & authority_gods) >= 2:
            return "leader"
        
        # 창작자 성향: 식신/상관 강함
        creative_gods = {"식신", "상관", "食神", "傷官"}
        if len(ten_gods_set & creative_gods) >= 2:
            return "creative"
        
        # 오행 균형 체크
        if total > 0:
            values = [fire, water, wood, metal, earth]
            max_val = max(values)
            min_val = min(values)
            if max_val > 0 and min_val > 0 and max_val / min_val <= 2:
                return "balanced"
        
        # 기본값
        return "standard"
        
    except Exception as e:
        logger.warning(f"[PersonaClassifier] 분류 실패: {e}")
        return "standard"


def get_persona_description(persona_id: str) -> str:
    """페르소나 설명 반환"""
    descriptions = {
        "standard": "균형 잡힌 비즈니스 성향",
        "fire_dominant": "화(火) 과다 - 열정적이고 추진력 강함, 과열 주의",
        "water_dominant": "수(水) 과다 - 지혜롭고 유연함, 우유부단 주의",
        "wood_dominant": "목(木) 과다 - 성장 지향, 확장 욕구 강함",
        "metal_dominant": "금(金) 과다 - 결단력 강함, 융통성 부족 주의",
        "earth_dominant": "토(土) 과다 - 안정 지향, 보수적 성향",
        "balanced": "오행 균형 - 안정적이나 특출난 강점 약함",
        "entrepreneur": "창업가 성향 - 재물운 강함, 사업 확장 유리",
        "leader": "리더 성향 - 조직 관리 능력, 권위 추구",
        "creative": "창작자 성향 - 아이디어 풍부, 실행력 보완 필요",
    }
    return descriptions.get(persona_id, "기본 비즈니스 성향")


def get_persona_keywords(persona_id: str) -> list:
    """페르소나별 강조 키워드"""
    keywords = {
        "standard": ["균형", "안정", "성장"],
        "fire_dominant": ["열정", "추진력", "속도", "과열 주의"],
        "water_dominant": ["지혜", "유연성", "소통", "결단력 보완"],
        "wood_dominant": ["성장", "확장", "도전", "리소스 관리"],
        "metal_dominant": ["결단", "효율", "정리", "유연성 보완"],
        "earth_dominant": ["안정", "신뢰", "지속", "변화 수용"],
        "balanced": ["조화", "다각화", "균형", "차별화 필요"],
        "entrepreneur": ["투자", "수익", "확장", "리스크 관리"],
        "leader": ["조직", "관리", "권한", "소통 강화"],
        "creative": ["아이디어", "혁신", "차별화", "실행력 보완"],
    }
    return keywords.get(persona_id, ["성장", "안정", "효율"])
