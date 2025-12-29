"""
사주 계산 테스트 스크립트
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.saju_engine import saju_engine

async def test_calculate():
    """사주 계산 테스트"""
    
    print("=" * 80)
    print("[TEST] 사주 계산 테스트")
    print("=" * 80)
    print()
    
    # 테스트 케이스 1: 1978년 5월 16일 11시
    print("테스트 1: 1978년 5월 16일 11시")
    print("-" * 60)
    
    result1 = await saju_engine.calculate_async(
        year=1978,
        month=5,
        day=16,
        hour=11,
        minute=0,
        gender="male",
        use_solar_time=True
    )
    
    print(f"년주: {result1.saju.year_pillar.ganji} ({result1.saju.year_pillar.gan}/{result1.saju.year_pillar.ji})")
    print(f"월주: {result1.saju.month_pillar.ganji} ({result1.saju.month_pillar.gan}/{result1.saju.month_pillar.ji})")
    print(f"일주: {result1.saju.day_pillar.ganji} ({result1.saju.day_pillar.gan}/{result1.saju.day_pillar.ji})")
    print(f"시주: {result1.saju.hour_pillar.ganji if result1.saju.hour_pillar else 'N/A'} ({result1.saju.hour_pillar.gan if result1.saju.hour_pillar else '-'}/{result1.saju.hour_pillar.ji if result1.saju.hour_pillar else '-'})")
    print(f"일간: {result1.day_master} ({result1.day_master_element})")
    print(f"계산 방법: {result1.quality.calculation_method}")
    print()
    
    # 테스트 케이스 2: 1985년 11월 23일 14시
    print("테스트 2: 1985년 11월 23일 14시")
    print("-" * 60)
    
    result2 = await saju_engine.calculate_async(
        year=1985,
        month=11,
        day=23,
        hour=14,
        minute=0,
        gender="female",
        use_solar_time=True
    )
    
    print(f"년주: {result2.saju.year_pillar.ganji} ({result2.saju.year_pillar.gan}/{result2.saju.year_pillar.ji})")
    print(f"월주: {result2.saju.month_pillar.ganji} ({result2.saju.month_pillar.gan}/{result2.saju.month_pillar.ji})")
    print(f"일주: {result2.saju.day_pillar.ganji} ({result2.saju.day_pillar.gan}/{result2.saju.day_pillar.ji})")
    print(f"시주: {result2.saju.hour_pillar.ganji if result2.saju.hour_pillar else 'N/A'} ({result2.saju.hour_pillar.gan if result2.saju.hour_pillar else '-'}/{result2.saju.hour_pillar.ji if result2.saju.hour_pillar else '-'})")
    print(f"일간: {result2.day_master} ({result2.day_master_element})")
    print(f"계산 방법: {result2.quality.calculation_method}")
    print()
    
    # 검증
    print("=" * 80)
    print("[OK] 검증 결과")
    print("=" * 80)
    
    if result1.saju.year_pillar.ganji and result1.saju.month_pillar.ganji and result1.saju.day_pillar.ganji:
        print("[OK] 테스트 1: 년/월/일주 모두 정상")
    else:
        print("[FAIL] 테스트 1: 사주 데이터 누락")
    
    if result2.saju.year_pillar.ganji and result2.saju.month_pillar.ganji and result2.saju.day_pillar.ganji:
        print("[OK] 테스트 2: 년/월/일주 모두 정상")
    else:
        print("[FAIL] 테스트 2: 사주 데이터 누락")
    
    # 서로 다른지 확인
    if result1.saju.year_pillar.ganji != result2.saju.year_pillar.ganji:
        print("[OK] 년주가 서로 다름")
    else:
        print("[FAIL] 년주가 동일함 (문제 발생)")
    
    if result1.saju.day_pillar.ganji != result2.saju.day_pillar.ganji:
        print("[OK] 일주가 서로 다름")
    else:
        print("[FAIL] 일주가 동일함 (문제 발생)")

if __name__ == "__main__":
    asyncio.run(test_calculate())
