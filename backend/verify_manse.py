"""
manse.py 검증 스크립트 (JSON 출력)
"""
import json
from datetime import datetime

# 천간/지지 상수
GAN = list("갑을병정무기경신임계")
JI = list("자축인묘진사오미신유술해")

# 절기 평균일
TERM_DATES = {
    2: 4, 3: 6, 4: 5, 5: 6, 6: 6, 7: 7,
    8: 8, 9: 8, 10: 8, 11: 7, 12: 7, 1: 6
}

class SajuManse:
    def __init__(self):
        self.ref_date = datetime(2000, 1, 1)
        self.ref_day_idx = 54  # 무오 = 54
    
    def _get_solar_term_month(self, year, month, day):
        cutoff_day = TERM_DATES.get(month, 5)
        if month == 1:
            return 1 if day >= cutoff_day else 12
        if day >= cutoff_day:
            return month
        else:
            return month - 1 if month > 1 else 12
    
    def get_saju(self, year, month, day, hour=None, minute=0):
        # 1. 년주
        saju_year = year
        if month < 2 or (month == 2 and day < 4):
            saju_year = year - 1
        
        year_gan_idx = (saju_year - 4) % 10
        year_ji_idx = (saju_year - 4) % 12
        year_pillar = GAN[year_gan_idx] + JI[year_ji_idx]
        
        # 2. 월주
        saju_month_num = self._get_solar_term_month(year, month, day)
        
        if saju_month_num == 12:
            month_ji_idx = 0
        elif saju_month_num == 1:
            month_ji_idx = 1
        else:
            month_ji_idx = saju_month_num
        
        start_gan_idx = (year_gan_idx % 5) * 2 + 2
        gap = month_ji_idx - 2
        if gap < 0:
            gap += 12
        
        month_gan_idx = (start_gan_idx + gap) % 10
        month_pillar = GAN[month_gan_idx] + JI[month_ji_idx]
        
        # 3. 일주 (Anchor: 2000.1.1 = 무오)
        diff_days = (datetime(year, month, day) - self.ref_date).days
        curr_day_idx = (self.ref_day_idx + diff_days) % 60
        
        day_gan_idx = curr_day_idx % 10
        day_ji_idx = curr_day_idx % 12
        day_pillar = GAN[day_gan_idx] + JI[day_ji_idx]
        
        # 4. 시주
        hour_pillar = None
        if hour is not None:
            # 동경 135도 보정 (-30분)
            total_minutes = hour * 60 + minute - 30
            if total_minutes < 0:
                total_minutes += 1440
            
            eff_hour = total_minutes // 60
            hour_ji_idx = ((eff_hour + 1) // 2) % 12
            
            start_time_gan = (day_gan_idx % 5) * 2
            hour_gan_idx = (start_time_gan + hour_ji_idx) % 10
            
            hour_pillar = GAN[hour_gan_idx] + JI[hour_ji_idx]
        
        return {
            "year": year_pillar,
            "month": month_pillar,
            "day": day_pillar,
            "time": hour_pillar
        }


if __name__ == "__main__":
    engine = SajuManse()
    
    results = {
        "test_1978_05_16_11h": {
            "input": "1978-05-16 11:00",
            "result": engine.get_saju(1978, 5, 16, 11, 0),
            "expected": {"year": "무오", "month": "정사", "day": "무인"}
        },
        "test_anchor_2000_01_01": {
            "input": "2000-01-01",
            "result": engine.get_saju(2000, 1, 1, 12, 0),
            "expected": {"day": "무오"}
        },
        "test_today_2025_12_18": {
            "input": "2025-12-18 21:00",
            "result": engine.get_saju(2025, 12, 18, 21, 0)
        }
    }
    
    # JSON으로 파일 저장
    with open("verify_result.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("Results saved to verify_result.json")
