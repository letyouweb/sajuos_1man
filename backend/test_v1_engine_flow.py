# -*- coding: utf-8 -*-
"""
SajuOS V1.0 Hybrid Engine Flow Test
"""
import asyncio
import httpx
import json
from datetime import datetime


async def test_engine_debug():
    """Engine debug endpoint test"""
    
    base_url = "http://localhost:8000"
    
    # Test case 1: 1988-05-15 10:00
    test_case_1 = {
        "birth_year": 1988,
        "birth_month": 5,
        "birth_day": 15,
        "birth_hour": 10,
        "target_year": 2026
    }
    
    # Test case 2: 1990-12-25 14:00
    test_case_2 = {
        "birth_year": 1990,
        "birth_month": 12,
        "birth_day": 25,
        "birth_hour": 14,
        "target_year": 2026
    }
    
    print("=" * 80)
    print("[DEBUG] SajuOS V1.0 Hybrid Engine Flow Test")
    print("=" * 80)
    print()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1
        print("[TEST 1] 1988-05-15 10:00")
        print("-" * 80)
        
        try:
            response1 = await client.get(
                f"{base_url}/api/v1/debug/engine",
                params=test_case_1
            )
            response1.raise_for_status()
            result1 = response1.json()
            
            print("Request OK")
            print()
            
            # Pillars
            pillars1 = result1.get("pillars", {})
            year1 = pillars1.get("year", {}).get("ganji", "?")
            month1 = pillars1.get("month", {}).get("ganji", "?")
            day1 = pillars1.get("day", {}).get("ganji", "?")
            hour1 = pillars1.get("hour", {}).get("ganji", "?")
            
            print(f"Pillars: {year1} {month1} {day1} {hour1}")
            print()
            
            # Derived Features
            derived1 = result1.get("derived", {})
            print(f"Derived Features:")
            print(f"  - Day Master: {derived1.get('day_master')} ({derived1.get('day_master_element')})")
            print(f"  - Structure: {derived1.get('structure')}")
            print(f"  - Strength: {'Strong' if derived1.get('is_strong_self') else 'Weak'}")
            print(f"  - Dominant Ten God: {derived1.get('dominant_ten_god')}")
            print()
            
            # Match Summary
            match_summary1 = result1.get("match_summary", {})
            print(f"Match Summary:")
            total_cards1 = 0
            for section_id, summary in match_summary1.items():
                card_count = summary.get("count", 0)
                avg_score = summary.get("avg_score", 0)
                total_cards1 += card_count
                print(f"  - {section_id}: {card_count} cards, avg_score: {avg_score:.2f}")
                
                # Top 3 cards
                top_cards = summary.get("top_cards", [])[:3]
                for i, card_info in enumerate(top_cards, 1):
                    card_id = card_info.get("card_id", "")
                    score = card_info.get("score", 0)
                    score_details = card_info.get("score_details", {})
                    print(f"      {i}. {card_id} (score: {score:.2f})")
                    if score_details:
                        print(f"         - base: {score_details.get('base_score', 0):.2f}, "
                              f"tag: {score_details.get('tag_match_score', 0):.2f}, "
                              f"year: {score_details.get('year_boost', 0):.2f}, "
                              f"goal: {score_details.get('goal_boost', 0):.2f}")
            
            print()
            print(f"  Total Matched Cards: {total_cards1}")
            print()
            
            # Raw JSON Summary
            raw_json1 = result1.get("raw_json", {})
            matched_ids1 = raw_json1.get("matched_rule_ids", [])
            match_scores1 = raw_json1.get("match_scores", {})
            
            print(f"Raw JSON Summary:")
            print(f"  - Total Card IDs: {len(matched_ids1)}")
            print(f"  - Score Records: {len(match_scores1)}")
            print()
            
            # Validation
            validation1 = result1.get("validation", {})
            print(f"Validation:")
            print(f"  - Pillars Valid: {validation1.get('pillars_valid')}")
            print(f"  - Matches Valid: {validation1.get('matches_valid')}")
            print(f"  - Scores Valid: {validation1.get('scores_valid')}")
            print(f"  - Rulecards Loaded: {validation1.get('rulecards_loaded')}")
            print(f"  - All Checks Passed: {validation1.get('all_checks_passed')}")
            print()
            
        except Exception as e:
            print(f"[ERROR] Test 1 failed: {e}")
            return
        
        # Test 2
        print("=" * 80)
        print("[TEST 2] 1990-12-25 14:00")
        print("-" * 80)
        
        try:
            response2 = await client.get(
                f"{base_url}/api/v1/debug/engine",
                params=test_case_2
            )
            response2.raise_for_status()
            result2 = response2.json()
            
            print("Request OK")
            print()
            
            # Pillars
            pillars2 = result2.get("pillars", {})
            year2 = pillars2.get("year", {}).get("ganji", "?")
            month2 = pillars2.get("month", {}).get("ganji", "?")
            day2 = pillars2.get("day", {}).get("ganji", "?")
            hour2 = pillars2.get("hour", {}).get("ganji", "?")
            
            print(f"Pillars: {year2} {month2} {day2} {hour2}")
            print()
            
            # Derived Features
            derived2 = result2.get("derived", {})
            print(f"Derived Features:")
            print(f"  - Day Master: {derived2.get('day_master')} ({derived2.get('day_master_element')})")
            print(f"  - Structure: {derived2.get('structure')}")
            print(f"  - Strength: {'Strong' if derived2.get('is_strong_self') else 'Weak'}")
            print(f"  - Dominant Ten God: {derived2.get('dominant_ten_god')}")
            print()
            
            # Match Summary
            match_summary2 = result2.get("match_summary", {})
            print(f"Match Summary:")
            total_cards2 = 0
            for section_id, summary in match_summary2.items():
                card_count = summary.get("count", 0)
                avg_score = summary.get("avg_score", 0)
                total_cards2 += card_count
                print(f"  - {section_id}: {card_count} cards, avg_score: {avg_score:.2f}")
            
            print()
            print(f"  Total Matched Cards: {total_cards2}")
            print()
            
            # Validation
            validation2 = result2.get("validation", {})
            print(f"Validation:")
            print(f"  - Pillars Valid: {validation2.get('pillars_valid')}")
            print(f"  - Matches Valid: {validation2.get('matches_valid')}")
            print(f"  - Scores Valid: {validation2.get('scores_valid')}")
            print(f"  - Rulecards Loaded: {validation2.get('rulecards_loaded')}")
            print(f"  - All Checks Passed: {validation2.get('all_checks_passed')}")
            print()
            
        except Exception as e:
            print(f"[ERROR] Test 2 failed: {e}")
            return
        
        # Comparison
        print("=" * 80)
        print("Comparison Analysis")
        print("=" * 80)
        print()
        
        # 1. Pillars comparison
        pillars_different = (
            (year1 != year2) or
            (month1 != month2) or
            (day1 != day2) or
            (hour1 != hour2)
        )
        
        print(f"1. Pillars Comparison:")
        print(f"   Test1: {year1} {month1} {day1} {hour1}")
        print(f"   Test2: {year2} {month2} {day2} {hour2}")
        print(f"   Result: {'OK - Different' if pillars_different else 'FAIL - Same'}")
        print()
        
        # 2. Section card counts
        print(f"2. Section Card Counts:")
        all_sections_have_cards = True
        for section_id in ["ELEM", "TEN", "STRU", "SURV", "APPL"]:
            count1 = match_summary1.get(section_id, {}).get("count", 0)
            count2 = match_summary2.get(section_id, {}).get("count", 0)
            print(f"   - {section_id}: {count1} vs {count2}")
            if count1 == 0 or count2 == 0:
                all_sections_have_cards = False
        
        print(f"   Result: {'OK - All sections have cards' if all_sections_have_cards else 'FAIL - Some sections have 0 cards'}")
        print()
        
        # 3. Raw JSON validation
        print(f"3. Raw JSON Validation:")
        print(f"   Test1: {len(matched_ids1)} card IDs, {len(match_scores1)} scores")
        print(f"   Test2: {len(result2.get('raw_json', {}).get('matched_rule_ids', []))} card IDs")
        has_trace = len(matched_ids1) > 0 and len(match_scores1) > 0
        print(f"   Result: {'OK - Trace info exists' if has_trace else 'FAIL - No trace info'}")
        print()
        
        # 4. Final result
        print("=" * 80)
        print("Final Validation Result")
        print("=" * 80)
        
        all_pass = (
            pillars_different and
            all_sections_have_cards and
            has_trace and
            validation1.get('all_checks_passed', False) and
            validation2.get('all_checks_passed', False)
        )
        
        print(f"[OK] Pillars Different: {pillars_different}")
        print(f"[OK] All Sections Have Cards: {all_sections_have_cards}")
        print(f"[OK] Raw JSON Trace Exists: {has_trace}")
        print(f"[OK] Test1 All Checks Passed: {validation1.get('all_checks_passed', False)}")
        print(f"[OK] Test2 All Checks Passed: {validation2.get('all_checks_passed', False)}")
        print()
        
        if all_pass:
            print("=" * 80)
            print("[SUCCESS] All validation passed! SajuOS V1.0 Engine works correctly!")
            print("=" * 80)
        else:
            print("=" * 80)
            print("[WARN] Some validation failed. Need improvements")
            print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_engine_debug())
