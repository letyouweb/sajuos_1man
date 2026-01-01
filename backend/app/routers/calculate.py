"""
/calculate 엔드포인트 - KASI API 통합 v3

Source of Truth 우선순위:
1. KASI API (한국천문연구원) - 실시간 데이터
2. ephem (NASA JPL) - Fallback

특징:
- API 실패시 자동 fallback (서비스 무중단)
- 태양시 보정 ON/OFF 토글 지원
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
import logging

from app.models.schemas import (
    CalculateRequest,
    CalculateResponse,
    ErrorResponse,
    HourOption
)
from app.services.engine_v2 import CalculationError, EPHEM_AVAILABLE, SajuManager
from app.services.saju_engine import saju_engine
from app.services.cache import cache_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/calculate",
    response_model=CalculateResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse}
    },
    summary="사주 계산 (KASI API + ephem 통합)",
    description="""
생년월일을 입력받아 사주 원국을 계산합니다.

**Source of Truth 우선순위:**
1. **KASI API** (한국천문연구원) - 공식 데이터
2. **ephem** (NASA JPL) - Fallback

**태양시 보정 (Toggle):**
- `use_solar_time=true`: 한국 표준시 -30분 보정 (권장)
- `use_solar_time=false`: 시계 시간 그대로 사용

