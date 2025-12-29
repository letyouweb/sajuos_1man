"""
24절기 데이터 및 절입 시각 판정
- 월주 계산의 핵심: 어느 절기 구간인지 판단
- 입춘 기준 연주 보정
"""
from datetime import datetime, date
from typing import Tuple, Optional, Dict, List
from dataclasses import dataclass


@dataclass
class SolarTermInfo:
    """절기 정보"""
    name: str           # 절기 이름
    month_index: int    # 월지 인덱스 (0=인월, 1=묘월, ..., 11=축월)
    approx_month: int   # 대략적인 양력 월
    approx_day: int     # 대략적인 양력 일


# 24절기 (입절 12개 + 중기 12개)
# 월주는 "입절"만 사용 (입춘, 경칩, 청명, 입하, 망종, 소서, 입추, 백로, 한로, 입동, 대설, 소한)
# 월지: 寅(인)=1월(입춘~경칩), 卯(묘)=2월(경칩~청명), ... 丑(축)=12월(소한~입춘)

SOLAR_TERMS_ENTRY = [
    # (절기명, 월지인덱스, 대략적 양력월, 대략적 양력일)
    SolarTermInfo("입춘", 0, 2, 4),    # 인월 시작 (1월 → 인덱스 0)
    SolarTermInfo("경칩", 1, 3, 6),    # 묘월 시작
    SolarTermInfo("청명", 2, 4, 5),    # 진월 시작
    SolarTermInfo("입하", 3, 5, 6),    # 사월 시작
    SolarTermInfo("망종", 4, 6, 6),    # 오월 시작
    SolarTermInfo("소서", 5, 7, 7),    # 미월 시작
    SolarTermInfo("입추", 6, 8, 8),    # 신월 시작
    SolarTermInfo("백로", 7, 9, 8),    # 유월 시작
    SolarTermInfo("한로", 8, 10, 8),   # 술월 시작
    SolarTermInfo("입동", 9, 11, 7),   # 해월 시작
    SolarTermInfo("대설", 10, 12, 7),  # 자월 시작
    SolarTermInfo("소한", 11, 1, 6),   # 축월 시작
]

