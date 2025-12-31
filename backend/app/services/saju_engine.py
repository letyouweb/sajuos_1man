"""
사주 계산 엔진 (API 래퍼)
- engine_v2.py의 검증된 천문학 기반 엔진 사용
- KASI API (Source of Truth) + ephem (Fallback)
- API 응답 형식에 맞게 변환
- 🔥 대운 간지 리스트 생성 (월주 기준)
"""
import logging
from typing import Optional, List
from dataclasses import dataclass

from app.models.schemas import Pillar, SajuWonGuk, DaeunInfo, QualityInfo
from app.services.engine_v2 import (
    ScientificSajuEngine, 
    SajuManager,
    scientific_engine, 
    CalculationError,
    EPHEM_AVAILABLE,
    GAN,
    JI,
    GAN_TO_ELEMENT,
    JI_TO_ELEMENT,
    DAY_MASTER_DESC
)
from app.config import get_settings

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 60갑자 + 대운 리스트 생성
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_sixty_ganji_list() -> List[str]:
    """60갑자 표준 순서 (갑자부터 1칸씩 증가)"""
    stems = ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계"]
    branches = ["자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해"]
    return [f"{stems[i % 10]}{branches[i % 12]}" for i in range(60)]

SIXTY_GANJI = get_sixty_ganji_list()


def normalize_ganji(s: Optional[str]) -> str:
    """입력 문자열을 '갑자' 형태로 정규화"""
    if not s:
        return ""
    return str(s).strip().replace(" ", "")


def calc_daeun_pillars(month_ganji: str, direction: str, count: int = 10) -> List[str]:
    """
    🔥 월주 기준 대운 간지 리스트 생성
    - forward(순행): 다음 간지부터
    - backward(역행): 이전 간지부터
    """
    mg = normalize_ganji(month_ganji)
    if not mg:
        return []
    
    try:
        idx = SIXTY_GANJI.index(mg)
    except ValueError:
        logger.warning(f"[Daeun] 60갑자에서 월주 못 찾음: {mg}")
        return []
    
    out = []
    cur = idx
    for _ in range(count):
        if direction == "forward":
            cur = (cur + 1) % 60
        else:
            cur = (cur - 1) % 60
        out.append(SIXTY_GANJI[cur])
    
    return out


@dataclass
class CalculationResult:
    """계산 결과"""
    saju: SajuWonGuk
    day_master: str
    day_master_element: str
    day_master_description: str
    daeun: Optional[DaeunInfo]
    quality: QualityInfo


