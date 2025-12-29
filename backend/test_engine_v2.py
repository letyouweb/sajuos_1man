"""
engine_v2.py 독립 실행 테스트 (의존성 없음)
- 수정: ephem.Ecliptic(sun).lon 사용 (진짜 황경)
"""
import math
from datetime import datetime, timedelta

try:
    import ephem
    EPHEM_AVAILABLE = True
except ImportError:
    EPHEM_AVAILABLE = False
    print("ERROR: ephem not installed")
    exit(1)

GAN = list("갑을병정무기경신임계")
JI = list("자축인묘진사오미신유술해")

class ScientificSajuEngine:
    def __init__(self):
        self.ANCHOR_DATE = datetime(2000, 1, 1)
        self.ANCHOR_IDX = 54
    
    def _get_solar_longitude(self, year, month, day, hour, minute=0):
        """
        태양의 황경(Ecliptic Longitude) 계산
        
        핵심: ephem.Ecliptic(sun).lon 사용
        - sun.hlon은 heliocentric longitude (태양 중심, 의미 없음)
        - Ecliptic().lon은 geocentric ecliptic longitude (지구에서 본 황경)
        """
        dt_kst = datetime(year, month, day, hour, minute)
        dt_utc = dt_kst - timedelta(hours=9)
        
        sun = ephem.Sun()
        observer = ephem.Observer()
        observer.date = dt_utc
        sun.compute(observer)
        
        # 진짜 황경: 지구에서 본 태양의 황도 경도
        ecliptic = ephem.Ecliptic(sun)
        lon_deg = math.degrees(ecliptic.lon)
        
        return lon_deg
    
    def _get_solar_term_index(self, solar_longitude):
        """
        황경 → 월지 인덱스 매핑
        
        24절기 기준 (각 절기 15도 간격):
        - 춘분(0°) → 묘월(3) 시작
        - 청명(15°) → 진월(4) 시작
        - 입하(45°) → 사월(5) 시작
        - 망종(75°) → 오월(6) 시작
        - ...
        - 동지(270°) → 자월(0) 시작
        - 소한(285°) → 축월(1) 시작  
        - 입춘(315°) → 인월(2) 시작
        - 경칩(345°) → 묘월(3) 시작
        
        공식: ((황경 + 45) // 30) % 12 + 2 조정
        또는 간단히: (황경 + 15) // 30 → 절기 index → 월지 매핑
        """
        deg = solar_longitude
        
        # 각 절기의 시작 황경과 월지 매핑
        # 입춘(315) = 인월(2) 시작
        # 정확한 매핑: 절기 시작 황경을 기준으로
        
        # 방법: 황경 + 45도 → 0~360 범위로 정규화 → 30으로 나눔
        # 이렇게 하면 0~30이 인월(2), 30~60이 묘월(3)...
        
        normalized = (deg + 45) % 360
        term_idx = int(normalized / 30)  # 0~11
        
        # term_idx를 월지 인덱스로 변환
        # term_idx 0 = 입춘~경칩 = 인월(2)
        # term_idx 1 = 경칩~청명 = 묘월(3)
        # ...
        month_ji_idx = (term_idx + 2) % 12
        
        return month_ji_idx
    
    def calculate(self, year, month, day, hour=None, minute=0, use_solar_time=True):
        calc_hour = hour if hour is not None else 12
        solar_lon = self._get_solar_longitude(year, month, day, calc_hour, minute)
        solar_idx = self._get_solar_term_index(solar_lon)
        
        # 년주
        cal_year = year
        if month <= 2:
            if solar_idx <= 1:  # 자(0) 또는 축(1)
                cal_year = year - 1
        
        year_gan_idx = (cal_year - 4) % 10
        year_ji_idx = (cal_year - 4) % 12
        
        # 월주
        month_ji_idx = solar_idx
        start_gan_idx = (year_gan_idx % 5) * 2 + 2
        gap = month_ji_idx - 2
        if gap < 0:
            gap += 12
        month_gan_idx = (start_gan_idx + gap) % 10
        
        # 일주
        target_dt = datetime(year, month, day)
        days_diff = (target_dt - self.ANCHOR_DATE).days
        curr_day_idx = (self.ANCHOR_IDX + days_diff) % 60
        day_gan_idx = curr_day_idx % 10
        day_ji_idx = curr_day_idx % 12
        
        # 시주
        hour_pillar = None
        if hour is not None:
            adjusted_minute = hour * 60 + minute
            if use_solar_time:
                adjusted_minute -= 30
                if adjusted_minute < 0:
                    adjusted_minute += 1440
            
            eff_hour = adjusted_minute // 60
            hour_ji_idx = ((eff_hour + 1) // 2) % 12
            start_time_gan = (day_gan_idx % 5) * 2
            hour_gan_idx = (start_time_gan + hour_ji_idx) % 10
            hour_pillar = GAN[hour_gan_idx] + JI[hour_ji_idx]
        
        return {
            "year": GAN[year_gan_idx] + JI[year_ji_idx],
            "month": GAN[month_gan_idx] + JI[month_ji_idx],
            "day": GAN[day_gan_idx] + JI[day_ji_idx],
            "time": hour_pillar,
            "meta": {
                "solar_longitude": round(solar_lon, 2),
                "solar_idx": solar_idx,
                "solar_time": use_solar_time
            }
        }


def run_tests():
    engine = ScientificSajuEngine()
    
    print("=" * 60)
    print("Regression Test: 1978-05-16 11:00 (KST)")
    print("=" * 60)
    
    # Case A: Solar Time ON
    res_on = engine.calculate(1978, 5, 16, 11, 0, use_solar_time=True)
    
    print(f"\n[Case A] Solar Time ON:")
    print(f"  year: {res_on['year']} (expected: 무오)")
    print(f"  month: {res_on['month']} (expected: 정사)")
    print(f"  day: {res_on['day']} (expected: 무인)")
    print(f"  time: {res_on['time']} (expected: 정사)")
    print(f"  solar_lon: {res_on['meta']['solar_longitude']} deg")
    print(f"  solar_idx (month_ji): {res_on['meta']['solar_idx']}")
    
    passed = True
    
    if res_on['year'] != '무오':
        print(f"  FAIL: year (got {res_on['year']})")
        passed = False
    if res_on['month'] != '정사':
        print(f"  FAIL: month (got {res_on['month']})")
        passed = False
    if res_on['day'] != '무인':
        print(f"  FAIL: day (got {res_on['day']})")
        passed = False
    if res_on['time'] != '정사':
        print(f"  FAIL: time (got {res_on['time']})")
        passed = False
    
    if passed:
        print("  PASS")
    
    # Case B: Solar Time OFF
    res_off = engine.calculate(1978, 5, 16, 11, 0, use_solar_time=False)
    
    print(f"\n[Case B] Solar Time OFF:")
    print(f"  time: {res_off['time']} (expected: 무오)")
    
    if res_off['time'] == '무오':
        print("  PASS")
    else:
        print(f"  FAIL (got {res_off['time']})")
        passed = False
    
    # Case C: Anchor
    res_anchor = engine.calculate(2000, 1, 1, 12, 0)
    
    print(f"\n[Case C] Anchor (2000-01-01):")
    print(f"  day: {res_anchor['day']} (expected: 무오)")
    
    if res_anchor['day'] == '무오':
        print("  PASS")
    else:
        print(f"  FAIL (got {res_anchor['day']})")
        passed = False
    
    # Case D: Ipchun boundary
    res_before = engine.calculate(2025, 2, 3, 12, 0)
    res_after = engine.calculate(2025, 2, 5, 12, 0)
    
    print(f"\n[Case D] Ipchun Boundary:")
    print(f"  2025-02-03 year: {res_before['year']} (solar_idx={res_before['meta']['solar_idx']}, lon={res_before['meta']['solar_longitude']})")
    print(f"  2025-02-05 year: {res_after['year']} (solar_idx={res_after['meta']['solar_idx']}, lon={res_after['meta']['solar_longitude']})")
    print("  OK")
    
    # Case E: Today
    res_today = engine.calculate(2025, 12, 18, 21, 0)
    
    print(f"\n[Case E] Today (2025-12-18 21:00):")
    print(f"  year: {res_today['year']}")
    print(f"  month: {res_today['month']}")
    print(f"  day: {res_today['day']}")
    print(f"  time: {res_today['time']}")
    print(f"  solar_lon: {res_today['meta']['solar_longitude']} deg")
    
    print("\n" + "=" * 60)
    if passed:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print("=" * 60)
    
    return passed


if __name__ == "__main__":
    run_tests()
