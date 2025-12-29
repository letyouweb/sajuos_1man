"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SajuOS V1.0 하이브리드 엔진 최종 검증 테스트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import requests
import json
import sys
from typing import Dict, Any

BASE_URL = "http://127.0.0.1:8000"


def test_engine_endpoint():
    """✅ TEST 1: 디버그 엔드포인트 작동 검증"""
    print("\n" + "="*60)
    print("TEST 1: 디버그 엔드포인트 작동 검증")
    print("="*60)
    
    url = f"{BASE_URL}/api/v1/debug/engine"
    params = {
        "birth_year": 1988,
        "birth_month": 5,
        "birth_day": 15,
        "birth_hour": 10
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Pillars 검증
            pillars = data.get("pillars", {})
            year = pillars.get("year", {}).get("ganji", "")
            month = pillars.get("month", {}).get("ganji", "")
            day = pillars.get("day", {}).get("ganji", "")
            hour = pillars.get("hour", {}).get("ganji", "")
            
            print(f"  ✅ API 응답 성공")
            print(f"  사주: {year} {month} {day} {hour}")
            
            # Derived 검증
            derived = data.get("derived", {})
            print(f"  일간: {derived.get('day_master')} ({derived.get('day_master_element')})")
            print(f"  구조: {derived.get('structure')}")
            
            # Match Summary 검증
            match_summary = data.get("match_summary", {})
            print(f"  섹션 매칭:")
            for section, info in match_summary.items():
                print(f"    - {section}: {info.get('count')}장")
            
            return True
        else:
            print(f"  ❌ API 실패: {response.status_code}")
            return False
    
    except Exception as e:
        print(f"  ❌ 예외 발생: {e}")
        return False


def test_pillars_difference():
    """✅ TEST 2: 생년월일이 다르면 pillars 반드시 다름"""
    print("\n" + "="*60)
    print("TEST 2: 생년월일 차이 → Pillars 차이 검증")
    print("="*60)
    
    url = f"{BASE_URL}/api/v1/debug/engine"
    
    # 케이스 A: 1988-05-15
    params_a = {"birth_year": 1988, "birth_month": 5, "birth_day": 15, "birth_hour": 10}
    
    # 케이스 B: 1993-03-25
    params_b = {"birth_year": 1993, "birth_month": 3, "birth_day": 25, "birth_hour": 18}
    
    try:
        response_a = requests.get(url, params=params_a, timeout=10)
        response_b = requests.get(url, params=params_b, timeout=10)
        
        if response_a.status_code == 200 and response_b.status_code == 200:
            data_a = response_a.json()
            data_b = response_b.json()
            
            pillars_a = data_a.get("pillars", {})
            pillars_b = data_b.get("pillars", {})
            
            saju_a = f"{pillars_a['year']['ganji']} {pillars_a['month']['ganji']} {pillars_a['day']['ganji']}"
            saju_b = f"{pillars_b['year']['ganji']} {pillars_b['month']['ganji']} {pillars_b['day']['ganji']}"
            
            print(f"  케이스 A (1988-05-15): {saju_a}")
            print(f"  케이스 B (1993-03-25): {saju_b}")
            
            if saju_a != saju_b:
                print(f"  ✅ Pillars가 다름 - 테스트 통과!")
                return True
            else:
                print(f"  ❌ Pillars가 같음 - 테스트 실패!")
                return False
        else:
            print(f"  ❌ API 호출 실패")
            return False
    
    except Exception as e:
        print(f"  ❌ 예외 발생: {e}")
        return False


def test_match_results_difference():
    """✅ TEST 3: 다른 사주는 매칭 결과도 다름"""
    print("\n" + "="*60)
    print("TEST 3: 매칭 결과 차이 검증")
    print("="*60)
    
    url = f"{BASE_URL}/api/v1/debug/engine"
    
    params_a = {"birth_year": 1988, "birth_month": 5, "birth_day": 15, "birth_hour": 10}
    params_b = {"birth_year": 1993, "birth_month": 3, "birth_day": 25, "birth_hour": 18}
    
    try:
        response_a = requests.get(url, params=params_a, timeout=10)
        response_b = requests.get(url, params=params_b, timeout=10)
        
        if response_a.status_code == 200 and response_b.status_code == 200:
            data_a = response_a.json()
            data_b = response_b.json()
            
            raw_a = data_a.get("raw_json", {})
            raw_b = data_b.get("raw_json", {})
            
            ids_a = set(raw_a.get("matched_rule_ids", []))
            ids_b = set(raw_b.get("matched_rule_ids", []))
            
            common = ids_a & ids_b
            diff = len(ids_a) + len(ids_b) - 2 * len(common)
            total = len(ids_a) + len(ids_b)
            
            diff_ratio = (diff / total * 100) if total > 0 else 0
            
            print(f"  케이스 A 매칭: {len(ids_a)}장")
            print(f"  케이스 B 매칭: {len(ids_b)}장")
            print(f"  공통: {len(common)}장")
            print(f"  차이: {diff}장 ({diff_ratio:.1f}%)")
            
            # 섹션별 차이도 확인
            match_a = data_a.get("match_summary", {})
            match_b = data_b.get("match_summary", {})
            
            print(f"\n  섹션별 비교:")
            for section in match_a.keys():
                count_a = match_a[section].get("count", 0)
                count_b = match_b[section].get("count", 0)
                print(f"    - {section}: A={count_a}장, B={count_b}장")
            
            if diff_ratio > 0:
                print(f"\n  ✅ 매칭 결과가 다름 - 테스트 통과!")
                return True
            else:
                print(f"\n  ❌ 매칭 결과가 같음 - 테스트 실패!")
                return False
        else:
            print(f"  ❌ API 호출 실패")
            return False
    
    except Exception as e:
        print(f"  ❌ 예외 발생: {e}")
        return False


def test_match_non_zero():
    """✅ TEST 4: 섹션별 매칭 카드 수가 0이 아님"""
    print("\n" + "="*60)
    print("TEST 4: 섹션별 매칭 카드 수 검증")
    print("="*60)
    
    url = f"{BASE_URL}/api/v1/debug/engine"
    params = {"birth_year": 1988, "birth_month": 5, "birth_day": 15, "birth_hour": 10}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            match_summary = data.get("match_summary", {})
            
            all_non_zero = True
            for section, info in match_summary.items():
                count = info.get("count", 0)
                print(f"  {section}: {count}장")
                if count == 0:
                    all_non_zero = False
                    print(f"    ❌ 0장!")
            
            if all_non_zero:
                print(f"\n  ✅ 모든 섹션에 매칭 카드 존재 - 테스트 통과!")
                return True
            else:
                print(f"\n  ❌ 일부 섹션이 0장 - 테스트 실패!")
                return False
        else:
            print(f"  ❌ API 호출 실패")
            return False
    
    except Exception as e:
        print(f"  ❌ 예외 발생: {e}")
        return False


def test_raw_json_trace():
    """✅ TEST 5: raw_json에 score trace 포함 확인"""
    print("\n" + "="*60)
    print("TEST 5: Raw JSON Score Trace 검증")
    print("="*60)
    
    url = f"{BASE_URL}/api/v1/debug/engine"
    params = {"birth_year": 1988, "birth_month": 5, "birth_day": 15, "birth_hour": 10}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            raw_json = data.get("raw_json", {})
            
            has_ids = bool(raw_json.get("matched_rule_ids"))
            has_scores = bool(raw_json.get("match_scores"))
            has_triggers = bool(raw_json.get("fired_triggers"))
            
            print(f"  matched_rule_ids: {len(raw_json.get('matched_rule_ids', []))}개")
            print(f"  match_scores: {len(raw_json.get('match_scores', {}))}개")
            print(f"  fired_triggers: {len(raw_json.get('fired_triggers', {}))}개")
            
            if has_ids and has_scores and has_triggers:
                print(f"\n  ✅ Score Trace 포함됨 - 테스트 통과!")
                return True
            else:
                print(f"\n  ❌ Score Trace 누락 - 테스트 실패!")
                return False
        else:
            print(f"  ❌ API 호출 실패")
            return False
    
    except Exception as e:
        print(f"  ❌ 예외 발생: {e}")
        return False


def main():
    """메인 테스트"""
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("SajuOS V1.0 하이브리드 엔진 최종 검증")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    results = []
    
    # 테스트 실행
    results.append(("디버그 엔드포인트", test_engine_endpoint()))
    results.append(("Pillars 차이", test_pillars_difference()))
    results.append(("매칭 결과 차이", test_match_results_difference()))
    results.append(("매칭 카드 수 >0", test_match_non_zero()))
    results.append(("Score Trace", test_raw_json_trace()))
    
    # 결과 요약
    print("\n" + "="*60)
    print("최종 결과")
    print("="*60)
    
    for name, result in results:
        status = "✅ 통과" if result else "❌ 실패"
        print(f"  {name}: {status}")
    
    all_pass = all(r[1] for r in results)
    
    if all_pass:
        print("\n🎉 모든 테스트 통과!")
        return 0
    else:
        print("\n❌ 일부 테스트 실패!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