class SajuEngine:
    """
    사주 계산 엔진 (API 래퍼)
    """
    
    def __init__(self):
        if not EPHEM_AVAILABLE:
            raise ImportError("ephem 라이브러리가 필요합니다.")
        
        self.engine = scientific_engine
        settings = get_settings()
        self.manager = SajuManager(kasi_api_key=settings.kasi_api_key)
    
    def calculate(
        self,
        year: int,
        month: int,
        day: int,
        hour: Optional[int] = None,
        minute: int = 0,
        gender: Optional[str] = None,
        timezone: str = "Asia/Seoul",
        use_solar_time: bool = True,
        current_age: Optional[int] = None
    ) -> CalculationResult:
        """동기 사주 계산 (ephem only)"""
        result = self.engine.calculate(
            year=year, month=month, day=day,
            hour=hour, minute=minute,
            use_solar_time=use_solar_time
        )
        return self._to_calculation_result(result, hour, gender, timezone, current_age)
    
    async def calculate_async(
        self,
        year: int,
        month: int,
        day: int,
        hour: Optional[int] = None,
        minute: int = 0,
        gender: Optional[str] = None,
        timezone: str = "Asia/Seoul",
        use_solar_time: bool = True,
        current_age: Optional[int] = None
    ) -> CalculationResult:
        """비동기 사주 계산 (KASI → ephem fallback)"""
        result = await self.manager.calculate(
            year=year, month=month, day=day,
            hour=hour, minute=minute,
            use_solar_time=use_solar_time
        )
        return self._to_calculation_result(result, hour, gender, timezone, current_age)
    
    def _to_calculation_result(
        self,
        result: dict,
        hour: Optional[int],
        gender: Optional[str],
        timezone: str,
        current_age: Optional[int] = None
    ) -> CalculationResult:
        """내부 결과 → CalculationResult 변환"""
        
        year_pillar = self._to_pillar(result["year_pillar"])
        month_pillar = self._to_pillar(result["month_pillar"])
        day_pillar = self._to_pillar(result["day_pillar"])
        hour_pillar = self._to_pillar(result["hour_pillar"]) if result["hour_pillar"] else None
        
        saju = SajuWonGuk(
            year_pillar=year_pillar,
            month_pillar=month_pillar,
            day_pillar=day_pillar,
            hour_pillar=hour_pillar
        )
        
        meta = result["meta"]
        quality = QualityInfo(
            has_birth_time=hour is not None,
            solar_term_boundary=meta.get("is_boundary", False),
            boundary_reason=meta.get("boundary_reason"),
            timezone=timezone,
            calculation_method=meta.get("calculation_method", "unknown")
        )
        
        # 🔥 대운 정보 (월주 기준)
        month_ganji = result["month_pillar"]["ganji"]
        daeun = self._calc_daeun(
            year_gan_idx=result["year_pillar"]["gan_index"],
            gender=gender,
            month_pillar=month_ganji,
            current_age=current_age
        )
        
        return CalculationResult(
            saju=saju,
            day_master=result["day_master"],
            day_master_element=result["day_master_element"],
            day_master_description=result["day_master_description"],
            daeun=daeun,
            quality=quality
        )
    
    def _to_pillar(self, pillar_data: dict) -> Pillar:
        """딕셔너리 → Pillar 객체 변환"""
        return Pillar(
            gan=pillar_data["gan"],
            ji=pillar_data["ji"],
            ganji=pillar_data["ganji"],
            gan_element=pillar_data["gan_element"],
            ji_element=pillar_data["ji_element"],
            gan_index=pillar_data["gan_index"],
            ji_index=pillar_data["ji_index"]
        )
    
    def _calc_daeun(
        self,
        year_gan_idx: int,
        gender: Optional[str],
        month_pillar: Optional[str] = None,
        start_age: int = 3,
        current_age: Optional[int] = None
    ) -> Optional[DaeunInfo]:
        """
        🔥 대운 정보 계산 (월주 기준)
        - 양남음녀 순행, 음남양녀 역행
        - 월주 다음/이전 간지부터 대운 시작
        """
        if not gender:
            return None
        
        # 1) 순행/역행 (양남음녀 순행, 음남양녀 역행)
        is_yang_year = (year_gan_idx % 2 == 0)  # 甲丙戊庚壬 = 양
        is_male = str(gender).lower() in ["male", "m", "남", "남성"]
        
        if (is_male and is_yang_year) or ((not is_male) and (not is_yang_year)):
            direction = "forward"
        else:
            direction = "backward"
        
        # 2) 월주 기준 대운 리스트 생성 (10개)
        daeun_list = []
        if month_pillar:
            daeun_list = calc_daeun_pillars(month_pillar, direction, count=10)
        
        # 3) current_daeun 선택 (10년 단위)
        current_daeun = None
        if current_age is not None and daeun_list:
            idx = max(current_age - start_age, 0) // 10
            if 0 <= idx < len(daeun_list):
                current_daeun = daeun_list[idx]
        
        # 🔥 검증 로그
        logger.info(f"[Daeun] month_pillar={month_pillar} | direction={direction} | list[:3]={daeun_list[:3]} | current={current_daeun}")
        
        return DaeunInfo(
            start_age=start_age,
            direction=direction,
            current_daeun=current_daeun,
            daeun_list=daeun_list
        )
    
    def get_hour_options(self) -> list:
        """시간대 선택 옵션"""
        return self.engine.get_hour_options()
    
    @staticmethod
    def get_today_context() -> str:
        """오늘 날짜 컨텍스트"""
        return SajuManager.get_today_string()
    
    @staticmethod
    def inject_date_context(question: str) -> str:
        """질문에 오늘 날짜 컨텍스트 주입"""
        return SajuManager.inject_today_context(question)


# 싱글톤 인스턴스
saju_engine = None
if EPHEM_AVAILABLE:
    saju_engine = SajuEngine()
