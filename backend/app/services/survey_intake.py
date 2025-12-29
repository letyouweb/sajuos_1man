"""
Survey Intake - 결제 후 7문항 설문
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
자기계발서 → 컨설팅 보고서 전환의 핵심:
사주 데이터만으로는 일반론이 됨
→ 사업 상황 + 목표 + 리스크 + 시간 데이터를 프롬프트에 주입
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from enum import Enum
import json


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 설문 선택지 Enum
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BusinessStage(str, Enum):
    """사업 단계"""
    IDEA = "idea"           # 아이디어/기획 단계
    ZERO_TO_ONE = "0to1"    # 0→1 (첫 매출 전)
    ONE_TO_TEN = "1to10"    # 1→10 (성장 초기)
    TEN_TO_HUNDRED = "10to100"  # 10→100 (확장 단계)
    ESTABLISHED = "established"  # 안정기 (연매출 10억+)
    PIVOT = "pivot"         # 사업 전환/피봇


class RevenueRange(str, Enum):
    """월매출 범위"""
    ZERO = "0"              # 매출 없음
    UNDER_500 = "under_500"  # 500만원 미만
    UNDER_1000 = "500_1000"  # 500~1000만원
    UNDER_3000 = "1000_3000"  # 1000~3000만원
    UNDER_5000 = "3000_5000"  # 3000~5000만원
    UNDER_1B = "5000_1b"    # 5000만원~1억
    OVER_1B = "over_1b"     # 1억 이상


class CashReserve(str, Enum):
    """현금 보유량"""
    ZERO = "0"              # 없음
    UNDER_1000 = "under_1000"  # 1000만원 미만
    UNDER_5000 = "1000_5000"  # 1000~5000만원
    UNDER_1B = "5000_1b"    # 5000만원~1억
    UNDER_3B = "1b_3b"      # 1~3억
    OVER_3B = "over_3b"     # 3억 이상


class Bottleneck(str, Enum):
    """가장 큰 병목"""
    LEAD = "lead"           # 리드/고객 확보
    CONVERSION = "conversion"  # 전환율
    OPERATIONS = "operations"  # 운영/시스템
    TEAM = "team"           # 팀/인력
    FUNDING = "funding"     # 자금/캐시플로우
    MENTAL = "mental"       # 멘탈/번아웃
    DIRECTION = "direction"  # 방향성/전략
    COMPETITION = "competition"  # 경쟁/차별화


class TimeAvailability(str, Enum):
    """주당 투입 가능 시간"""
    UNDER_10 = "under_10"   # 10시간 미만 (부업)
    UNDER_30 = "10_30"      # 10~30시간
    UNDER_50 = "30_50"      # 30~50시간 (풀타임)
    OVER_50 = "over_50"     # 50시간+ (올인)


class RiskTolerance(str, Enum):
    """리스크 성향"""
    CONSERVATIVE = "conservative"  # 보수적 (안정 최우선)
    BALANCED = "balanced"         # 중립 (적정 리스크)
    AGGRESSIVE = "aggressive"     # 공격적 (고위험 고수익)


class GoalType(str, Enum):
    """2026 주요 목표 유형"""
    REVENUE = "revenue"       # 매출 달성
    PROFIT = "profit"         # 순이익 달성
    ASSET = "asset"           # 자산 형성
    BRAND = "brand"           # 브랜드/인지도
    SCALE = "scale"           # 규모 확장 (팀, 지점 등)
    EXIT = "exit"             # 엑싯/매각
    BALANCE = "balance"       # 워라밸/지속가능성
    PIVOT = "pivot"           # 사업 전환


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 설문 응답 데이터 구조
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class SurveyResponse:
    """결제 후 7문항 설문 응답"""
    
    # Q1. 업종/사업 단계
    industry: str = ""  # 자유 입력 (예: "IT/SaaS", "온라인 커머스", "컨설팅")
    business_stage: BusinessStage = BusinessStage.ONE_TO_TEN
    
    # Q2. 현재 월매출/마진 (범위 선택)
    monthly_revenue: RevenueRange = RevenueRange.UNDER_1000
    margin_percent: int = 30  # 마진율 (0-100)
    
    # Q3. 현금 보유량
    cash_reserve: CashReserve = CashReserve.UNDER_1000
    
    # Q4. 가장 큰 병목
    primary_bottleneck: Bottleneck = Bottleneck.LEAD
    secondary_bottleneck: Optional[Bottleneck] = None
    
    # Q5. 2026 목표 (자유 입력 + 유형)
    goal_type: GoalType = GoalType.REVENUE
    goal_detail: str = ""  # 예: "월매출 5000만원", "순이익 1억"
    
    # Q6. 주당 투입 가능 시간
    time_availability: TimeAvailability = TimeAvailability.UNDER_50
    has_team: bool = False
    team_size: int = 0
    
    # Q7. 리스크 성향
    risk_tolerance: RiskTolerance = RiskTolerance.BALANCED
    
    # 보너스: 가장 급한 질문 (자유 입력)
    urgent_question: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "industry": self.industry,
            "business_stage": self.business_stage.value if isinstance(self.business_stage, Enum) else self.business_stage,
            "monthly_revenue": self.monthly_revenue.value if isinstance(self.monthly_revenue, Enum) else self.monthly_revenue,
            "margin_percent": self.margin_percent,
            "cash_reserve": self.cash_reserve.value if isinstance(self.cash_reserve, Enum) else self.cash_reserve,
            "primary_bottleneck": self.primary_bottleneck.value if isinstance(self.primary_bottleneck, Enum) else self.primary_bottleneck,
            "secondary_bottleneck": self.secondary_bottleneck.value if self.secondary_bottleneck and isinstance(self.secondary_bottleneck, Enum) else self.secondary_bottleneck,
            "goal_type": self.goal_type.value if isinstance(self.goal_type, Enum) else self.goal_type,
            "goal_detail": self.goal_detail,
            "time_availability": self.time_availability.value if isinstance(self.time_availability, Enum) else self.time_availability,
            "has_team": self.has_team,
            "team_size": self.team_size,
            "risk_tolerance": self.risk_tolerance.value if isinstance(self.risk_tolerance, Enum) else self.risk_tolerance,
            "urgent_question": self.urgent_question,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SurveyResponse":
        """딕셔너리에서 생성"""
        return cls(
            industry=data.get("industry", ""),
            business_stage=BusinessStage(data.get("business_stage", "1to10")),
            monthly_revenue=RevenueRange(data.get("monthly_revenue", "under_1000")),
            margin_percent=data.get("margin_percent", 30),
            cash_reserve=CashReserve(data.get("cash_reserve", "under_1000")),
            primary_bottleneck=Bottleneck(data.get("primary_bottleneck", "lead")),
            secondary_bottleneck=Bottleneck(data["secondary_bottleneck"]) if data.get("secondary_bottleneck") else None,
            goal_type=GoalType(data.get("goal_type", "revenue")),
            goal_detail=data.get("goal_detail", ""),
            time_availability=TimeAvailability(data.get("time_availability", "30_50")),
            has_team=data.get("has_team", False),
            team_size=data.get("team_size", 0),
            risk_tolerance=RiskTolerance(data.get("risk_tolerance", "balanced")),
            urgent_question=data.get("urgent_question", ""),
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 설문 결과 → 프롬프트 컨텍스트 변환
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def survey_to_prompt_context(survey: SurveyResponse) -> str:
    """
    설문 응답을 AI 프롬프트에 주입할 컨텍스트로 변환
    
    이 정보가 있어야 "일반론"이 아닌 "맞춤 컨설팅"이 됨
    """
    
    # 사업 단계 설명
    stage_map = {
        BusinessStage.IDEA: "아이디어/기획 단계 (매출 없음, PMF 탐색 중)",
        BusinessStage.ZERO_TO_ONE: "0→1 단계 (첫 매출 창출 전, MVP 검증 중)",
        BusinessStage.ONE_TO_TEN: "1→10 단계 (초기 매출 발생, 성장 가속화 필요)",
        BusinessStage.TEN_TO_HUNDRED: "10→100 단계 (확장기, 시스템화/팀빌딩 필요)",
        BusinessStage.ESTABLISHED: "안정기 (검증된 사업 모델, 효율화/다각화 고민)",
        BusinessStage.PIVOT: "사업 전환/피봇 단계 (기존 모델 재검토 중)",
    }
    
    # 월매출 범위 설명
    revenue_map = {
        RevenueRange.ZERO: "매출 없음 (Pre-revenue)",
        RevenueRange.UNDER_500: "500만원 미만",
        RevenueRange.UNDER_1000: "500~1000만원",
        RevenueRange.UNDER_3000: "1000~3000만원",
        RevenueRange.UNDER_5000: "3000~5000만원",
        RevenueRange.UNDER_1B: "5000만원~1억",
        RevenueRange.OVER_1B: "1억 이상",
    }
    
    # 현금 보유량 설명
    cash_map = {
        CashReserve.ZERO: "비상금 없음 (현금 흐름 의존)",
        CashReserve.UNDER_1000: "1000만원 미만 (1~2개월 운영 가능)",
        CashReserve.UNDER_5000: "1000~5000만원 (3~6개월 버퍼)",
        CashReserve.UNDER_1B: "5000만원~1억 (안정적 버퍼)",
        CashReserve.UNDER_3B: "1~3억 (공격적 투자 가능)",
        CashReserve.OVER_3B: "3억 이상 (충분한 여유 자금)",
    }
    
    # 병목 설명
    bottleneck_map = {
        Bottleneck.LEAD: "리드/고객 확보 (잠재 고객이 부족)",
        Bottleneck.CONVERSION: "전환율 (관심→구매 전환이 낮음)",
        Bottleneck.OPERATIONS: "운영/시스템 (업무 효율이 낮음)",
        Bottleneck.TEAM: "팀/인력 (사람이 부족하거나 역량 부족)",
        Bottleneck.FUNDING: "자금/캐시플로우 (돈이 부족)",
        Bottleneck.MENTAL: "멘탈/번아웃 (체력/의욕 저하)",
        Bottleneck.DIRECTION: "방향성/전략 (무엇을 해야 할지 모르겠음)",
        Bottleneck.COMPETITION: "경쟁/차별화 (경쟁자 대비 우위가 없음)",
    }
    
    # 시간 가용성 설명
    time_map = {
        TimeAvailability.UNDER_10: "10시간 미만/주 (부업/사이드 프로젝트)",
        TimeAvailability.UNDER_30: "10~30시간/주 (파트타임)",
        TimeAvailability.UNDER_50: "30~50시간/주 (풀타임)",
        TimeAvailability.OVER_50: "50시간+/주 (올인 상태)",
    }
    
    # 리스크 성향 설명
    risk_map = {
        RiskTolerance.CONSERVATIVE: "보수적 (안정 최우선, 리스크 최소화)",
        RiskTolerance.BALANCED: "중립 (적정 리스크, 성장과 안정 균형)",
        RiskTolerance.AGGRESSIVE: "공격적 (고위험 고수익 추구)",
    }
    
    # 팀 정보
    team_info = f"{survey.team_size}명 팀 보유" if survey.has_team and survey.team_size > 0 else "1인 사업자 (솔로)"
    
    context = f"""
