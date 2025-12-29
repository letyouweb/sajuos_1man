"""
Survey Intake v2 - P0 Pivot: 1인 자영업자용 5문항 설문
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 P0 핵심 변경:
- 7문항 → 5문항으로 간소화
- 프론트엔드 필드와 1:1 매핑
- industry/painPoint/goal 기반 룰카드 가중치 연동
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. P0 Pivot: 5문항 Enum 정의
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class RevenueRange(str, Enum):
    """월매출 범위 (P0: 프론트 연동)"""
    ZERO = "0"
    UNDER_500 = "under_500"
    UNDER_1000 = "500_1000"
    UNDER_3000 = "1000_3000"
    UNDER_5000 = "3000_5000"
    UNDER_1B = "5000_1b"
    OVER_1B = "over_1b"


class PainPoint(str, Enum):
    """핵심 병목 (P0: 프론트 연동)"""
    LEAD = "lead"               # 고객 확보
    CONVERSION = "conversion"   # 전환율
    OPERATIONS = "operations"   # 운영/시스템
    FUNDING = "funding"         # 자금
    MENTAL = "mental"           # 번아웃
    DIRECTION = "direction"     # 방향성


class TimeAvailability(str, Enum):
    """주당 투입 시간 (P0: 프론트 연동)"""
    UNDER_10 = "under_10"
    UNDER_30 = "10_30"
    UNDER_50 = "30_50"
    OVER_50 = "over_50"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. P0 설문 응답 데이터 구조 (5문항)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class SurveyResponse:
    """
    🔥 P0 Pivot: 1인 자영업자용 5문항 설문
    프론트엔드 BusinessSurvey.tsx와 1:1 매핑
    """
    
    # Q1. 업종 (자유 입력)
    industry: str = ""
    
    # Q2. 월매출 범위
    revenue: str = "under_1000"
    
    # Q3. 핵심 병목
    painPoint: str = "lead"
    
    # Q4. 2026 목표 (자유 입력)
    goal: str = ""
    
    # Q5. 주당 투입 시간
    time: str = "30_50"
    
    # 레거시 호환 필드 (기존 7문항 지원)
    business_stage: str = ""
    monthly_revenue: str = ""
    margin_percent: int = 30
    cash_reserve: str = ""
    primary_bottleneck: str = ""
    secondary_bottleneck: str = ""
    goal_type: str = ""
    goal_detail: str = ""
    time_availability: str = ""
    has_team: bool = False
    team_size: int = 0
    risk_tolerance: str = ""
    urgent_question: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            # P0 5문항
            "industry": self.industry,
            "revenue": self.revenue,
            "painPoint": self.painPoint,
            "goal": self.goal,
            "time": self.time,
            # 레거시 호환
            "business_stage": self.business_stage,
            "monthly_revenue": self.monthly_revenue or self.revenue,
            "primary_bottleneck": self.primary_bottleneck or self.painPoint,
            "goal_detail": self.goal_detail or self.goal,
            "time_availability": self.time_availability or self.time,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SurveyResponse":
        """
        딕셔너리에서 생성 (P0 5문항 + 레거시 호환)
        """
        if not data:
            return cls()
        
        # 🔥 P0: 프론트엔드 5문항 필드 우선
        industry = data.get("industry", "")
        revenue = data.get("revenue") or data.get("monthly_revenue", "under_1000")
        painPoint = data.get("painPoint") or data.get("primary_bottleneck", "lead")
        goal = data.get("goal") or data.get("goal_detail", "")
        time = data.get("time") or data.get("time_availability", "30_50")
        
        return cls(
            industry=industry,
            revenue=revenue,
            painPoint=painPoint,
            goal=goal,
            time=time,
            # 레거시 필드
            business_stage=data.get("business_stage", ""),
            monthly_revenue=data.get("monthly_revenue", ""),
            margin_percent=data.get("margin_percent", 30),
            cash_reserve=data.get("cash_reserve", ""),
            primary_bottleneck=data.get("primary_bottleneck", ""),
            secondary_bottleneck=data.get("secondary_bottleneck", ""),
            goal_type=data.get("goal_type", ""),
            goal_detail=data.get("goal_detail", ""),
            time_availability=data.get("time_availability", ""),
            has_team=data.get("has_team", False),
            team_size=data.get("team_size", 0),
            risk_tolerance=data.get("risk_tolerance", ""),
            urgent_question=data.get("urgent_question", ""),
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 설문 → 룰카드 가중치 태그 변환
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 업종 → 관련 태그 매핑
INDUSTRY_TAG_MAP: Dict[str, List[str]] = {
    # IT/테크
    "it": ["創業", "事業", "技術", "革新", "食傷", "傷官"],
    "saas": ["創業", "事業", "技術", "革新", "食傷", "傷官", "收入"],
    "개발": ["創業", "技術", "革新", "食傷", "傷官", "印星"],
    "ai": ["創業", "技術", "革新", "食傷", "傷官", "印星"],
    "플랫폼": ["創業", "事業", "技術", "革新", "財運"],
    
    # 커머스
    "커머스": ["財星", "正財", "偏財", "投資", "收入", "財庫"],
    "쇼핑몰": ["財星", "正財", "偏財", "投資", "收入", "財庫"],
    "이커머스": ["財星", "正財", "偏財", "投資", "收入", "財庫"],
    "온라인": ["財星", "正財", "偏財", "投資", "收入"],
    
    # 서비스
    "컨설팅": ["官星", "正官", "偏官", "人脈", "貴人", "印星"],
    "교육": ["印星", "正印", "偏印", "人脈", "食神"],
    "코칭": ["印星", "正印", "偏印", "人脈", "食神"],
    "강의": ["印星", "正印", "偏印", "人脈", "食神"],
    
    # 요식업
    "카페": ["財星", "食神", "收入", "勞累", "投資"],
    "음식점": ["財星", "食神", "收入", "勞累", "投資"],
    "식당": ["財星", "食神", "收入", "勞累", "投資"],
    "프랜차이즈": ["財星", "官星", "投資", "合作", "事業"],
    
    # 콘텐츠
    "콘텐츠": ["食傷", "傷官", "食神", "創業", "收入"],
    "유튜브": ["食傷", "傷官", "食神", "創業", "收入", "人脈"],
    "크리에이터": ["食傷", "傷官", "食神", "創業", "人脈"],
    "인플루언서": ["食傷", "傷官", "食神", "人脈", "財運"],
    
    # 디자인/크리에이티브
    "디자인": ["食傷", "傷官", "食神", "印星", "創業"],
    "브랜딩": ["食傷", "傷官", "印星", "官星"],
    
    # 부동산/투자
    "부동산": ["財星", "正財", "偏財", "財庫", "投資"],
    "투자": ["偏財", "財星", "投資", "財庫", "大運"],
}

# 병목 → 관련 태그 매핑
PAINPOINT_TAG_MAP: Dict[str, List[str]] = {
    "lead": ["人脈", "貴人", "官星", "食傷", "傷官"],  # 고객 확보
    "conversion": ["財星", "正財", "食神生財", "合作", "吉時"],  # 전환율
    "operations": ["印星", "正印", "官星", "勞累", "精神"],  # 운영/시스템
    "funding": ["財星", "財庫", "破財", "損財", "偏財"],  # 자금
    "mental": ["身弱", "勞累", "精神", "健康", "印星"],  # 번아웃
    "direction": ["大運", "流年", "官星", "印星", "轉職"],  # 방향성
}

# 목표 키워드 → 관련 태그 매핑
GOAL_TAG_MAP: Dict[str, List[str]] = {
    # 매출/수익 관련
    "매출": ["財星", "正財", "財運", "收入", "食神生財"],
    "수익": ["財星", "正財", "財運", "收入"],
    "돈": ["財星", "偏財", "財庫", "財運"],
    "월매출": ["財星", "正財", "財運", "收入", "月運"],
    "연매출": ["財星", "正財", "財運", "大運"],
    
    # 규모 확장
    "확장": ["官星", "事業", "合作", "投資", "大運"],
    "스케일": ["官星", "事業", "合作", "投資"],
    "성장": ["官星", "事業", "大運", "流年"],
    
    # 팀/인력
    "팀": ["比劫", "比肩", "合作", "人脈", "官星"],
    "채용": ["比劫", "合作", "人脈", "官星"],
    "인력": ["比劫", "比肩", "合作", "人脈"],
    
    # 브랜드/인지도
    "브랜드": ["印星", "正印", "官星", "食傷", "傷官"],
    "인지도": ["印星", "官星", "食傷", "人脈"],
    
    # 시스템/자동화
    "자동화": ["印星", "正印", "食神", "官星"],
    "시스템": ["印星", "正印", "官星"],
    
    # 안정/워라밸
    "안정": ["正財", "財庫", "身强", "印星"],
    "워라밸": ["身强", "健康", "精神", "印星"],
}


def get_survey_weight_tags(survey: SurveyResponse) -> Dict[str, List[str]]:
    """
    🔥 P0 핵심: 설문 데이터 → 룰카드 가중치 태그 변환
    
    Returns:
        {
            "industry_tags": [...],
            "painpoint_tags": [...],
            "goal_tags": [...],
            "all_tags": [...]  # 중복 제거 합집합
        }
    """
    result = {
        "industry_tags": [],
        "painpoint_tags": [],
        "goal_tags": [],
        "all_tags": []
    }
    
    all_tags = set()
    
    # 1. 업종 태그
    industry_lower = survey.industry.lower() if survey.industry else ""
    for keyword, tags in INDUSTRY_TAG_MAP.items():
        if keyword in industry_lower:
            result["industry_tags"].extend(tags)
            all_tags.update(tags)
    
    # 2. 병목 태그
    painpoint_tags = PAINPOINT_TAG_MAP.get(survey.painPoint, [])
    result["painpoint_tags"] = painpoint_tags
    all_tags.update(painpoint_tags)
    
    # 3. 목표 태그
    goal_lower = survey.goal.lower() if survey.goal else ""
    for keyword, tags in GOAL_TAG_MAP.items():
        if keyword in goal_lower:
            result["goal_tags"].extend(tags)
            all_tags.update(tags)
    
    result["all_tags"] = list(all_tags)
    
    logger.info(
        f"[SurveyTags] industry={survey.industry} → {len(result['industry_tags'])}개 | "
        f"painPoint={survey.painPoint} → {len(result['painpoint_tags'])}개 | "
        f"goal → {len(result['goal_tags'])}개 | "
        f"total unique={len(all_tags)}개"
    )
    
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 설문 결과 → 프롬프트 컨텍스트 변환
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def survey_to_prompt_context(survey: SurveyResponse) -> str:
    """
    🔥 P0 Pivot: 5문항 설문 → 프롬프트 컨텍스트 (ONE-MAN BUSINESS)
    """
    
    # 매출 범위 설명
    revenue_map = {
        "0": "매출 없음 (Pre-revenue)",
        "under_500": "500만원 미만/월",
        "500_1000": "500~1000만원/월",
        "under_1000": "500~1000만원/월",
        "1000_3000": "1000~3000만원/월",
        "3000_5000": "3000~5000만원/월",
        "5000_1b": "5000만원~1억/월",
        "over_1b": "1억 이상/월",
    }
    
    # 병목 설명
    painpoint_map = {
        "lead": "🎯 고객 확보 (잠재 고객/리드가 부족)",
        "conversion": "💰 전환율 (관심→구매 전환이 낮음)",
        "operations": "⚙️ 운영/시스템 (업무 효율이 낮음)",
        "funding": "💸 자금 (현금흐름/투자금 부족)",
        "mental": "🧠 번아웃 (체력/의욕 저하)",
        "direction": "🧭 방향성 (무엇을 해야 할지 모르겠음)",
    }
    
    # 시간 설명
    time_map = {
        "under_10": "10시간 미만/주 (부업)",
        "10_30": "10~30시간/주 (파트타임)",
        "30_50": "30~50시간/주 (풀타임)",
        "over_50": "50시간+/주 (올인)",
    }
    
    context = f"""
