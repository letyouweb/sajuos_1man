"""
캐시 서비스
- 동일 입력에 대한 계산 결과 캐싱
- 메모리 기반 (Redis 연동은 추후)
"""
from typing import Optional, Any
from cachetools import TTLCache, LRUCache
import hashlib
import json
from datetime import datetime

from app.config import get_settings


class CacheService:
    """
    계산 결과 캐싱 서비스
    
    캐시 전략:
    1. /calculate 결과: TTL 24시간 (날짜별 간지는 고정값)
    2. KASI API 응답: TTL 7일 (잘 바뀌지 않음)
    3. /interpret 결과: 캐시 안 함 (LLM 응답은 매번 다름)
    """
    
    def __init__(self):
        settings = get_settings()
        
        # 사주 계산 결과 캐시 (날짜 -> 간지 매핑)
        self.saju_cache = TTLCache(
            maxsize=settings.cache_max_size,
            ttl=settings.cache_ttl_seconds
        )
        
        # KASI API 응답 캐시
        self.kasi_cache = TTLCache(
            maxsize=10000,
            ttl=86400 * 7  # 7일
        )
        
        # 통계
        self._hits = 0
        self._misses = 0
    
    def _make_key(self, *args) -> str:
        """캐시 키 생성"""
        key_str = json.dumps(args, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    # ========== 사주 계산 캐시 ==========
    
    def get_saju(self, year: int, month: int, day: int, hour: Optional[int] = None) -> Optional[dict]:
        """사주 계산 결과 캐시 조회"""
        key = self._make_key("saju", year, month, day, hour)
        result = self.saju_cache.get(key)
        
        if result:
            self._hits += 1
        else:
            self._misses += 1
        
        return result
    
    def set_saju(self, year: int, month: int, day: int, hour: Optional[int], data: dict):
        """사주 계산 결과 캐시 저장"""
        key = self._make_key("saju", year, month, day, hour)
        self.saju_cache[key] = data
    
    # ========== KASI API 캐시 ==========
    
    def get_kasi(self, year: int, month: int, day: int) -> Optional[dict]:
        """KASI API 응답 캐시 조회"""
        key = self._make_key("kasi", year, month, day)
        return self.kasi_cache.get(key)
    
    def set_kasi(self, year: int, month: int, day: int, data: dict):
        """KASI API 응답 캐시 저장"""
        key = self._make_key("kasi", year, month, day)
        self.kasi_cache[key] = data
    
    # ========== 통계 ==========
    
    def get_stats(self) -> dict:
        """캐시 통계 조회"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "saju_cache_size": len(self.saju_cache),
            "kasi_cache_size": len(self.kasi_cache)
        }
    
    def clear(self):
        """캐시 초기화"""
        self.saju_cache.clear()
        self.kasi_cache.clear()
        self._hits = 0
        self._misses = 0


# 싱글톤 인스턴스
cache_service = CacheService()