**고가용성:**
- KASI API 실패시 자동으로 ephem fallback
- 서비스 중단 없는 안정적인 응답
    """
)
async def calculate_saju(
    request: CalculateRequest,
    use_solar_time: bool = Query(True, description="태양시 보정 ON/OFF")
):
    """
    사주 계산 API (KASI 우선, ephem Fallback)
    """
    
    # 🔥 P0 FIX: ephem 체크 제거 - KASI-only로도 동작 가능
    # ephem이 없어도 KASI API로 계산 가능
    
    if saju_engine is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": "ENGINE_NOT_READY",
                "message": "사주 엔진이 초기화되지 않았습니다."
            }
        )
    
    year = request.birth_year
    month = request.birth_month
    day = request.birth_day
    hour = request.birth_hour
    minute = request.birth_minute
    gender = request.gender.value if request.gender else None
    timezone = request.timezone
    
    # 사주 계산 (KASI 우선 → ephem Fallback)
    try:
        # 비동기 계산 (KASI API → ephem fallback)
        result = await saju_engine.calculate_async(
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            gender=gender,
            timezone=timezone,
            use_solar_time=use_solar_time
        )
        
        # 응답 구성
        birth_info = f"{year}년 {month}월 {day}일"
        if hour is not None:
            birth_info += f" {hour}시"
            if minute > 0:
                birth_info += f" {minute}분"
        
        # 경계 경고 메시지
        boundary_warning = None
        if result.quality.solar_term_boundary:
            if result.quality.boundary_reason == "near_ipchun":
                boundary_warning = (
                    f"⚠️ 입춘 경계일 근처입니다. "
                    f"출생시간에 따라 연주/월주가 달라질 수 있습니다."
                )
            elif result.quality.boundary_reason == "near_term_change":
                boundary_warning = (
                    f"⚠️ 절기 경계일 근처입니다. "
                    f"출생시간에 따라 월주가 달라질 수 있습니다."
                )
        
        response_data = {
            "success": True,
            "birth_info": birth_info,
            "saju": result.saju.model_dump(),
            "day_master": result.day_master,
            "day_master_element": result.day_master_element,
            "day_master_description": result.day_master_description,
            "daeun": result.daeun.model_dump() if result.daeun else None,
            "quality": result.quality.model_dump(),
            # 레거시 호환
            "is_boundary_date": result.quality.solar_term_boundary,
            "boundary_warning": boundary_warning,
            "calculation_method": result.quality.calculation_method
        }
        
        logger.info(f"Saju calculated: {year}-{month}-{day} | Source: {result.quality.calculation_method}")
        
        return CalculateResponse(**response_data)
        
    except CalculationError as e:
        logger.error(f"Calculation error: {type(e).__name__}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "CALCULATION_ERROR",
                "message": "사주 계산에 실패했습니다.",
                "detail": str(e)
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error: {type(e).__name__}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "INTERNAL_ERROR",
                "message": "서버 내부 오류가 발생했습니다.",
                "detail": str(e)
            }
        )


@router.get(
    "/calculate/hour-options",
    response_model=List[HourOption],
    summary="시간대 선택 옵션",
    description="출생 시간 입력을 위한 시간대(2시간 단위) 선택 옵션 목록"
)
async def get_hour_options():
    """시간대 선택 옵션 목록"""
    if saju_engine is None:
        from app.services.engine_v2 import HOUR_OPTIONS
        return [
            {
                "index": h["index"],
                "ji": h["ji"],
                "ji_hanja": h["ji_hanja"],
                "range_start": h["start"],
                "range_end": h["end"],
                "label": f"{h['ji_hanja']}시 ({h['ji']}시) - {h['start']}~{h['end']}"
            }
            for h in HOUR_OPTIONS
        ]
    return saju_engine.get_hour_options()


@router.get(
    "/calculate/today",
    summary="오늘 날짜 (KST)",
    description="서버의 현재 날짜를 반환합니다. 연도 착각 방지용."
)
async def get_today():
    """오늘 날짜 반환 (KST)"""
    today = SajuManager.get_today_kst()
    return {
        "today": SajuManager.get_today_string(),
        "year": today.year,
        "month": today.month,
        "day": today.day,
        "timezone": "Asia/Seoul"
    }


@router.get(
    "/calculate/compare",
    summary="태양시 보정 ON/OFF 비교",
    description="동일 날짜에 대해 태양시 보정 ON/OFF 결과를 나란히 비교합니다."
)
async def compare_solar_time(
    year: int = Query(..., ge=1900, le=2100),
    month: int = Query(..., ge=1, le=12),
    day: int = Query(..., ge=1, le=31),
    hour: int = Query(..., ge=0, le=23),
    minute: int = Query(0, ge=0, le=59)
):
    """
    태양시 보정 ON/OFF 비교
    """
    
    if saju_engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")
    
    # 태양시 보정 ON
    result_on = await saju_engine.calculate_async(
        year=year, month=month, day=day,
        hour=hour, minute=minute,
        use_solar_time=True
    )
    
    # 태양시 보정 OFF
    result_off = await saju_engine.calculate_async(
        year=year, month=month, day=day,
        hour=hour, minute=minute,
        use_solar_time=False
    )
    
    return {
        "input": {
            "date": f"{year}-{month:02d}-{day:02d}",
            "time": f"{hour:02d}:{minute:02d}"
        },
        "solar_time_on": {
            "mode": "태양시 보정 ON (-30분)",
            "source": result_on.quality.calculation_method,
            "year": result_on.saju.year_pillar.ganji,
            "month": result_on.saju.month_pillar.ganji,
            "day": result_on.saju.day_pillar.ganji,
            "hour": result_on.saju.hour_pillar.ganji if result_on.saju.hour_pillar else None
        },
        "solar_time_off": {
            "mode": "태양시 보정 OFF (시계 시간)",
            "source": result_off.quality.calculation_method,
            "year": result_off.saju.year_pillar.ganji,
            "month": result_off.saju.month_pillar.ganji,
            "day": result_off.saju.day_pillar.ganji,
            "hour": result_off.saju.hour_pillar.ganji if result_off.saju.hour_pillar else None
        },
        "difference": {
            "hour_pillar_differs": (
                (result_on.saju.hour_pillar.ganji if result_on.saju.hour_pillar else None) !=
                (result_off.saju.hour_pillar.ganji if result_off.saju.hour_pillar else None)
            )
        }
    }


@router.get(
    "/calculate/cache-stats",
    summary="캐시 통계"
)
async def get_cache_stats():
    """캐시 통계 조회"""
    return cache_service.get_stats()
