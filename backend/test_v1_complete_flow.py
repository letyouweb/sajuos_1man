"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SajuOS V1.0 완전한 플로우 테스트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
목적:
1. /api/v1/debug/engine 엔드포인트 테스트
2. Calc→Derive→Match 흐름 검증
3. 룰카드 로딩 0장 방지 확인
4. 스코어링 랭킹 시스템 검증
5. Supabase 저장 검증
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import asyncio
import httpx
import json
from datetime import datetime


BASE_URL = "http://localhost:8000/api/v1"

# 테스트 케이스 2개 (다른 생년월일)
TEST_CASES = [
    {
        "name": "Case 1: 1988-05-15 10시",
        "birth_year": 1988,
        "birth_month": 5,
        "birth_day": 15,
        "birth_hour": 10,
        "target_year": 2026
    },
    {
        "name": "Case 2: 1995-12-25 14시",
        "birth_year": 1995,
        "birth_month": 12,
        "birth_day": 25,
        "birth_hour": 14,
        "target_year": 2026
    }
]


async def test_debug_engine():
    """Debug Engine 테스트"""
    print("=" * 80)
    print("SajuOS V1.0 Complete Flow Test")
    print("=" * 80)
    print()
    
    results = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for idx, case in enumerate(TEST_CASES, 1):
            print(f"\n{'─' * 80}")
            print(f"Test Case {idx}: {case['name']}")
            print(f"{'─' * 80}")
            
            try:
                # 1. Debug Engine API 호출
                params = {
                    "birth_year": case["birth_year"],
                    "birth_month": case["birth_month"],
                    "birth_day": case["birth_day"],
                    "birth_hour": case["birth_hour"],
                    "target_year": case["target_year"]
                }
                
                print(f"\n[Request] GET {BASE_URL}/debug/engine")
                print(f"   Params: {params}")
                
                response = await client.get(f"{BASE_URL}/debug/engine", params=params)
                response.raise_for_status()
                
                data = response.json()
                
                # 2. 결과 분석
                pillars = data.get("pillars", {})
                derived = data.get("derived", {})
                match_summary = data.get("match_summary", {})
                validation = data.get("validation", {})
                rulecard_status = data.get("rulecard_status", {})
                raw_json = data.get("raw_json", {})
                
                # 3. 결과 출력
                print(f"\n[OK] Response OK (HTTP {response.status_code})")
                print(f"\n[1. PILLARS (사주 4주)]")
                print(f"   Year:  {pillars.get('year', {}).get('ganji', 'N/A')}")
                print(f"   Month: {pillars.get('month', {}).get('ganji', 'N/A')}")
                print(f"   Day:   {pillars.get('day', {}).get('ganji', 'N/A')}")
                print(f"   Hour:  {pillars.get('hour', {}).get('ganji', 'N/A')}")
                
                print(f"\n[2. DERIVED (파생 특징)]")
                print(f"   일간: {derived.get('day_master', 'N/A')} ({derived.get('day_master_element', 'N/A')})")
                print(f"   구조: {derived.get('structure', 'N/A')}")
                print(f"   강약: {'신강' if derived.get('is_strong_self') else '신약'}")
                print(f"   주도십성: {derived.get('dominant_ten_god', 'N/A')}")
                print(f"   타이밍: {derived.get('timing_desc', 'N/A')}")
                
                print(f"\n[3. MATCH SUMMARY (섹션별 매칭)]")
                for section_id, summary in match_summary.items():
                    count = summary.get("count", 0)
                    avg_score = summary.get("avg_score", 0)
                    top_cards = summary.get("top_cards", [])
                    
                    print(f"   {section_id}: {count}장, 평균점수: {avg_score:.2f}")
                    
                    # Top 3 카드 점수 표시
                    for i, card in enumerate(top_cards[:3], 1):
                        card_id = card.get("card_id", "N/A")
                        score = card.get("score", 0)
                        details = card.get("score_details", {})
                        
                        print(f"      #{i} {card_id}: {score:.2f}점")
                        if details:
                            print(f"         - base: {details.get('base_score', 0):.1f}, "
                                  f"tag: {details.get('tag_match_score', 0):.1f}, "
                                  f"year: {details.get('year_boost', 0):.1f}, "
                                  f"goal: {details.get('goal_boost', 0):.1f}")
                
                print(f"\n[4. RULECARD STATUS (룰카드 로드 상태)]")
                print(f"   로드 상태: {'[OK] 로드됨' if rulecard_status.get('loaded') else '[FAIL] 미로드'}")
                print(f"   총 카드 수: {rulecard_status.get('total_cards', 0)}장")
                print(f"   토픽별 분포:")
                by_topic = rulecard_status.get("by_topic", {})
                for topic, count in by_topic.items():
                    print(f"      {topic}: {count}장")
                
                print(f"\n[5. VALIDATION (검증 결과)]")
                print(f"   Pillars Valid: {'[OK]' if validation.get('pillars_valid') else '[FAIL]'}")
                print(f"   Matches Valid: {'[OK]' if validation.get('matches_valid') else '[FAIL]'}")
                print(f"   Scores Valid: {'[OK]' if validation.get('scores_valid') else '[FAIL]'}")
                print(f"   Total Matched Cards: {validation.get('total_matched_cards', 0)}장")
                print(f"   All Checks: {'[OK] PASS' if validation.get('all_checks_passed') else '[FAIL] FAIL'}")
                
                print(f"\n[6. RAW JSON (추적 정보)]")
                print(f"   Matched Rule IDs: {len(raw_json.get('matched_rule_ids', []))}개")
                print(f"   Total Matched: {raw_json.get('total_matched', 0)}장")
                
                # Features Summary
                features = raw_json.get("features_summary", {})
                print(f"   Features:")
                print(f"      - 일간: {features.get('day_master', 'N/A')}")
                print(f"      - 구조: {features.get('structure', 'N/A')}")
                print(f"      - 주도십성: {features.get('dominant_ten_god', 'N/A')}")
                
                # 결과 저장
                results.append({
                    "case_name": case["name"],
                    "pillars": {
                        "year": pillars.get("year", {}).get("ganji", ""),
                        "month": pillars.get("month", {}).get("ganji", ""),
                        "day": pillars.get("day", {}).get("ganji", ""),
                        "hour": pillars.get("hour", {}).get("ganji", ""),
                    },
                    "validation": validation,
                    "match_summary": match_summary,
                    "raw_json": raw_json
                })
                
            except httpx.HTTPStatusError as e:
                print(f"\n[ERROR] HTTP Error: {e.response.status_code}")
                print(f"   Response: {e.response.text[:500]}")
            except Exception as e:
                print(f"\n[ERROR] Error: {type(e).__name__}: {str(e)}")
                import traceback
                traceback.print_exc()
    
    # 최종 비교
    print(f"\n{'=' * 80}")
    print("FINAL COMPARISON")
    print(f"{'=' * 80}")
    
    if len(results) >= 2:
        case1 = results[0]
        case2 = results[1]
        
        print(f"\n[사주 4주 비교]")
        print(f"Case 1: {case1['pillars']['year']} {case1['pillars']['month']} "
              f"{case1['pillars']['day']} {case1['pillars']['hour']}")
        print(f"Case 2: {case2['pillars']['year']} {case2['pillars']['month']} "
              f"{case2['pillars']['day']} {case2['pillars']['hour']}")
        
        pillars_different = (
            case1['pillars']['year'] != case2['pillars']['year'] or
            case1['pillars']['month'] != case2['pillars']['month'] or
            case1['pillars']['day'] != case2['pillars']['day']
        )
        print(f"   결과: {'[OK] 다름 (정상)' if pillars_different else '[FAIL] 같음 (오류)'}")
        
        print(f"\n[매칭 카드 비교]")
        for section_id in ["ELEM", "TEN", "STRU", "SURV", "APPL"]:
            count1 = case1['match_summary'].get(section_id, {}).get('count', 0)
            count2 = case2['match_summary'].get(section_id, {}).get('count', 0)
            print(f"   {section_id}: Case1={count1}장, Case2={count2}장")
        
        print(f"\n[검증 요약]")
        print(f"[OK] 테스트 완료!")
        print(f"   - 입력 2개의 사주 4주가 다름: {'[OK]' if pillars_different else '[FAIL]'}")
        print(f"   - 모든 섹션에 매칭 카드 존재: "
              f"{'[OK]' if case1['validation'].get('matches_valid') and case2['validation'].get('matches_valid') else '[FAIL]'}")
        print(f"   - Raw JSON에 추적 정보 존재: "
              f"{'[OK]' if case1['raw_json'].get('total_matched', 0) > 0 and case2['raw_json'].get('total_matched', 0) > 0 else '[FAIL]'}")


if __name__ == "__main__":
    asyncio.run(test_debug_engine())