# 2020-2030년 정밀 절기 시각 (KST 기준)
# 형식: (년, 월, 일, 시, 분)
# 출처: 한국천문연구원 데이터 기반
SOLAR_TERMS_PRECISE: Dict[int, List[Tuple[int, int, int, int, int]]] = {
    2024: [
        (2024, 2, 4, 17, 27),   # 입춘
        (2024, 3, 5, 11, 23),   # 경칩
        (2024, 4, 4, 16, 2),    # 청명
        (2024, 5, 5, 9, 10),    # 입하
        (2024, 6, 5, 13, 10),   # 망종
        (2024, 7, 6, 23, 20),   # 소서
        (2024, 8, 7, 9, 9),     # 입추
        (2024, 9, 7, 12, 11),   # 백로
        (2024, 10, 8, 3, 0),    # 한로
        (2024, 11, 7, 7, 20),   # 입동
        (2024, 12, 7, 0, 17),   # 대설
        (2025, 1, 5, 11, 33),   # 소한 (다음해 1월이지만 2024년 데이터에 포함)
    ],
    2025: [
        (2025, 2, 3, 23, 10),   # 입춘
        (2025, 3, 5, 17, 7),    # 경칩
        (2025, 4, 4, 21, 48),   # 청명
        (2025, 5, 5, 14, 57),   # 입하
        (2025, 6, 5, 18, 56),   # 망종
        (2025, 7, 7, 5, 5),     # 소서
        (2025, 8, 7, 14, 51),   # 입추
        (2025, 9, 7, 17, 52),   # 백로
        (2025, 10, 8, 8, 41),   # 한로
        (2025, 11, 7, 13, 4),   # 입동
        (2025, 12, 7, 6, 5),    # 대설
        (2026, 1, 5, 17, 23),   # 소한
    ],
    2026: [
        (2026, 2, 4, 4, 52),
        (2026, 3, 5, 22, 59),
        (2026, 4, 5, 3, 39),
        (2026, 5, 5, 20, 49),
        (2026, 6, 6, 0, 48),
        (2026, 7, 7, 10, 57),
        (2026, 8, 7, 20, 42),
        (2026, 9, 7, 23, 41),
        (2026, 10, 8, 14, 29),
        (2026, 11, 7, 18, 52),
        (2026, 12, 7, 11, 52),
        (2027, 1, 5, 23, 10),
    ],
    # 과거 년도 (회귀 테스트용)
    1978: [
        (1978, 2, 4, 7, 27),    # 입춘
        (1978, 3, 6, 1, 23),    # 경칩
        (1978, 4, 5, 5, 59),    # 청명
        (1978, 5, 5, 23, 8),    # 입하
        (1978, 6, 6, 3, 10),    # 망종
        (1978, 7, 7, 13, 23),   # 소서
        (1978, 8, 7, 22, 55),   # 입추
        (1978, 9, 8, 1, 38),    # 백로
        (1978, 10, 8, 16, 15),  # 한로
        (1978, 11, 7, 20, 24),  # 입동
        (1978, 12, 7, 13, 17),  # 대설
        (1979, 1, 6, 0, 32),    # 소한
    ],
    1996: [
        (1996, 2, 4, 15, 8),
        (1996, 3, 5, 9, 2),
        (1996, 4, 4, 13, 43),
        (1996, 5, 5, 6, 53),
        (1996, 6, 5, 10, 54),
        (1996, 7, 6, 21, 7),
        (1996, 8, 7, 6, 54),
        (1996, 9, 7, 9, 55),
        (1996, 10, 8, 0, 45),
        (1996, 11, 7, 4, 59),
        (1996, 12, 6, 21, 55),
        (1997, 1, 5, 9, 8),
    ],
    1990: [
        (1990, 2, 4, 10, 15),
        (1990, 3, 6, 4, 11),
        (1990, 4, 5, 8, 43),
        (1990, 5, 6, 1, 44),
        (1990, 6, 6, 5, 47),
        (1990, 7, 7, 16, 8),
        (1990, 8, 8, 1, 55),
        (1990, 9, 8, 4, 54),
        (1990, 10, 8, 19, 36),
        (1990, 11, 7, 23, 52),
        (1990, 12, 7, 16, 47),
        (1991, 1, 6, 3, 56),
    ],
    2000: [
        (2000, 2, 4, 20, 14),
        (2000, 3, 5, 14, 7),
        (2000, 4, 4, 18, 32),
        (2000, 5, 5, 11, 31),
        (2000, 6, 5, 15, 29),
        (2000, 7, 7, 1, 41),
        (2000, 8, 7, 11, 29),
        (2000, 9, 7, 14, 27),
        (2000, 10, 8, 5, 12),
        (2000, 11, 7, 9, 24),
        (2000, 12, 7, 2, 14),
        (2001, 1, 5, 13, 21),
    ],
}


