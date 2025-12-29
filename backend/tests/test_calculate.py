"""
사주 계산 테스트 - 상업용 등급 엔진 검증
"""
import pytest
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.manse import SajuManse, saju_manse
from app.services.saju_engine import saju_engine


class TestManse:
    """manse.py 직접 테스트"""
    
    def test_1978_05_16_11h(self):
        """
        핵심 검증 케이스: 1978년 5월 16일 11시
        기대값: 무오-정사-무인-무오
        """
        result = saju_manse.get_saju(1978, 5, 16, 11, 0)
        
        assert result["year_pillar"]["ganji"] == "무오", \
            f"년주: Expected 무오, got {result['year_pillar']['ganji']}"
        assert result["month_pillar"]["ganji"] == "정사", \
            f"월주: Expected 정사, got {result['month_pillar']['ganji']}"
        assert result["day_pillar"]["ganji"] == "무인", \
            f"일주: Expected 무인, got {result['day_pillar']['ganji']}"
        # 시주: 11시에서 -30분 보정 → 10시30분 → 사시
        # 실제로는 오시일 수도 있음 (10:30은 사시 범위 09:00~10:59)
        print(f"시주: {result['hour_pillar']['ganji']}")
    
    def test_ipchun_boundary_before(self):
        """입춘 전: 2025년 2월 3일 → 갑진년"""
        result = saju_manse.get_saju(2025, 2, 3, 12, 0)
        assert result["year_pillar"]["ganji"] == "갑진", \
            f"Expected 갑진, got {result['year_pillar']['ganji']}"
        assert result["quality"]["solar_term_boundary"] == True
    
    def test_ipchun_boundary_after(self):
        """입춘 후: 2025년 2월 5일 → 을사년"""
        result = saju_manse.get_saju(2025, 2, 5, 12, 0)
        assert result["year_pillar"]["ganji"] == "을사", \
            f"Expected 을사, got {result['year_pillar']['ganji']}"
    
    def test_january_special(self):
        """1월 특수 케이스: 소한(1/6) 전후"""
        # 1월 3일: 자월 (전년도 12월)
        result1 = saju_manse.get_saju(2025, 1, 3, 12, 0)
        assert result1["month_pillar"]["ji"] == "자", \
            f"Expected 자, got {result1['month_pillar']['ji']}"
        
        # 1월 10일: 축월
        result2 = saju_manse.get_saju(2025, 1, 10, 12, 0)
        assert result2["month_pillar"]["ji"] == "축", \
            f"Expected 축, got {result2['month_pillar']['ji']}"
    
    def test_day_pillar_anchor(self):
        """일주 Anchor 검증: 2000년 1월 1일 = 무오"""
        result = saju_manse.get_saju(2000, 1, 1, 12, 0)
        assert result["day_pillar"]["ganji"] == "무오", \
            f"Expected 무오, got {result['day_pillar']['ganji']}"
    
    def test_hour_ji_mapping(self):
        """시간→지지 매핑 검증"""
        # 자시: 23:00~00:59
        # 30분 보정 적용하면 23:30~01:29 → 실효 시간 23:00~01:00
        
        # 테스트: 11시 입력 → 10:30 → 사시(5)
        result = saju_manse.get_saju(1978, 5, 16, 11, 0)
        assert result["hour_pillar"]["ji_index"] == 5, \
            f"Expected 사시(5), got {result['hour_pillar']['ji_index']}"
    
    def test_no_hour(self):
        """시간 미입력"""
        result = saju_manse.get_saju(1978, 5, 16)
        assert result["hour_pillar"] is None
        assert result["quality"]["has_birth_time"] == False


class TestSajuEngine:
    """saju_engine.py (API 래퍼) 테스트"""
    
    def test_calculate_1978_05_16(self):
        """API 래퍼 테스트"""
        result = saju_engine.calculate(
            year=1978, month=5, day=16, hour=11, minute=0
        )
        
        assert result.saju.year_pillar.ganji == "무오"
        assert result.saju.month_pillar.ganji == "정사"
        assert result.saju.day_pillar.ganji == "무인"
        assert result.day_master == "무"
        assert result.day_master_element == "토"
    
    def test_quality_info(self):
        """품질 정보 확인"""
        result = saju_engine.calculate(
            year=2025, month=2, day=3, hour=12
        )
        
        assert result.quality.solar_term_boundary == True
        assert result.quality.boundary_reason == "near_ipchun"
    
    def test_daeun_direction(self):
        """대운 방향 계산"""
        # 남성 + 양년(무오) → 순행
        result = saju_engine.calculate(
            year=1978, month=5, day=16, hour=11, gender="male"
        )
        assert result.daeun.direction == "forward"
        
        # 여성 + 양년(무오) → 역행
        result2 = saju_engine.calculate(
            year=1978, month=5, day=16, hour=11, gender="female"
        )
        assert result2.daeun.direction == "backward"


class TestRegressionCases:
    """회귀 테스트 케이스"""
    
    @pytest.mark.parametrize("case", [
        {
            "input": {"year": 1978, "month": 5, "day": 16, "hour": 11},
            "year": "무오", "month": "정사", "day": "무인",
            "desc": "검증 기준 케이스"
        },
        {
            "input": {"year": 2000, "month": 1, "day": 1},
            "day": "무오",
            "desc": "Anchor 날짜"
        },
        {
            "input": {"year": 2025, "month": 1, "day": 1},
            "year": "갑진",
            "desc": "입춘 전 (전년도)"
        },
        {
            "input": {"year": 1990, "month": 6, "day": 15},
            "year": "경오",
            "desc": "1990년"
        },
    ])
    def test_regression(self, case):
        result = saju_manse.get_saju(**case["input"])
        
        if "year" in case:
            assert result["year_pillar"]["ganji"] == case["year"], \
                f"{case['desc']}: year Expected {case['year']}, got {result['year_pillar']['ganji']}"
        
        if "month" in case:
            assert result["month_pillar"]["ganji"] == case["month"], \
                f"{case['desc']}: month Expected {case['month']}, got {result['month_pillar']['ganji']}"
        
        if "day" in case:
            assert result["day_pillar"]["ganji"] == case["day"], \
                f"{case['desc']}: day Expected {case['day']}, got {result['day_pillar']['ganji']}"


if __name__ == "__main__":
    # 직접 실행 테스트
    print("=" * 60)
    print("1978년 5월 16일 11시 테스트")
    print("=" * 60)
    
    result = saju_manse.get_saju(1978, 5, 16, 11, 0)
    print(f"년주: {result['year_pillar']['ganji']} (기대: 무오)")
    print(f"월주: {result['month_pillar']['ganji']} (기대: 정사)")
    print(f"일주: {result['day_pillar']['ganji']} (기대: 무인)")
    print(f"시주: {result['hour_pillar']['ganji']}")
    print(f"일간: {result['day_master']}")
    
    print("\n" + "=" * 60)
    print("pytest 실행:")
    pytest.main([__file__, "-v"])
