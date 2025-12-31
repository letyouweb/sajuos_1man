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
        양력 날짜로 음양력 정보 조회 (캐시 우선) + 원본/정규화 동시 저장

        흐름:
        1) 캐시 조회 (sol_year, sol_month, sol_day)
           - hit: payload(정규화) 반환 + raw를 "raw" 키로 함께 제공
        2) miss: KASI(getLunCalInfo) 호출
           - 성공: payload_norm + payload_raw 동시 upsert 후 반환
        3) KASI 실패:
           - 캐시 있으면 캐시로 폴백
           - 캐시도 없으면 "calendar unavailable" 에러
        """
        ymd = f"{year}-{month:02d}-{day:02d}"

        # 1) 캐시 먼저 조회
        try:
            supabase = self._get_supabase()
            cached = supabase.get_calendar_cache(year, month, day)
            if cached and cached.get("payload"):
                logger.info(f"[KASI] cache hit: {ymd}")
                norm = cached.get("payload") or {}
                raw = cached.get("payload_raw")
                # 반환은 기존 하위호환 유지: 정규화 필드를 최상단에 두고 raw만 추가
                payload = dict(norm)
                if raw is not None:
                    payload["raw"] = raw
                payload["source"] = "cache"
                return payload
        except Exception as e:
            logger.warning(f"[KASI] cache read error: {e}")

        # 2) 캐시 miss -> KASI API 호출
        logger.info(f"[KASI] cache miss, calling API: {ymd}")

        if not self.api_key:
            raise RuntimeError("KASI API key not configured")

        url = f"{self.BASE_URL}/getLunCalInfo"
        params = {
            "serviceKey": self.api_key,
            "solYear": str(year),
            "solMonth": str(month).zfill(2),
            "solDay": str(day).zfill(2),
            "_type": "json",
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                payload_raw = response.json()  # ✅ 원본 JSON 통째 저장
                item = (
                    payload_raw.get("response", {})
                    .get("body", {})
                    .get("items", {})
                    .get("item", {})
                )

                if not item:
                    raise RuntimeError(f"KASI returned empty for {ymd}")

                # ✅ 정규화(서비스에서 바로 쓰는 형태)
                payload_norm = {
                    "year_ganji": item.get("lunSecha", ""),
                    "month_ganji": item.get("lunWolgeon", ""),
                    "day_ganji": item.get("lunIljin", ""),
                    "lunar_year": item.get("lunYear", ""),
                    "lunar_month": item.get("lunMonth", ""),
                    "lunar_day": item.get("lunDay", ""),
                    "is_leap_month": item.get("lunLeapmonth", "") == "윤",
                }

                # 3) 성공이면 캐시 저장 (실패해도 본 흐름은 계속)
                try:
                    supabase = self._get_supabase()
                    supabase.upsert_calendar_cache(
                        year, month, day,
                        payload_norm=payload_norm,
                        payload_raw=payload_raw,
                        source="kasi",
                    )
                    logger.info(f"[KASI] cache upsert success: {ymd}")
                except Exception as e:
                    logger.warning(f"[KASI] cache upsert fail: {e}")

                # 반환: 하위호환(정규화 필드 최상단) + raw 포함
                out = dict(payload_norm)
                out["raw"] = payload_raw
                out["source"] = "kasi"
                return out

        except Exception as e:
            # 로그 폭주 방지: error 대신 warning 권장
            logger.warning(f"[KASI] API error: {e}")

            # 4) KASI 실패 -> 캐시 폴백
            try:
                supabase = self._get_supabase()
                cached = supabase.get_calendar_cache(year, month, day)
                if cached and cached.get("payload"):
                    logger.info("[KASI] fallback to cache after API failure")
                    norm = cached.get("payload") or {}
                    raw = cached.get("payload_raw")
                    payload = dict(norm)
                    if raw is not None:
                        payload["raw"] = raw
                    payload["source"] = "cache_fallback"
                    return payload
            except Exception:
                pass

            # 5) 캐시도 없으면 에러
            raise RuntimeError(f"calendar unavailable for {ymd}")

    async def get_ganji_data(self, year: int, month: int, day: int) -> Dict[str, str]:
(self, year: int, month: int, day: int) -> Dict[str, str]:
        """간지 데이터 통합 조회 (KASI-only + 캐시)"""
        lunar_info = await self.get_lunar_info_with_cache(year, month, day)
        return {
            "year_ganji": lunar_info.get("year_ganji", ""),
            "month_ganji": lunar_info.get("month_ganji", ""),
            "day_ganji": lunar_info.get("day_ganji", ""),
            "source": lunar_info.get("source", "kasi")
        }


kasi_client = KasiApiClient()
