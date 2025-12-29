# -*- coding: utf-8 -*-
"""
SajuOS V1.0 Hybrid Engine Integration Test
"""
import asyncio
import sys
import json
from pathlib import Path

# 백엔드 app 모듈 임포트
sys.path.insert(0, str(Path(__file__).parent))

from app.services.calc_module import calc_module
from app.services.derive_module import derive_module
from app.services.match_module import match_module


TEST_CASES = [
    {
        "name": "Case1 - 1988-05-15 10:00",
        "birth_year": 1988,
        "birth_month": 5,
        "birth_day": 15,
        "birth_hour": 10,
        "target_year": 2026
    },
    {
        "name": "Case2 - 1990-12-25 14:00",
        "birth_year": 1990,
        "birth_month": 12,
        "birth_day": 25,
        "birth_hour": 14,
        "target_year": 2026
    },
    {
        "name": "Case3 - 1985-03-08 06:00",
        "birth_year": 1985,
        "birth_month": 3,
        "birth_day": 8,
        "birth_hour": 6,
        "target_year": 2026
    }
]


async def test_case(case: dict) -> dict:
    """Run single test case"""
    print(f"\n{'='*80}")
    print(f"[TEST] {case['name']}")
    print(f"{'='*80}")
    
    result = {
        "name": case["name"],
        "input": case,
        "pillars": None,
        "derived": None,
        "match_summary": {},
        "validation": {},
        "errors": []
    }
    
    try:
        # STEP 1: Calc Module
        print(f"\n[Step 1] Calc module...")
        pillars = await calc_module.calculate_pillars(
            birth_year=case["birth_year"],
            birth_month=case["birth_month"],
            birth_day=case["birth_day"],
            birth_hour=case["birth_hour"],
            birth_minute=0
        )
        
        year_ganji = pillars.year.ganji if pillars.year else "?"
        month_ganji = pillars.month.ganji if pillars.month else "?"
        day_ganji = pillars.day.ganji if pillars.day else "?"
        hour_ganji = pillars.hour.ganji if pillars.hour else "?"
        
        result["pillars"] = {
            "year": year_ganji,
            "month": month_ganji,
            "day": day_ganji,
            "hour": hour_ganji
        }
        
        print(f"[OK] Calc: {year_ganji} {month_ganji} {day_ganji} {hour_ganji}")
        
        # Pillars validation - hour can be without hanja
        pillars_valid = all([
            pillars.year is not None,
            pillars.month is not None,
            pillars.day is not None,
            len(year_ganji) >= 2,  # At least 2 chars
            len(month_ganji) >= 2,
            len(day_ganji) >= 2
        ])
        
        result["validation"]["pillars_valid"] = pillars_valid
        
        if not pillars_valid:
            result["errors"].append("Pillars calculation failed")
            return result
        
        # STEP 2: Derive Module
        print(f"\n[Step 2] Derive module...")
        features = derive_module.derive_features(pillars, target_year=case["target_year"])
        
        result["derived"] = {
            "day_master": features.day_master,
            "day_master_element": features.day_master_element,
            "is_strong_self": features.is_strong_self,
            "structure": features.structure,
            "dominant_ten_god": features.dominant_ten_god,
            "strong_elements": features.strong_elements,
            "weak_elements": features.weak_elements
        }
        
        print(f"[OK] Derive:")
        print(f"   Day Master: {features.day_master} ({features.day_master_element})")
        print(f"   Structure: {features.structure}")
        print(f"   Strength: {'Strong' if features.is_strong_self else 'Weak'}")
        print(f"   Dominant Ten God: {features.dominant_ten_god}")
        
        # STEP 3: Match Module
        print(f"\n[Step 3] Match module...")
        
        if not match_module.loaded or not match_module.store:
            print(f"   Loading rulecards...")
            
            backend_path = Path(__file__).parent
            rulecards_path = backend_path / "data" / "rulecards.jsonl"
            
            if not rulecards_path.exists():
                rulecards_path = backend_path / "temp_rulecards.jsonl"
            
            if not rulecards_path.exists():
                raise FileNotFoundError(f"Rulecards file not found: {rulecards_path}")
            
            print(f"   Rulecards file: {rulecards_path}")
            match_module.load_rulecards(str(rulecards_path))
        
        total_cards = len(match_module.store.cards) if match_module.store else 0
        by_topic = match_module.store.by_topic if match_module.store else {}
        
        print(f"[OK] Rulecards loaded: {total_cards} cards")
        for topic, cards in by_topic.items():
            print(f"   {topic}: {len(cards)} cards")
        
        result["validation"]["rulecards_loaded"] = total_cards
        
        if total_cards == 0:
            result["errors"].append("Rulecards loading failed: 0 cards")
            return result
        
        matches = match_module.match_all_sections(features)
        print(f"[OK] Match completed: {len(matches)} sections")
        
        # STEP 4: Match Summary
        total_matched_cards = 0
        
        for section_id, section_match in matches.items():
            card_count = len(section_match.cards)
            total_matched_cards += card_count
            
            top_cards = [
                {
                    "card_id": card.card_id,
                    "score": round(card.score, 2),
                    "score_details": card.score_details
                }
                for card in section_match.cards[:3]
            ]
            
            result["match_summary"][section_id] = {
                "count": card_count,
                "top_cards": top_cards,
                "avg_score": round(section_match.avg_score, 2)
            }
            
            print(f"   {section_id}: {card_count} cards, avg_score: {section_match.avg_score:.2f}")
        
        matches_valid = all([
            len(section_match.cards) > 0
            for section_match in matches.values()
        ])
        
        scores_valid = all([
            section_match.avg_score > 0
            for section_match in matches.values()
        ])
        
        result["validation"]["matches_valid"] = matches_valid
        result["validation"]["scores_valid"] = scores_valid
        result["validation"]["total_matched_cards"] = total_matched_cards
        
        # STEP 5: Validation
        result["validation"]["all_checks_passed"] = all([
            pillars_valid,
            matches_valid,
            scores_valid,
            total_cards > 0,
            total_matched_cards > 0
        ])
        
        print(f"\n{'='*80}")
        print(f"[RESULT] {case['name']}")
        print(f"   Pillars valid: {pillars_valid}")
        print(f"   Matches valid: {matches_valid}")
        print(f"   Scores valid: {scores_valid}")
        print(f"   Rulecards loaded: {total_cards}")
        print(f"   Total matched cards: {total_matched_cards}")
        print(f"   All checks: {'PASS' if result['validation']['all_checks_passed'] else 'FAIL'}")
        print(f"{'='*80}")
        
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        result["errors"].append(str(e))
        import traceback
        traceback.print_exc()
    
    return result


