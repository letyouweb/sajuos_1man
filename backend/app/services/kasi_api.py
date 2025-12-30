"""
한국천문연구원(KASI) API 연동 모듈 v2 (KASI-only)
- ephem 제거, KASI 결과만 사용
- calendar_cache: Supabase 캐싱 연동
- 실패 시: 캐시 폴백 -> 캐시도 없으면 에러
"""
import httpx
from typing import Optional, Dict, Any
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)


class KasiApiClient:
    """KASI API 클라이언트 (KASI-only + calendar_cache)"""
    
    BASE_URL = "http://apis.data.go.kr/B090041/openapi/service/LrsrCldInfoService"
    
    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.kasi_api_key
        self._supabase = None
    
    def _get_supabase(self):
        """Lazy-init Supabase"""
        if self._supabase is None:
            from app.services.supabase_service import SupabaseService
            self._supabase = SupabaseService()
        return self._supabase
    
    async def get_lunar_info_with_cache(self, year: int, month: int, day: int) -> Dict[str, Any]:
        """
        양력 날짜로 음양력 정보 조회 (캐시 우선)
        1) 캐시 조회 -> hit면 반환
        2) 캐시 miss -> KASI 호출 -> 성공 시 캐시 저장
        3) KASI 실패 -> 캐시 폴백
        4) 캐시도 없으면 에러
        """
        # 1) 캐시 먼저 조회
        try:
            supabase = self._get_supabase()
            cached = supabase.get_calendar_cache(year, month, day)
            if cached and cached.get("payload"):
                logger.info(f"[KASI] cache hit: {year}-{month:02d}-{day:02d}")
                payload = cached["payload"]
                payload["source"] = "cache"
                return payload
        except Exception as e:
            logger.warning(f"[KASI] cache read error: {e}")
        
        # 2) 캐시 miss -> KASI API 호출
        logger.info(f"[KASI] cache miss, calling API: {year}-{month:02d}-{day:02d}")
        
        if not self.api_key:
            raise RuntimeError("KASI API key not configured")
        
        url = f"{self.BASE_URL}/getLunCalInfo"
        params = {
            "serviceKey": self.api_key,
            "solYear": str(year),
            "solMonth": str(month).zfill(2),
            "solDay": str(day).zfill(2),
            "_type": "json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                items = data.get("response", {}).get("body", {}).get("items", {}).get("item", {})
                
                if items:
                    payload = {
                        "year_ganji": items.get("lunSecha", ""),
                        "month_ganji": items.get("lunWolgeon", ""),
                        "day_ganji": items.get("lunIljin", ""),
                        "lunar_year": items.get("lunYear", ""),
                        "lunar_month": items.get("lunMonth", ""),
                        "lunar_day": items.get("lunDay", ""),
                        "is_leap_month": items.get("lunLeapmonth", "") == "윤"
                    }
                    
                    # 3) 성공 시 캐시 저장
                    try:
                        supabase = self._get_supabase()
                        supabase.upsert_calendar_cache(year, month, day, payload, source="kasi")
                        logger.info(f"[KASI] cache upsert success: {year}-{month:02d}-{day:02d}")
                    except Exception as e:
                        logger.warning(f"[KASI] cache upsert fail: {e}")
                    
                    payload["source"] = "kasi"
                    return payload
                
                raise RuntimeError(f"KASI returned empty for {year}-{month:02d}-{day:02d}")
                
        except Exception as e:
            logger.error(f"[KASI] API error: {e}")
            
            # 4) KASI 실패 -> 캐시 폴백 재시도
            try:
                supabase = self._get_supabase()
                cached = supabase.get_calendar_cache(year, month, day)
                if cached and cached.get("payload"):
                    logger.info(f"[KASI] fallback to cache after API failure")
                    payload = cached["payload"]
                    payload["source"] = "cache_fallback"
                    return payload
            except Exception:
                pass
            
            # 5) 캐시도 없으면 에러
            raise RuntimeError(f"calendar unavailable for {year}-{month:02d}-{day:02d}")
    
    async def get_ganji_data(self, year: int, month: int, day: int) -> Dict[str, str]:
        """간지 데이터 통합 조회 (KASI-only + 캐시)"""
        lunar_info = await self.get_lunar_info_with_cache(year, month, day)
        return {
            "year_ganji": lunar_info.get("year_ganji", ""),
            "month_ganji": lunar_info.get("month_ganji", ""),
            "day_ganji": lunar_info.get("day_ganji", ""),
            "source": lunar_info.get("source", "kasi")
        }


kasi_client = KasiApiClient()
