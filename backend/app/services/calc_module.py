"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1️⃣ CALC 모듈 - 사주 8글자 계산 (KASI-only)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KASI API + calendar_cache로 년/월/일주 계산
시주 계산은 내부 로직 (시간 있을 경우)
ephem 제거, KASI 결과만 사용
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

from app.services.kasi_api import kasi_client
from app.services.ganji import ganji_calc, CHEONGAN, JIJI, GAN_TO_ELEMENT, JI_TO_ELEMENT

logger = logging.getLogger(__name__)


@dataclass
class PillarData:
    """단일 기둥 데이터"""
    gan: str                    # 천간 (갑~계)
    ji: str                     # 지지 (자~해)
    ganji: str                  # 간지 조합
    gan_element: str            # 천간 오행
    ji_element: str             # 지지 오행
    gan_index: int             # 천간 인덱스 (0-9)
    ji_index: int              # 지지 인덱스 (0-11)


@dataclass
class SajuPillars:
    """사주 8글자 (4기둥)"""
    year: PillarData
    month: PillarData
    day: PillarData
    hour: Optional[PillarData]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "year": asdict(self.year),
            "month": asdict(self.month),
            "day": asdict(self.day),
            "hour": asdict(self.hour) if self.hour else None
        }


class CalcModule:
    """
    사주 8글자 계산 모듈 (KASI-only)
    - KASI API + calendar_cache 사용 (년/월/일주)
    - 시주: 내부 계산 (ganji_calc)
    - KASI 실패 시 에러 반환 (ephem fallback 제거)
    """
    
    async def calculate_pillars(
        self,
        birth_year: int,
        birth_month: int,
        birth_day: int,
        birth_hour: Optional[int] = None,
        birth_minute: int = 0
    ) -> SajuPillars:
        logger.info(f"[CalcModule] 사주 계산: {birth_year}-{birth_month:02d}-{birth_day:02d}")
        
        # KASI API + 캐시로 년/월/일주 계산
        year_pillar, month_pillar, day_pillar = await self._get_pillars_from_kasi(
            birth_year, birth_month, birth_day
        )
        
        # 시주 계산 (시간 있을 경우)
        hour_pillar = None
        if birth_hour is not None:
            hour_pillar = self._calculate_hour_pillar(
                day_pillar.gan_index, birth_hour, birth_minute
            )
        
        result = SajuPillars(year=year_pillar, month=month_pillar, day=day_pillar, hour=hour_pillar)
        logger.info(f"[CalcModule] 완료: {year_pillar.ganji} {month_pillar.ganji} {day_pillar.ganji}")
        return result
    
    async def _get_pillars_from_kasi(
        self,
        year: int,
        month: int,
        day: int
    ) -> tuple[PillarData, PillarData, PillarData]:
        """KASI API + 캐시로 년/월/일주 계산"""
        ganji_data = await kasi_client.get_ganji_data(year, month, day)
        
        source = ganji_data.get("source", "unknown")
        logger.info(f"[CalcModule] KASI source={source}")
        
        year_ganji = ganji_data.get("year_ganji", "")
        month_ganji = ganji_data.get("month_ganji", "")
        day_ganji = ganji_data.get("day_ganji", "")
        
        if not year_ganji or not month_ganji or not day_ganji:
            raise RuntimeError(f"calendar unavailable for {year}-{month:02d}-{day:02d}")
        
        # 간지 파싱
        year_gan, year_ji = year_ganji[0], year_ganji[1]
        month_gan, month_ji = month_ganji[0], month_ganji[1]
        day_gan, day_ji = day_ganji[0], day_ganji[1]
        
        year_pillar = PillarData(
            gan=year_gan, ji=year_ji, ganji=year_ganji,
            gan_element=GAN_TO_ELEMENT[year_gan], ji_element=JI_TO_ELEMENT[year_ji],
            gan_index=CHEONGAN.index(year_gan), ji_index=JIJI.index(year_ji)
        )
        month_pillar = PillarData(
            gan=month_gan, ji=month_ji, ganji=month_ganji,
            gan_element=GAN_TO_ELEMENT[month_gan], ji_element=JI_TO_ELEMENT[month_ji],
            gan_index=CHEONGAN.index(month_gan), ji_index=JIJI.index(month_ji)
        )
        day_pillar = PillarData(
            gan=day_gan, ji=day_ji, ganji=day_ganji,
            gan_element=GAN_TO_ELEMENT[day_gan], ji_element=JI_TO_ELEMENT[day_ji],
            gan_index=CHEONGAN.index(day_gan), ji_index=JIJI.index(day_ji)
        )
        return year_pillar, month_pillar, day_pillar
    
    def _calculate_hour_pillar(self, day_gan_idx: int, hour: int, minute: int) -> PillarData:
        hour_gan, hour_ji, hour_gan_idx, hour_ji_idx = ganji_calc.calc_hour_ganji(day_gan_idx, hour, minute)
        return PillarData(
            gan=hour_gan, ji=hour_ji, ganji=f"{hour_gan}{hour_ji}",
            gan_element=GAN_TO_ELEMENT[hour_gan], ji_element=JI_TO_ELEMENT[hour_ji],
            gan_index=hour_gan_idx, ji_index=hour_ji_idx
        )


calc_module = CalcModule()
