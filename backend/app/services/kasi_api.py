"""
한국천문연구원(KASI) API 연동 모듈
- 음양력 정보 API
- 절기 정보 API
- 간지(세차/월건/일진) 데이터 확보
"""
import httpx
from typing import Optional, Dict, Any
from datetime import date
import logging
from functools import lru_cache

from app.config import get_settings

logger = logging.getLogger(__name__)


class KasiApiClient:
    """
    한국천문연구원 공공데이터 API 클라이언트
    
    사용 API:
    1. 음양력 정보 조회 (간지 포함)
       - URL: http://apis.data.go.kr/B090041/openapi/service/LrsrCldInfoService/getLunCalInfo
    
    2. 특일정보 - 24절기 조회
       - URL: http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/get24DivisionsInfo
    """
    
    BASE_URL_LUNAR = "http://apis.data.go.kr/B090041/openapi/service/LrsrCldInfoService"
    BASE_URL_SPECIAL = "http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService"
    
    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.kasi_api_key
    
    async def get_lunar_info(
        self,
        year: int,
        month: int,
        day: int
    ) -> Optional[Dict[str, Any]]:
        """
        양력 날짜로 음양력 정보 조회 (간지 포함)
        
        Returns:
            {
                "solYear": "2025",
                "solMonth": "01",
                "solDay": "01",
                "lunYear": "2024",
                "lunMonth": "12",
                "lunDay": "02",
                "lunSecha": "갑진",      # 년 간지
                "lunWolgeon": "병자",    # 월 간지  
                "lunIljin": "임오"       # 일 간지
            }
        """
        if not self.api_key:
            logger.warning("KASI API key not configured, using fallback")
            return None
        
        url = f"{self.BASE_URL_LUNAR}/getLunCalInfo"
        params = {
            "serviceKey": self.api_key,
            "solYear": str(year),
            "solMonth": str(month).zfill(2),
            "solDay": str(day).zfill(2),
            "_type": "json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                # 응답 파싱
                items = (
                    data.get("response", {})
                    .get("body", {})
                    .get("items", {})
                    .get("item", {})
                )
                
                if items:
                    return {
                        "year_ganji": items.get("lunSecha", ""),      # 세차 (년 간지)
                        "month_ganji": items.get("lunWolgeon", ""),   # 월건 (월 간지)
                        "day_ganji": items.get("lunIljin", ""),       # 일진 (일 간지)
                        "lunar_year": items.get("lunYear", ""),
                        "lunar_month": items.get("lunMonth", ""),
                        "lunar_day": items.get("lunDay", ""),
                        "is_leap_month": items.get("lunLeapmonth", "") == "윤"
                    }
                
                return None
                
        except httpx.HTTPError as e:
            logger.error(f"KASI API HTTP error: {e}")
            return None
        except Exception as e:
            logger.error(f"KASI API error: {e}")
            return None
    
    async def get_solar_terms(
        self,
        year: int,
        month: int
    ) -> Optional[Dict[str, Any]]:
        """
        해당 월의 24절기 정보 조회
        
        Returns:
            {
                "term_name": "입춘",
                "term_date": "2025-02-03",
                "term_time": "23:10"
            }
        """
        if not self.api_key:
            return None
        
        url = f"{self.BASE_URL_SPECIAL}/get24DivisionsInfo"
        params = {
            "serviceKey": self.api_key,
            "solYear": str(year),
            "solMonth": str(month).zfill(2),
            "_type": "json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                items = (
                    data.get("response", {})
                    .get("body", {})
                    .get("items", {})
                    .get("item", [])
                )
                
                # 여러 절기가 있을 수 있음 (입절, 중기)
                if items:
                    if isinstance(items, dict):
                        items = [items]
                    
                    result = []
                    for item in items:
                        result.append({
                            "name": item.get("dateName", ""),
                            "date": item.get("locdate", ""),
                            "is_holiday": item.get("isHoliday", "N") == "Y"
                        })
                    return result
                
                return None
                
        except Exception as e:
            logger.error(f"KASI Solar Terms API error: {e}")
            return None
    
    async def get_ganji_data(
        self,
        year: int,
        month: int,
        day: int
    ) -> Dict[str, str]:
        """
        간지 데이터 통합 조회 (캐시 친화적)
        
        Returns:
            {
                "year_ganji": "갑진",
                "month_ganji": "병자",
                "day_ganji": "임오",
                "source": "kasi_api" | "fallback"
            }
        """
        # KASI API 먼저 시도
        lunar_info = await self.get_lunar_info(year, month, day)
        
        if lunar_info and lunar_info.get("year_ganji"):
            return {
                "year_ganji": lunar_info["year_ganji"],
                "month_ganji": lunar_info["month_ganji"],
                "day_ganji": lunar_info["day_ganji"],
                "source": "kasi_api"
            }
        
        # Fallback: 내부 계산
        logger.info(f"Using fallback calculation for {year}-{month}-{day}")
        return {
            "year_ganji": None,  # saju_engine이 계산
            "month_ganji": None,
            "day_ganji": None,
            "source": "fallback"
        }


# 싱글톤 인스턴스
kasi_client = KasiApiClient()