=== 🎯 1인 자영업자 프로필 (P0 설문) ===

【업종】
{survey.industry or "미기재"}

【현재 월매출】
{revenue_map.get(survey.revenue, survey.revenue)}

【최대 병목】
{painpoint_map.get(survey.painPoint, survey.painPoint)}

【2026년 목표】
{survey.goal or "미기재"}

【주당 투입 가능 시간】
{time_map.get(survey.time, survey.time)}

=== 🚨 ONE-MAN BUSINESS 컨설팅 지침 ===

⚠️ 반드시 준수:
1. 이 고객의 "업종({survey.industry})"에 맞는 구체적 전략만 제시
2. "현재 매출({revenue_map.get(survey.revenue, survey.revenue)})" 수준에서 실행 가능한 액션만
3. "핵심 병목({survey.painPoint})" 해결이 최우선 과제
4. "주당 {time_map.get(survey.time, survey.time)}"만 투입 가능 → 우선순위 명확히
5. "2026 목표({survey.goal})"를 향한 90일 스프린트 설계

❌ 금지:
- "노력하세요", "성장의 시기", "좋은 운이 따릅니다" 같은 일반론
- 추상적 조언, 자기계발서 문투
- 대기업/팀 기반 전략 (1인 자영업자임!)
"""
    
    return context.strip()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. 프론트엔드용 설문 폼 스펙 (P0 5문항)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SURVEY_FORM_SPEC = {
    "title": "비즈니스 현황 (60초)",
    "description": "이 정보로 당신 상황에 맞는 전략을 제공합니다.",
    "questions": [
        {
            "id": "industry",
            "type": "text",
            "label": "업종/사업 분야",
            "placeholder": "예: IT/SaaS, 온라인 커머스, 교육, 컨설팅...",
            "required": True,
        },
        {
            "id": "revenue",
            "type": "select",
            "label": "현재 월매출",
            "options": [
                {"value": "0", "label": "매출 없음"},
                {"value": "under_500", "label": "500만원 미만"},
                {"value": "500_1000", "label": "500~1000만원"},
                {"value": "1000_3000", "label": "1000~3000만원"},
                {"value": "3000_5000", "label": "3000~5000만원"},
                {"value": "5000_1b", "label": "5000만원~1억"},
                {"value": "over_1b", "label": "1억 이상"},
            ],
            "required": True,
        },
        {
            "id": "painPoint",
            "type": "select",
            "label": "지금 가장 큰 병목은?",
            "options": [
                {"value": "lead", "label": "🎯 고객 확보"},
                {"value": "conversion", "label": "💰 전환율"},
                {"value": "operations", "label": "⚙️ 운영/시스템"},
                {"value": "funding", "label": "💸 자금"},
                {"value": "mental", "label": "🧠 번아웃"},
                {"value": "direction", "label": "🧭 방향성"},
            ],
            "required": True,
        },
        {
            "id": "goal",
            "type": "text",
            "label": "2026년 가장 중요한 목표 1개",
            "placeholder": "예: 월매출 5000만원, 시스템 자동화, 브랜드 인지도 확보...",
            "required": True,
        },
        {
            "id": "time",
            "type": "select",
            "label": "주당 투입 가능 시간",
            "options": [
                {"value": "under_10", "label": "10시간 미만 (부업)"},
                {"value": "10_30", "label": "10~30시간 (파트타임)"},
                {"value": "30_50", "label": "30~50시간 (풀타임)"},
                {"value": "over_50", "label": "50시간+ (올인)"},
            ],
            "required": True,
        },
    ]
}


def get_survey_form_spec() -> Dict[str, Any]:
    """프론트엔드용 설문 폼 스펙 반환"""
    return SURVEY_FORM_SPEC
