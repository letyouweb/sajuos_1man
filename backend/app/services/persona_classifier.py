"""
persona_classifier.py
사주 데이터 기반 페르소나 분류

🔥 P0: 판정 순서 = 위기형 → 결핍형 → 과다형 → 정석형 → standard

페르소나 종류:
- crisis: 복합 결핍 (위기형)
- missing_wealth: 재성 결핍
- missing_expression: 식상 결핍
- missing_authority: 관성 결핍
- missing_support: 인성 결핍
- fire_dominant: 화(火) 과다
- water_dominant: 수(水) 과다
- wood_dominant: 목(木) 과다
- metal_dominant: 금(金) 과다
- earth_dominant: 토(土) 과다
- balanced: 오행 균형
- entrepreneur: 창업가 성향
- leader: 리더 성향
- creative: 창작자 성향
- standard: 기본 (폴백)
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def classify_persona(saju_data: Dict[str, Any]) -> str:
    """
    사주 데이터 기반 페르소나 분류
    
    🔥 P0: 판정 순서 = 위기형 → 결핍형 → 과다형 → 정석형 → standard
    
    Args:
        saju_data: 사주 데이터 (saju_summary, elements_count 등 포함)
        
    Returns:
        persona_id: 페르소나 ID
    """
    try:
        # saju_summary에서 정보 추출
        saju_summary = saju_data.get("saju_summary") or {}
        elements_count = saju_summary.get("elements_count") or {}
        ten_gods = saju_summary.get("ten_gods_present") or []
        
        # 결핍 플래그
        is_missing_jaesung = saju_summary.get("is_missing_jaesung", False)
        is_missing_shiksang = saju_summary.get("is_missing_shiksang", False)
        is_missing_gwansung = saju_summary.get("is_missing_gwansung", False)
        is_missing_insung = saju_summary.get("is_missing_insung", False)
        
        # 오행 개수
        fire = elements_count.get("fire", 0) or elements_count.get("화", 0)
        water = elements_count.get("water", 0) or elements_count.get("수", 0)
        wood = elements_count.get("wood", 0) or elements_count.get("목", 0)
        metal = elements_count.get("metal", 0) or elements_count.get("금", 0)
        earth = elements_count.get("earth", 0) or elements_count.get("토", 0)
        
        total = fire + water + wood + metal + earth
        
        persona = "standard"  # 기본값
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🔥 1단계: 위기형 (crisis) - 복합 결핍
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        missing_count = sum([is_missing_jaesung, is_missing_shiksang, is_missing_gwansung, is_missing_insung])
        if missing_count >= 2:
            persona = "crisis"
            logger.info(f"[Persona] 🔴 위기형 판정: missing_count={missing_count}")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🔥 2단계: 결핍형 (missing_*) - 단일 결핍
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        elif is_missing_jaesung:
            persona = "missing_wealth"
        elif is_missing_shiksang:
            persona = "missing_expression"
        elif is_missing_gwansung:
            persona = "missing_authority"
        elif is_missing_insung:
            persona = "missing_support"
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🔥 3단계: 과다형 (dominant) - 오행 40% 이상
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        elif total > 0:
            if fire / total >= 0.4:
                persona = "fire_dominant"
            elif water / total >= 0.4:
                persona = "water_dominant"
            elif wood / total >= 0.4:
                persona = "wood_dominant"
            elif metal / total >= 0.4:
                persona = "metal_dominant"
            elif earth / total >= 0.4:
                persona = "earth_dominant"
            else:
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # 🔥 4단계: 정석형 (특화 성향)
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                ten_gods_set = set(ten_gods)
                
                # 창업가 성향: 정재/편재 2개 이상
                wealth_gods = {"정재", "편재", "正財", "偏財"}
                if len(ten_gods_set & wealth_gods) >= 2:
                    persona = "entrepreneur"
                
                # 리더 성향: 정관/편관 2개 이상
                elif len(ten_gods_set & {"정관", "편관", "正官", "偏官"}) >= 2:
                    persona = "leader"
                
                # 창작자 성향: 식신/상관 2개 이상
                elif len(ten_gods_set & {"식신", "상관", "食神", "傷官"}) >= 2:
                    persona = "creative"
                
                # 오행 균형 체크
                else:
                    values = [fire, water, wood, metal, earth]
                    max_val = max(values) if values else 0
                    min_val = min([v for v in values if v > 0]) if any(v > 0 for v in values) else 0
                    if max_val > 0 and min_val > 0 and max_val / min_val <= 2:
                        persona = "balanced"
        
        # 🔥 로그 출력 (필수)
        logger.info(
            f"[Persona] missing_jaesung={is_missing_jaesung} | "
            f"missing_shiksang={is_missing_shiksang} | "
            f"missing_gwansung={is_missing_gwansung} | "
            f"missing_insung={is_missing_insung} | "
            f"=> persona={persona}"
        )
        
        return persona
        
    except Exception as e:
        logger.warning(f"[PersonaClassifier] 분류 실패: {e}")
        return "standard"


def get_persona_description(persona_id: str) -> str:
    """페르소나 설명 반환"""
    descriptions = {
        "standard": "균형 잡힌 비즈니스 성향",
        # 결핍형
        "missing_wealth": "재성 결핍 - 현금흐름 보완 전략 필요",
        "missing_expression": "식상 결핍 - 마케팅/표현력 강화 필요",
        "missing_authority": "관성 결핍 - 조직/권위 체계 보완 필요",
        "missing_support": "인성 결핍 - 학습/지원 체계 확보 필요",
        "crisis": "복합 결핍 - 다방면 보완 전략 필요",
        # 과다형
        "fire_dominant": "화(火) 과다 - 열정적이고 추진력 강함, 과열 주의",
        "water_dominant": "수(水) 과다 - 지혜롭고 유연함, 우유부단 주의",
        "wood_dominant": "목(木) 과다 - 성장 지향, 확장 욕구 강함",
        "metal_dominant": "금(金) 과다 - 결단력 강함, 융통성 부족 주의",
        "earth_dominant": "토(土) 과다 - 안정 지향, 보수적 성향",
        # 정석형
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
        # 결핍형
        "missing_wealth": ["현금흐름", "수익 보완", "비용 관리", "재정 안정"],
        "missing_expression": ["마케팅 강화", "표현력", "영업 전략", "커뮤니케이션"],
        "missing_authority": ["조직력", "권위 확보", "시스템 구축", "관리 체계"],
        "missing_support": ["학습", "멘토링", "지원 체계", "네트워크 확보"],
        "crisis": ["종합 보완", "리스크 관리", "기반 강화", "단계적 성장"],
        # 과다형
        "fire_dominant": ["열정", "추진력", "속도", "과열 주의"],
        "water_dominant": ["지혜", "유연성", "소통", "결단력 보완"],
        "wood_dominant": ["성장", "확장", "도전", "리소스 관리"],
        "metal_dominant": ["결단", "효율", "정리", "유연성 보완"],
        "earth_dominant": ["안정", "신뢰", "지속", "변화 수용"],
        # 정석형
        "balanced": ["조화", "다각화", "균형", "차별화 필요"],
        "entrepreneur": ["투자", "수익", "확장", "리스크 관리"],
        "leader": ["조직", "관리", "권한", "소통 강화"],
        "creative": ["아이디어", "혁신", "차별화", "실행력 보완"],
    }
    return keywords.get(persona_id, ["성장", "안정", "효율"])