async def compare_results(results: list):
    """Compare test results"""
    print(f"\n{'='*80}")
    print(f"[COMPARISON] Test Results")
    print(f"{'='*80}")
    
    # 1. Check if pillars are unique
    print(f"\n[1] Pillars comparison:")
    pillars_set = set()
    for r in results:
        if r["pillars"]:
            pillar_str = f"{r['pillars']['year']} {r['pillars']['month']} {r['pillars']['day']} {r['pillars']['hour']}"
            print(f"   {r['name']}: {pillar_str}")
            pillars_set.add(pillar_str)
    
    pillars_unique = len(pillars_set) == len(results)
    print(f"   -> Unique: {'PASS' if pillars_unique else 'FAIL'} ({len(pillars_set)}/{len(results)})")
    
    # 2. Check derived features
    print(f"\n[2] Derived features:")
    for r in results:
        if r["derived"]:
            print(f"   {r['name']}:")
            print(f"      Day Master: {r['derived']['day_master']} ({r['derived']['day_master_element']})")
            print(f"      Structure: {r['derived']['structure']}")
            print(f"      Strength: {'Strong' if r['derived']['is_strong_self'] else 'Weak'}")
    
    # 3. Check matched cards count
    print(f"\n[3] Matched cards count:")
    all_sections_have_cards = True
    for r in results:
        print(f"   {r['name']}:")
        for section_id, summary in r["match_summary"].items():
            card_count = summary["count"]
            print(f"      {section_id}: {card_count} cards")
            if card_count == 0:
                all_sections_have_cards = False
    
    print(f"   -> All sections have cards: {'PASS' if all_sections_have_cards else 'FAIL'}")
    
    # 4. Overall validation
    print(f"\n[4] Overall validation:")
    all_passed = all([r["validation"].get("all_checks_passed", False) for r in results])
    
    for r in results:
        status = "PASS" if r["validation"].get("all_checks_passed", False) else "FAIL"
        print(f"   {r['name']}: {status}")
    
    print(f"\n{'='*80}")
    final_result = all_passed and pillars_unique and all_sections_have_cards
    print(f"[FINAL] {'ALL TESTS PASSED' if final_result else 'SOME TESTS FAILED'}")
    print(f"{'='*80}")
    
    return {
        "all_passed": all_passed,
        "pillars_unique": pillars_unique,
        "all_sections_have_cards": all_sections_have_cards,
        "final_result": final_result
    }


async def main():
    """Main test execution"""
    print("""
================================================================================
                                                                          
              SajuOS V1.0 Hybrid Engine Integration Test                    
                                                                          
  Purpose:                                                                   
  1. Verify Calc->Derive->Match flow                                        
  2. Check rulecard loading (prevent 0 cards)                                          
  3. Verify Match scoring and ranking                                           
  4. Verify different inputs produce different results                          
                                                                          
================================================================================
    """)
    
    # Run all test cases
    results = []
    for case in TEST_CASES:
        result = await test_case(case)
        results.append(result)
    
    # Compare results
    comparison = await compare_results(results)
    
    # Save JSON
    output_path = Path(__file__).parent / "test_v1_hybrid_engine_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "test_cases": results,
            "comparison": comparison,
            "timestamp": asyncio.get_event_loop().time()
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n[OK] Test results saved: {output_path}")
    
    return comparison["final_result"]


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
