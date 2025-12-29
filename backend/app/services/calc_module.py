"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1️⃣ CALC 모듈 - 사주 8글자 계산
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KASI API로 년/월/일주 계산 + 시주 계산 (시간 있을 경우)
결과를 saju_features.pillars에 저장
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

from app.services.kasi_api import kasi_client
from app.services.ganji import ganji_calc, CHEONGAN, JIJI, GAN_TO_ELEMENT, JI_TO_ELEMENT
from app.services.solar_terms import get_lichun_adjusted_year

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
        """딕셔너리 변환"""
        return {
            "year": asdict(self.year),
            "month": asdict(self.month),
            "day": asdict(self.day),
            "hour": asdict(self.hour) if self.hour else None
        }


class CalcModule:
    """
    사주 8글자 계산 모듈
    
    Features:
    1. KASI API 우선 사용
    2. Fallback: 내부 계산 (ganji_calc)
    3. 입춘 보정 자동 처리
    4. 시주 계산 (시간 있을 경우)
    """
    
    async def calculate_pillars(
        self,
        birth_year: int,
        birth_month: int,
        birth_day: int,
        birth_hour: Optional[int] = None,
        birth_minute: int = 0
    ) -> SajuPillars:
        """
        사주 8글자 계산
        
        Args:
            birth_year: 출생 연도 (양력)
            birth_month: 출생 월
            birth_day: 출생 일
            birth_hour: 출생 시 (0-23, 선택)
            birth_minute: 출생 분 (0-59)
        
        Returns:
            SajuPillars: 년/월/일/시주
        """
        logger.info(f"[CalcModule] 사주 계산 시작: {birth_year}-{birth_month:02d}-{birth_day:02d} {birth_hour}:{birth_minute:02d}")
        
        # 1. KASI API 시도
        year_pillar, month_pillar, day_pillar = await self._try_kasi_api(
            birth_year, birth_month, birth_day
        )
        
        # 2. KASI 실패시 Fallback
        if not year_pillar or not month_pillar or not day_pillar:
            logger.info("[CalcModule] KASI API 실패, Fallback 계산 사용")
            year_pillar, month_pillar, day_pillar = self._fallback_calculation(
                birth_year, birth_month, birth_day
            )
        
        # 3. 시주 계산 (시간 있을 경우)
        hour_pillar = None
        if birth_hour is not None:
            hour_pillar = self._calculate_hour_pillar(
                day_pillar.gan_index, birth_hour, birth_minute
            )
        
        result = SajuPillars(
            year=year_pillar,
            month=month_pillar,
            day=day_pillar,
            hour=hour_pillar
        )
        
        logger.info(f"[CalcModule] 계산 완료: {year_pillar.ganji} {month_pillar.ganji} {day_pillar.ganji} {hour_pillar.ganji if hour_pillar else '(시간미상)'}")
        
        return result
    
    async def _try_kasi_api(
        self,
        year: int,
        month: int,
        day: int
    ) -> tuple[Optional[PillarData], Optional[PillarData], Optional[PillarData]]:
        """KASI API로 년/월/일주 계산 시도"""
        
        try:
            ganji_data = await kasi_client.get_ganji_data(year, month, day)
            
            if ganji_data.get("source") == "kasi_api":
                year_ganji = ganji_data["year_ganji"]
                month_ganji = ganji_data["month_ganji"]
                day_ganji = ganji_data["day_ganji"]
                
                # 간지 파싱
                year_gan, year_ji = year_ganji[0], year_ganji[1]
                month_gan, month_ji = month_ganji[0], month_ganji[1]
                day_gan, day_ji = day_ganji[0], day_ganji[1]
                
                # 인덱스 찾기
                year_gan_idx = CHEONGAN.index(year_gan)
                year_ji_idx = JIJI.index(year_ji)
                month_gan_idx = CHEONGAN.index(month_gan)
                month_ji_idx = JIJI.index(month_ji)
                day_gan_idx = CHEONGAN.index(day_gan)
                day_ji_idx = JIJI.index(day_ji)
                
                year_pillar = PillarData(
                    gan=year_gan,
                    ji=year_ji,
                    ganji=year_ganji,
                    gan_element=GAN_TO_ELEMENT[year_gan],
                    ji_element=JI_TO_ELEMENT[year_ji],
                    gan_index=year_gan_idx,
                    ji_index=year_ji_idx
                )
                
                month_pillar = PillarData(
                    gan=month_gan,
                    ji=month_ji,
                    ganji=month_ganji,
                    gan_element=GAN_TO_ELEMENT[month_gan],
                    ji_element=JI_TO_ELEMENT[month_ji],
                    gan_index=month_gan_idx,
                    ji_index=month_ji_idx
                )
                
                day_pillar = PillarData(
                    gan=day_gan,
                    ji=day_ji,
                    ganji=day_ganji,
                    gan_element=GAN_TO_ELEMENT[day_gan],
                    ji_element=JI_TO_ELEMENT[day_ji],
                    gan_index=day_gan_idx,
                    ji_index=day_ji_idx
                )
                
                logger.info("[CalcModule] KASI API 성공")
                return year_pillar, month_pillar, day_pillar
        
        except Exception as e:
            logger.warning(f"[CalcModule] KASI API 오류: {e}")
        
        return None, None, None
    
    def _fallback_calculation(
        self,
        year: int,
        month: int,
        day: int
    ) -> tuple[PillarData, PillarData, PillarData]:
        """내부 계산 (ganji_calc) - Fallback"""
        
        # 1. 입춘 보정된 연도 계산
        adjusted_year = get_lichun_adjusted_year(year, month, day)
        
        # 2. 년주 계산
        year_gan, year_ji, year_gan_idx, year_ji_idx = ganji_calc.calc_year_ganji(adjusted_year)
        
        # 3. 월주 계산
        # 월지 인덱스: 1월=인(0), 2월=묘(1), ..., 12월=축(11)
        month_ji_idx = (month - 1) % 12
        month_gan, month_ji, month_gan_idx, month_ji_actual_idx = ganji_calc.calc_month_ganji(
            year_gan_idx, month_ji_idx
        )
        
        # 4. 일주 계산
        day_gan, day_ji, day_gan_idx, day_ji_idx = ganji_calc.calc_day_ganji(year, month, day)
        
        year_pillar = PillarData(
            gan=year_gan,
            ji=year_ji,
            ganji=f"{year_gan}{year_ji}",
            gan_element=GAN_TO_ELEMENT[year_gan],
            ji_element=JI_TO_ELEMENT[year_ji],
            gan_index=year_gan_idx,
            ji_index=year_ji_idx
        )
        
        month_pillar = PillarData(
            gan=month_gan,
            ji=month_ji,
            ganji=f"{month_gan}{month_ji}",
            gan_element=GAN_TO_ELEMENT[month_gan],
            ji_element=JI_TO_ELEMENT[month_ji],
            gan_index=month_gan_idx,
            ji_index=month_ji_actual_idx
        )
        
        day_pillar = PillarData(
            gan=day_gan,
            ji=day_ji,
            ganji=f"{day_gan}{day_ji}",
            gan_element=GAN_TO_ELEMENT[day_gan],
            ji_element=JI_TO_ELEMENT[day_ji],
            gan_index=day_gan_idx,
            ji_index=day_ji_idx
        )
        
        return year_pillar, month_pillar, day_pillar
    
    def _calculate_hour_pillar(
        self,
        day_gan_idx: int,
        hour: int,
        minute: int
    ) -> PillarData:
        """시주 계산"""
        
        hour_gan, hour_ji, hour_gan_idx, hour_ji_idx = ganji_calc.calc_hour_ganji(
            day_gan_idx, hour, minute
        )
        
        return PillarData(
            gan=hour_gan,
            ji=hour_ji,
            ganji=f"{hour_gan}{hour_ji}",
            gan_element=GAN_TO_ELEMENT[hour_gan],
            ji_element=JI_TO_ELEMENT[hour_ji],
            gan_index=hour_gan_idx,
            ji_index=hour_ji_idx
        )


# 싱글톤 인스턴스
calc_module = CalcModule()
