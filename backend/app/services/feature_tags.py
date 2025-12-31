"""
Feature Tags v0.3 - 단일 소스
모든 엔드포인트는 이 함수만 호출
"""
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

CHEONGAN = ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계"]
JIJI = ["자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해"]

GAN_ELEMENT = {"갑": "목", "을": "목", "병": "화", "정": "화", "무": "토", "기": "토", "경": "금", "신": "금", "임": "수", "계": "수"}
JI_ELEMENT = {"자": "수", "축": "토", "인": "목", "묘": "목", "진": "토", "사": "화", "오": "화", "미": "토", "신": "금", "유": "금", "술": "토", "해": "수"}

TEN_GODS_MAP = {
    (0, 0): "비견", (0, 1): "겁재", (0, 2): "식신", (0, 3): "상관", (0, 4): "편재",
    (0, 5): "정재", (0, 6): "편관", (0, 7): "정관", (0, 8): "편인", (0, 9): "정인",
}


def build_feature_tags(pillars: Dict[str, Any], survey_data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    사주 Feature 단일 소스 (v0.3)
    
    Args:
        pillars: {"year": {...}, "month": {...}, "day": {...}, "hour": {...}}
        survey_data: 설문 데이터 (optional)
    
    Returns:
        {
            "day_master": "갑",
            "month_branch": "인",
            "pillars": "갑자 을축 병인 정묘",
            "tokens": ["갑", "자", "을", "축", ...],
            "elements_count": {"목": 2, "화": 1, ...},
            "ten_gods_count": {"비견": 1, ...} or None,
            "survey_tags": ["IT", "리드"]  # survey 기반
        }
    """
    result = {
        "day_master": None,
        "month_branch": None,
        "pillars": "",
        "tokens": [],
        "elements_count": {"목": 0, "화": 0, "토": 0, "금": 0, "수": 0},
        "ten_gods_count": None,
        "survey_tags": []
    }
    
    if not pillars:
        return result
    
    # 1. pillars 문자열 + tokens 추출
    pillar_parts = []
    tokens = []
    
    for key in ["year", "month", "day", "hour"]:
        p = pillars.get(key)
        if not p:
            continue
        
        ganji = p.get("ganji", "")
        if ganji and len(ganji) >= 2:
            pillar_parts.append(ganji)
            gan, ji = ganji[0], ganji[1]
            tokens.extend([gan, ji])
            
            # 오행 카운트
            if gan in GAN_ELEMENT:
                result["elements_count"][GAN_ELEMENT[gan]] += 1
            if ji in JI_ELEMENT:
                result["elements_count"][JI_ELEMENT[ji]] += 1
    
    result["pillars"] = " ".join(pillar_parts)
    result["tokens"] = tokens
    
    # 2. day_master (일간)
    day_p = pillars.get("day", {})
    day_gan = day_p.get("gan") or (day_p.get("ganji", "")[0] if day_p.get("ganji") else None)
    if day_gan:
        result["day_master"] = day_gan
    
    # 3. month_branch (월지)
    month_p = pillars.get("month", {})
    month_ji = month_p.get("ji") or (month_p.get("ganji", "")[1] if len(month_p.get("ganji", "")) > 1 else None)
    if month_ji:
        result["month_branch"] = month_ji
    
    # 4. ten_gods_count (십성 카운트)
    if day_gan and day_gan in CHEONGAN:
        day_idx = CHEONGAN.index(day_gan)
        ten_gods = {}
        
        for t in tokens:
            if t in CHEONGAN:
                t_idx = CHEONGAN.index(t)
                diff = (t_idx - day_idx) % 10
                god = TEN_GODS_MAP.get((0, diff), "비견")
                ten_gods[god] = ten_gods.get(god, 0) + 1
        
        if ten_gods:
            result["ten_gods_count"] = ten_gods
    
    # 5. survey_tags (설문 기반 태그)
    if survey_data:
        survey_tags = []
        
        # industry
        industry = survey_data.get("industry", "")
        if industry:
            survey_tags.append(industry)
        
        # painPoint
        pain = survey_data.get("painPoint", "")
        if pain:
            survey_tags.append(pain)
        
        # businessGoal
        goal = survey_data.get("businessGoal", "")
        if goal:
            survey_tags.append(goal)
        
        # decisionStyle
        style = survey_data.get("decisionStyle", "")
        if style:
            survey_tags.append(style)
        
        result["survey_tags"] = survey_tags
    
    logger.info(f"[FeatureTags] day_master={result['day_master']}, month_branch={result['month_branch']}, tokens={len(tokens)}")
    
    return result


def get_matching_tokens(features: Dict[str, Any]) -> List[str]:
    """매칭용 토큰 리스트 반환"""
    tokens = list(features.get("tokens", []))
    
    # 오행 추가
    for elem, cnt in features.get("elements_count", {}).items():
        if cnt > 0:
            tokens.append(elem)
    
    # 십성 추가
    ten_gods = features.get("ten_gods_count")
    if ten_gods:
        tokens.extend(ten_gods.keys())
    
    # survey_tags 추가
    tokens.extend(features.get("survey_tags", []))
    
    return tokens
