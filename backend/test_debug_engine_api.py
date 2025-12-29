"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5단계: Debug 엔드포인트 테스트 - 엔진 통합 검증
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import asyncio
import json
import sys
import os
from pathlib import Path
from datetime import datetime

# UTF-8 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import httpx

async def test_debug_engine():
    """Debug 엔드포인트 테스트"""
    
    print("\n" + "="*80)
    print("🔥 5단계: Debug 엔드포인트 테스트")
    print("="*80)
    
    base_url = "http://localhost:8000/api/v1"
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 테스트 케이스: 2개의 다른 사주
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    test_cases = [
        {
            "name": "케이스 1: 1985-05-15 14시",
            "params": {
                "birth_year": 1985,
                "birth_month": 5,
                "birth_day": 15,
                "birth_hour": 14,
                "target_year": 2026
            }
        },
        {
            "name": "케이스 2: 1988-11-23 10시",
            "params": {
                "birth_year": 1988,
                "birth_month": 11,
                "birth_day": 23,
                "birth_hour": 10,
                "target_year": 2026
            }
        }
    ]
    
    results = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, test_case in enumerate(test_cases):
            print(f"\n[{i+1}] {test_case['name']}")
            print(f"   입력: {test_case['params']}")
            
            try:
                response = await client.get(
                    f"{base_url}/debug/engine",
                    params=test_case["params"]
                )
                
                if response.status_code == 200:
                    data = response.json()
                    results.append(data)
                    
                    print(f"   ✅ 응답 성공!")
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # 1. Pillars 검증
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    pillars = data.get("pillars", {})
                    year_ganji = pillars.get("year", {}).get("ganji", "N/A")
                    month_ganji = pillars.get("month", {}).get("ganji", "N/A")
                    day_ganji = pillars.get("day", {}).get("ganji", "N/A")
                    hour_ganji = pillars.get("hour", {}).get("ganji", "N/A")
                    
                    print(f"\n   📅 사주 8글자:")
                    print(f"      년주: {year_ganji}")
                    print(f"      월주: {month_ganji}")
                    print(f"      일주: {day_ganji}")
                    print(f"      시주: {hour_ganji}")
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # 2. Derived 검증
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    derived = data.get("derived", {})
                    print(f"\n   🔍 파생 특징:")
                    print(f"      일간: {derived.get('day_master', 'N/A')} ({derived.get('day_master_element', 'N/A')})")
                    print(f"      구조: {derived.get('structure', 'N/A')}")
                    print(f"      강약: {'신강' if derived.get('is_strong_self') else '신약'}")
                    print(f"      주도 십성: {derived.get('dominant_ten_god', 'N/A')}")
                    print(f"      강한 오행: {derived.get('strong_elements', [])}")
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # 3. Match Summary 검증
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    match_summary = data.get("match_summary", {})
                    print(f"\n   🎯 매칭 요약:")
                    for section_id, section_data in match_summary.items():
                        count = section_data.get("count", 0)
                        avg_score = section_data.get("avg_score", 0)
                        top_cards = section_data.get("top_cards", [])
                        
                        print(f"      {section_id}: {count}장 (평균점수: {avg_score})")
                        
                        if top_cards:
                            top_card = top_cards[0]
                            print(f"         Top: {top_card.get('card_id')} (점수: {top_card.get('score')})")
                            
                            # 점수 상세 표시
                            score_details = top_card.get("score_details", {})
                            if score_details:
                                print(f"            Priority: {score_details.get('priority', 0)}")
                                print(f"            Tag Match: {score_details.get('tag_match', 0)}")
                                print(f"            Year Boost: {score_details.get('year_boost', 0)}")
                                print(f"            Goal Match: {score_details.get('goal_match', 0)}")
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # 4. Validation 검증
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    validation = data.get("validation", {})
                    print(f"\n   ✔️ 검증 결과:")
                    print(f"      Pillars Valid: {validation.get('pillars_valid', False)}")
                    print(f"      Matches Valid: {validation.get('matches_valid', False)}")
                    print(f"      Scores Valid: {validation.get('scores_valid', False)}")
                    print(f"      Total Matched Cards: {validation.get('total_matched_cards', 0)}")
                    print(f"      Rulecards Loaded: {validation.get('rulecards_loaded', 0)}")
                    print(f"      All Checks Passed: {'✅' if validation.get('all_checks_passed') else '❌'}")
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # 5. Raw JSON 검증
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    raw_json = data.get("raw_json", {})
                    print(f"\n   📦 Raw JSON:")
                    print(f"      Matched Rule IDs: {len(raw_json.get('matched_rule_ids', []))}개")
                    print(f"      Match Scores: {len(raw_json.get('match_scores', {}))}개")
                    print(f"      Total Matched: {raw_json.get('total_matched', 0)}")
                    
                else:
                    print(f"   ❌ 실패: {response.status_code}")
                    print(f"   {response.text}")
                    
            except Exception as e:
                print(f"   ❌ 오류: {e}")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 케이스 간 비교 검증
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n" + "="*80)
    print("🔍 케이스 간 비교 검증")
    print("="*80)
    
    if len(results) >= 2:
        pillars1 = results[0].get("pillars", {})
        pillars2 = results[1].get("pillars", {})
        
        year1 = pillars1.get("year", {}).get("ganji", "")
        year2 = pillars2.get("year", {}).get("ganji", "")
        
        month1 = pillars1.get("month", {}).get("ganji", "")
        month2 = pillars2.get("month", {}).get("ganji", "")
        
        day1 = pillars1.get("day", {}).get("ganji", "")
        day2 = pillars2.get("day", {}).get("ganji", "")
        
        hour1 = pillars1.get("hour", {}).get("ganji", "")
        hour2 = pillars2.get("hour", {}).get("ganji", "")
        
        print(f"\n케이스 1 사주: {year1} {month1} {day1} {hour1}")
        print(f"케이스 2 사주: {year2} {month2} {day2} {hour2}")
        
        # 🔥 핵심 검증: 사주가 다른지 확인
        pillars_different = (
            year1 != year2 or
            month1 != month2 or
            day1 != day2 or
            hour1 != hour2
        )
        
        if pillars_different:
            print(f"\n✅ 검증 통과: 두 케이스의 사주가 다릅니다!")
        else:
            print(f"\n❌ 검증 실패: 두 케이스의 사주가 동일합니다!")
        
        # 매칭 결과도 다른지 확인
        match1 = results[0].get("match_summary", {})
        match2 = results[1].get("match_summary", {})
        
        matches_different = False
        for section_id in match1.keys():
            top1 = match1[section_id].get("top_cards", [{}])[0].get("card_id", "")
            top2 = match2[section_id].get("top_cards", [{}])[0].get("card_id", "")
            
            if top1 != top2:
                matches_different = True
                print(f"   {section_id}: Top 카드 다름 ({top1} vs {top2})")
        
        if matches_different:
            print(f"\n✅ 검증 통과: 매칭 결과가 다릅니다!")
        else:
            print(f"\n⚠️ 주의: 일부 섹션의 Top 카드가 동일합니다.")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 최종 결과 요약
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n" + "="*80)
    print("✅ 5단계 Debug 엔드포인트 테스트 완료!")
    print("="*80)
    
    if len(results) >= 2:
        val1 = results[0].get("validation", {})
        val2 = results[1].get("validation", {})
        
        print(f"\n📊 전체 검증 결과:")
        print(f"   케이스 1: {'✅ PASS' if val1.get('all_checks_passed') else '❌ FAIL'}")
        print(f"   케이스 2: {'✅ PASS' if val2.get('all_checks_passed') else '❌ FAIL'}")
        print(f"   Pillars 다름: {'✅' if pillars_different else '❌'}")
        print(f"   Matches 다름: {'✅' if matches_different else '⚠️'}")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    asyncio.run(test_debug_engine())