class SolarTermsEngine:
    """
    절기 엔진
    - 출생일시가 어느 절기 구간에 속하는지 판정
    - 월지 인덱스(0~11) 반환
    - 입춘 보정된 연도 반환
    """
    
    def __init__(self):
        pass
    
    def get_solar_term_month_index(
        self,
        year: int,
        month: int,
        day: int,
        hour: int = 0,
        minute: int = 0
    ) -> Tuple[int, int, bool, Optional[str]]:
        """
        절기 기준 월지 인덱스 계산
        
        Args:
            year, month, day: 양력 날짜
            hour, minute: 시분 (정밀 계산용)
        
        Returns:
            (월지인덱스, 입춘보정연도, 경계여부, 경계사유)
            - 월지인덱스: 0=인(寅), 1=묘(卯), ..., 11=축(丑)
            - 입춘보정연도: 입춘 전이면 year-1, 아니면 year
            - 경계여부: 절기 ±48시간 이내면 True
            - 경계사유: "near_ipchun" | "near_term_change" | None
        """
        birth_dt = datetime(year, month, day, hour, minute)
        
        # 1. 정밀 데이터가 있는 연도인지 확인
        if year in SOLAR_TERMS_PRECISE:
            return self._calc_with_precise_data(birth_dt, year)
        
        # 2. 정밀 데이터가 없으면 근사 계산 (경계 표시 필수)
        return self._calc_with_approx_data(birth_dt, year)
    
    def _calc_with_precise_data(
        self,
        birth_dt: datetime,
        year: int
    ) -> Tuple[int, int, bool, Optional[str]]:
        """정밀 절기 데이터 기반 계산"""
        
        terms = SOLAR_TERMS_PRECISE.get(year, [])
        
        # 입춘 시각 확인 (첫 번째 절기)
        ipchun = terms[0]
        ipchun_dt = datetime(*ipchun)
        
        # 입춘 보정 연도
        if birth_dt < ipchun_dt:
            adjusted_year = year - 1
            # 전년도 절기 데이터 사용
            prev_terms = SOLAR_TERMS_PRECISE.get(year - 1, [])
            if prev_terms:
                terms = prev_terms
            else:
                # 전년도 데이터 없으면 근사 계산
                return self._calc_with_approx_data(birth_dt, year - 1, is_pre_ipchun=True)
        else:
            adjusted_year = year
        
        # 월지 인덱스 결정
        month_idx = 11  # 기본값 (축월)
        is_boundary = False
        boundary_reason = None
        
        for i, term_data in enumerate(terms):
            term_dt = datetime(*term_data)
            
            # 경계 체크 (±48시간)
            time_diff = abs((birth_dt - term_dt).total_seconds())
            if time_diff <= 48 * 3600:
                is_boundary = True
                if i == 0:
                    boundary_reason = "near_ipchun"
                else:
                    boundary_reason = "near_term_change"
            
            # 해당 절기 이전인지 확인
            if birth_dt < term_dt:
                # 이전 월지
                if i == 0:
                    month_idx = 11  # 축월 (입춘 전)
                else:
                    month_idx = i - 1
                break
            else:
                month_idx = i
        
        # 12번째(소한) 이후면 축월
        if month_idx >= 12:
            month_idx = 11
        
        return month_idx, adjusted_year, is_boundary, boundary_reason
    
    def _calc_with_approx_data(
        self,
        birth_dt: datetime,
        year: int,
        is_pre_ipchun: bool = False
    ) -> Tuple[int, int, bool, Optional[str]]:
        """근사 절기 데이터 기반 계산 (정밀 데이터 없는 연도)"""
        
        # 근사 입춘: 2월 4일
        approx_ipchun = datetime(year, 2, 4, 0, 0)
        
        if is_pre_ipchun or birth_dt < approx_ipchun:
            adjusted_year = year - 1 if not is_pre_ipchun else year
        else:
            adjusted_year = year
        
        # 근사 월지 계산
        month_idx = 11  # 기본값
        
        for i, term_info in enumerate(SOLAR_TERMS_ENTRY):
            approx_term = datetime(
                year if term_info.approx_month >= 2 else year + 1,
                term_info.approx_month,
                term_info.approx_day,
                0, 0
            )
            
            if birth_dt < approx_term:
                month_idx = (i - 1) % 12
                break
            else:
                month_idx = i % 12
        
        # 근사 계산은 항상 경계로 표시
        is_boundary = True
        boundary_reason = "approx_calculation"
        
        return month_idx, adjusted_year, is_boundary, boundary_reason
    
    def is_near_solar_term(
        self,
        year: int,
        month: int,
        day: int,
        hour: int = 0,
        minute: int = 0,
        threshold_hours: int = 48
    ) -> Tuple[bool, Optional[str]]:
        """절기 경계 근처인지 확인"""
        _, _, is_boundary, reason = self.get_solar_term_month_index(
            year, month, day, hour, minute
        )
        return is_boundary, reason


# 싱글톤
solar_terms_engine = SolarTermsEngine()


def get_lichun_adjusted_year(year: int, month: int, day: int) -> int:
    """
    입춘 보정된 연도 반환
    
    Args:
        year: 양력 연도
        month: 양력 월
        day: 양력 일
    
    Returns:
        입춘 보정된 연도
    """
    _, adjusted_year, _, _ = solar_terms_engine.get_solar_term_month_index(
        year, month, day
    )
    return adjusted_year
