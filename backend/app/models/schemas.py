"""
Pydantic 스키마 정의
API 요청/응답 모델 - 재설계 버전
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any
from datetime import date
from enum import Enum


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class ConcernType(str, Enum):
    LOVE = "love"           # 연애/결혼
    WEALTH = "wealth"       # 재물/금전
    CAREER = "career"       # 직장/사업
    HEALTH = "health"       # 건강
    STUDY = "study"         # 학업/시험
    GENERAL = "general"     # 종합/기타


# ============ /calculate 요청/응답 ============

class CalculateRequest(BaseModel):
    """사주 계산 요청"""
    birth_year: int = Field(..., ge=1900, le=2100, description="출생 년도 (양력)")
    birth_month: int = Field(..., ge=1, le=12, description="출생 월")
    birth_day: int = Field(..., ge=1, le=31, description="출생 일")
    birth_hour: Optional[int] = Field(None, ge=0, le=23, description="출생 시간 (0-23시, 선택)")
    birth_minute: int = Field(0, ge=0, le=59, description="출생 분 (0-59)")
    gender: Optional[Gender] = Field(None, description="성별")
    timezone: str = Field("Asia/Seoul", description="타임존")
    
    class Config:
        json_schema_extra = {
            "example": {
                "birth_year": 1978,
                "birth_month": 5,
                "birth_day": 16,
                "birth_hour": 10,
                "birth_minute": 30,
                "gender": "male",
                "timezone": "Asia/Seoul"
            }
        }


class Pillar(BaseModel):
    """사주 기둥 (년/월/일/시주)"""
    gan: str = Field(..., description="천간 (갑을병정무기경신임계)")
    ji: str = Field(..., description="지지 (자축인묘진사오미신유술해)")
    ganji: str = Field(..., description="간지 조합 (예: 갑자)")
    
    # 오행 정보
    gan_element: str = Field(..., description="천간 오행 (목화토금수)")
    ji_element: str = Field(..., description="지지 오행")
    
    # 인덱스 (내부 계산용)
    gan_index: Optional[int] = Field(None, description="천간 인덱스 (0-9)")
    ji_index: Optional[int] = Field(None, description="지지 인덱스 (0-11)")


class SajuWonGuk(BaseModel):
    """사주 원국 (4개 기둥)"""
    year_pillar: Pillar = Field(..., description="년주")
    month_pillar: Pillar = Field(..., description="월주")
    day_pillar: Pillar = Field(..., description="일주 (일간=나)")
    hour_pillar: Optional[Pillar] = Field(None, description="시주 (시간 미입력시 None)")


class DaeunInfo(BaseModel):
    """대운 정보"""
    start_age: int = Field(..., description="대운 시작 나이")
    direction: Literal["forward", "backward"] = Field(..., description="대운 방향 (순행/역행)")
    current_daeun: Optional[str] = Field(None, description="현재 대운")
    daeun_list: List[str] = Field(default_factory=list, description="대운 간지 리스트 (10개)")


class QualityInfo(BaseModel):
    """계산 품질 정보 (정확도 배지용)"""
    has_birth_time: bool = Field(..., description="출생시간 입력 여부")
    solar_term_boundary: bool = Field(..., description="절기 경계 여부")
    boundary_reason: Optional[str] = Field(None, description="경계 사유 (near_ipchun/near_term_change/approx_calculation)")
    timezone: str = Field("Asia/Seoul", description="타임존")
    calculation_method: str = Field("solar_term_based", description="계산 방식")


class CalculateResponse(BaseModel):
    """사주 계산 응답"""
    success: bool = True
    
    # 입력 정보 에코
    birth_info: str = Field(..., description="입력된 생년월일 (예: 1988년 8월 8일 8시)")
    
    # 사주 원국
    saju: SajuWonGuk
    
    # 일간 정보 (핵심)
    day_master: str = Field(..., description="일간 (나를 나타내는 글자)")
    day_master_element: str = Field(..., description="일간 오행")
    day_master_description: str = Field(..., description="일간 설명")
    
    # 대운 정보
    daeun: Optional[DaeunInfo] = None
    
    # 품질 정보 (정확도 배지용)
    quality: QualityInfo
    
    # 레거시 호환 (제거 예정)
    is_boundary_date: bool = Field(False, description="절기 경계일 여부 (레거시)")
    boundary_warning: Optional[str] = Field(None, description="경계일 경고 메시지 (레거시)")
    calculation_method: str = Field("solar_term_based", description="계산 방식 (레거시)")


class HourOption(BaseModel):
    """시간대 선택 옵션"""
    index: int = Field(..., description="지지 인덱스 (0-11)")
    ji: str = Field(..., description="지지 한글 (자~해)")
    ji_hanja: str = Field(..., description="지지 한자 (子~亥)")
    range_start: str = Field(..., description="시작 시간 (HH:MM)")
    range_end: str = Field(..., description="종료 시간 (HH:MM)")
    label: str = Field(..., description="표시 라벨")


# ============ /interpret 요청/응답 ============

class InterpretRequest(BaseModel):
    """사주 해석 요청"""
    # 사주 계산 결과 (또는 직접 입력)
    saju_result: Optional[CalculateResponse] = Field(None, description="/calculate 응답 결과")
    
    # 또는 직접 사주 입력
    year_pillar: Optional[str] = Field(None, description="년주 (예: 무오)")
    month_pillar: Optional[str] = Field(None, description="월주")
    day_pillar: Optional[str] = Field(None, description="일주")
    hour_pillar: Optional[str] = Field(None, description="시주")
    
    # 사용자 정보
    name: str = Field("고객님", description="이름/닉네임")
    gender: Optional[Gender] = None
    
    # 고민/질문
    concern_type: ConcernType = Field(ConcernType.GENERAL, description="고민 유형")
    question: str = Field(..., min_length=5, max_length=500, description="구체적인 고민/질문")
    
    # 2026 신년운세용: target_year 강제
    target_year: Optional[int] = Field(2026, description="분석 기준 연도 (기본: 2026)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "year_pillar": "무오",
                "month_pillar": "정사",
                "day_pillar": "무인",
                "hour_pillar": "정사",
                "name": "홍길동",
                "gender": "male",
                "concern_type": "career",
                "question": "올해 이직 운세가 궁금합니다."
            }
        }


class InterpretResponse(BaseModel):
    """사주 해석 응답 (구조화된 JSON)"""
    success: bool = True
    
    # 요약
    summary: str = Field(..., description="한 줄 요약 (50자 이내)")
    
    # 구조화된 분석
    structure: Optional[Dict[str, Any]] = Field(None, description="구조화된 분석 데이터")
    
    # 핵심 분석
    day_master_analysis: str = Field(..., description="일간(나) 분석")
    strengths: List[str] = Field(..., description="강점/장점 (2-3개)")
    risks: List[str] = Field(..., description="주의점/약점 (2-3개)")
    
    # 질문에 대한 답변
    answer: str = Field(..., description="사용자 질문에 대한 구체적 답변")
    
    # 행동 지침
    action_plan: List[str] = Field(..., description="구체적 행동 조언 (3개)")
    
    # 시기 정보
    lucky_periods: List[str] = Field(..., description="좋은 시기 (2-3개)")
    caution_periods: List[str] = Field([], description="조심할 시기")
    
    # 행운 요소
    lucky_elements: Optional[dict] = Field(None, description="행운 요소 (색상/방향/숫자)")
    
    # 마무리
    blessing: str = Field(..., description="축복/응원 메시지")
    
    # 필수 면책조항
    disclaimer: str = Field(
        "본 해석은 오락/참고 목적으로 제공되며, 의학/법률/투자 등 전문적 조언을 대체하지 않습니다.",
        description="면책조항"
    )
    
    # 메타데이터
    model_used: str = Field(..., description="사용된 AI 모델")
    tokens_used: Optional[int] = Field(None, description="사용된 토큰 수")


# ============ 에러 응답 ============

class ErrorResponse(BaseModel):
    """에러 응답"""
    success: bool = False
    error_code: str
    message: str
    detail: Optional[str] = None

