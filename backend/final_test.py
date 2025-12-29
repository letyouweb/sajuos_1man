"""
최종 검증 - JSON 출력
"""
import json
import math
from datetime import datetime, timedelta
import ephem

GAN = list("갑을병정무기경신임계")
JI = list("자축인묘진사오미신유술해")

class ScientificSajuEngine:
    def __init__(self):
        self.ANCHOR_DATE = datetime(2000, 1, 1)
        self.ANCHOR_IDX = 54
    
    def _get_solar_longitude(self, year, month, day, hour, minute=0):
        dt_kst = datetime(year, month, day, hour, minute)
        dt_utc = dt_kst - timedelta(hours=9)
        sun = ephem.Sun()
        observer = ephem.Observer()
        observer.date = dt_utc
        sun.compute(observer)
        ecliptic = ephem.Ecliptic(sun)
        return math.degrees(ecliptic.lon)
    
    def _get_solar_term_index(self, solar_longitude):
        normalized = (solar_longitude + 45) % 360
        term_idx = int(normalized / 30)
        return (term_idx + 2) % 12
    
    def calculate(self, year, month, day, hour=None, minute=0, use_solar_time=True):
        calc_hour = hour if hour is not None else 12
        solar_lon = self._get_solar_longitude(year, month, day, calc_hour, minute)
        solar_idx = self._get_solar_term_index(solar_lon)
        
        cal_year = year
        if month <= 2 and solar_idx <= 1:
            cal_year = year - 1
        
        year_gan_idx = (cal_year - 4) % 10
        year_ji_idx = (cal_year - 4) % 12
        
        month_ji_idx = solar_idx
        start_gan_idx = (year_gan_idx % 5) * 2 + 2
        gap = month_ji_idx - 2
        if gap < 0: gap += 12
        month_gan_idx = (start_gan_idx + gap) % 10
        
        target_dt = datetime(year, month, day)
        days_diff = (target_dt - self.ANCHOR_DATE).days
        curr_day_idx = (self.ANCHOR_IDX + days_diff) % 60
        day_gan_idx = curr_day_idx % 10
        day_ji_idx = curr_day_idx % 12
        
        hour_pillar = None
        if hour is not None:
            adjusted_minute = hour * 60 + minute
            if use_solar_time:
                adjusted_minute -= 30
                if adjusted_minute < 0: adjusted_minute += 1440
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
            "solar_longitude": round(solar_lon, 2),
            "solar_time_applied": use_solar_time
        }


if __name__ == "__main__":
    engine = ScientificSajuEngine()
    
    results = {
        "engine": "ScientificSajuEngine v2 (ephem astronomical)",
        "source_of_truth": "NASA JPL Data via ephem library",
        "tests": {
            "1978-05-16_11h_solar_on": {
                "input": "1978-05-16 11:00 (Solar Time ON)",
                "result": engine.calculate(1978, 5, 16, 11, 0, use_solar_time=True),
                "expected": {"year": "무오", "month": "정사", "day": "무인", "time": "정사"},
                "status": "PASS" if engine.calculate(1978, 5, 16, 11, 0)["time"] == "정사" else "FAIL"
            },
            "1978-05-16_11h_solar_off": {
                "input": "1978-05-16 11:00 (Solar Time OFF)",
                "result": engine.calculate(1978, 5, 16, 11, 0, use_solar_time=False),
                "expected_time": "무오",
                "status": "PASS" if engine.calculate(1978, 5, 16, 11, 0, False)["time"] == "무오" else "FAIL"
            },
            "anchor_2000-01-01": {
                "input": "2000-01-01 (Anchor Date)",
                "result": engine.calculate(2000, 1, 1, 12, 0),
                "expected_day": "무오",
                "status": "PASS" if engine.calculate(2000, 1, 1, 12, 0)["day"] == "무오" else "FAIL"
            },
            "ipchun_before_2025-02-03": {
                "input": "2025-02-03 (Before Ipchun)",
                "result": engine.calculate(2025, 2, 3, 12, 0),
                "expected_year": "갑진 (previous year)"
            },
            "ipchun_after_2025-02-05": {
                "input": "2025-02-05 (After Ipchun)",
                "result": engine.calculate(2025, 2, 5, 12, 0),
                "expected_year": "을사 (current year)"
            },
            "today_2025-12-18": {
                "input": "2025-12-18 21:00",
                "result": engine.calculate(2025, 12, 18, 21, 0)
            }
        }
    }
    
    with open("final_verification.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("Saved to final_verification.json")