=== 🎯 고객 비즈니스 프로필 (설문 기반) ===

[업종/산업]
{survey.industry or "미기재"}

[사업 단계]
{stage_map.get(survey.business_stage, "미기재")}

[재무 현황]
- 월매출: {revenue_map.get(survey.monthly_revenue, "미기재")}
- 마진율: 약 {survey.margin_percent}%
- 현금 보유: {cash_map.get(survey.cash_reserve, "미기재")}

[조직]
{team_info}

[핵심 병목]
1차: {bottleneck_map.get(survey.primary_bottleneck, "미기재")}
{f"2차: {bottleneck_map.get(survey.secondary_bottleneck, '')}" if survey.secondary_bottleneck else ""}

[2026년 목표]
유형: {survey.goal_type.value if isinstance(survey.goal_type, Enum) else survey.goal_type}
상세: {survey.goal_detail or "미기재"}

[투입 가능 시간]
{time_map.get(survey.time_availability, "미기재")}

[리스크 성향]
{risk_map.get(survey.risk_tolerance, "미기재")}

[가장 급한 질문/고민]
{survey.urgent_question or "미기재"}

=== 🚨 컨설팅 지침 ===
위 프로필을 기반으로:
1. 일반론이 아닌 "이 고객 상황"에 맞는 조언을 하세요.
2. 현재 월매출/현금 수준에서 실행 가능한 액션만 제안하세요.
3. 병목({survey.primary_bottleneck.value if isinstance(survey.primary_bottleneck, Enum) else survey.primary_bottleneck})을 해결하는 것이 최우선입니다.
4. 리스크 성향({survey.risk_tolerance.value if isinstance(survey.risk_tolerance, Enum) else survey.risk_tolerance})에 맞는 전략을 제시하세요.
5. 주당 {time_map.get(survey.time_availability, "제한된 시간")}만 투입 가능하다는 점을 고려하세요.
"""
    
    return context.strip()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 프론트엔드용 설문 폼 스펙
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SURVEY_FORM_SPEC = {
    "title": "프리미엄 리포트를 위한 60초 설문",
    "description": "더 정확한 컨설팅을 위해 현재 상황을 알려주세요.",
    "questions": [
        {
            "id": "industry",
            "type": "text",
            "label": "업종/사업 분야",
            "placeholder": "예: IT/SaaS, 온라인 커머스, 교육, 컨설팅...",
            "required": True,
        },
        {
            "id": "business_stage",
            "type": "select",
            "label": "현재 사업 단계",
            "options": [
                {"value": "idea", "label": "🌱 아이디어/기획 단계"},
                {"value": "0to1", "label": "🚀 0→1 (첫 매출 전)"},
                {"value": "1to10", "label": "📈 1→10 (성장 초기)"},
                {"value": "10to100", "label": "🏗️ 10→100 (확장 단계)"},
                {"value": "established", "label": "🏢 안정기 (연매출 10억+)"},
                {"value": "pivot", "label": "🔄 사업 전환/피봇"},
            ],
            "required": True,
        },
        {
            "id": "monthly_revenue",
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
            "id": "cash_reserve",
            "type": "select",
            "label": "현금 보유량 (비상금)",
            "options": [
                {"value": "0", "label": "없음"},
                {"value": "under_1000", "label": "1000만원 미만"},
                {"value": "1000_5000", "label": "1000~5000만원"},
                {"value": "5000_1b", "label": "5000만원~1억"},
                {"value": "1b_3b", "label": "1~3억"},
                {"value": "over_3b", "label": "3억 이상"},
            ],
            "required": True,
        },
        {
            "id": "primary_bottleneck",
            "type": "select",
            "label": "지금 가장 큰 병목은?",
            "options": [
                {"value": "lead", "label": "🎯 리드/고객 확보"},
                {"value": "conversion", "label": "💰 전환율 (관심→구매)"},
                {"value": "operations", "label": "⚙️ 운영/시스템"},
                {"value": "team", "label": "👥 팀/인력"},
                {"value": "funding", "label": "💸 자금/캐시플로우"},
                {"value": "mental", "label": "🧠 멘탈/번아웃"},
                {"value": "direction", "label": "🧭 방향성/전략"},
                {"value": "competition", "label": "⚔️ 경쟁/차별화"},
            ],
            "required": True,
        },
        {
            "id": "goal_detail",
            "type": "text",
            "label": "2026년 가장 중요한 목표 1개",
            "placeholder": "예: 월매출 5000만원, 팀 3명 채용, 브랜드 인지도 확보...",
            "required": True,
        },
        {
            "id": "time_availability",
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
        {
            "id": "risk_tolerance",
            "type": "select",
            "label": "리스크 성향",
            "options": [
                {"value": "conservative", "label": "🛡️ 보수적 (안정 최우선)"},
                {"value": "balanced", "label": "⚖️ 중립 (성장과 안정 균형)"},
                {"value": "aggressive", "label": "🚀 공격적 (고위험 고수익)"},
            ],
            "required": True,
        },
        {
            "id": "urgent_question",
            "type": "textarea",
            "label": "지금 당장 해결하고 싶은 질문 1개 (선택)",
            "placeholder": "예: 첫 고객을 어떻게 확보할까요? 가격 책정을 어떻게 해야 할까요?",
            "required": False,
        },
    ]
}


def get_survey_form_spec() -> Dict[str, Any]:
    """프론트엔드용 설문 폼 스펙 반환"""
    return SURVEY_FORM_SPEC
