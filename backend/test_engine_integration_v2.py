"""
SajuOS V1.0 Hybrid Engine Integration Test
"""
import asyncio
import sys
import os
from pathlib import Path

# Add project root to sys.path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from app.services.calc_module import calc_module
from app.services.derive_module import derive_module
from app.services.match_module import match_module
from app.services.rulecards_store import RuleCardStore


def print_header(title: str):
    """Print header"""
    print(f"\n{'=' * 70}")
    print(f">>> {title}")
    print(f"{'=' * 70}\n")


def print_section(title: str):
    """Print section"""
    print(f"\n{'-' * 50}")
    print(f">> {title}")
    print(f"{'-' * 50}")


async def test_case_1():
    """
    Test Case 1: 1988-05-15 10:00
    """
    print_header("TEST CASE 1: 1988-05-15 10:00")
    
    # STEP 1: Calc
    print_section("STEP 1: Calc Module")
    pillars = await calc_module.calculate_pillars(
        birth_year=1988,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        birth_minute=0
    )
    
    year_ganji = pillars.year.ganji if pillars.year else "?"
    month_ganji = pillars.month.ganji if pillars.month else "?"
    day_ganji = pillars.day.ganji if pillars.day else "?"
    hour_ganji = pillars.hour.ganji if pillars.hour else "?"
    
    print(f"   Year : {year_ganji}")
    print(f"   Month: {month_ganji}")
    print(f"   Day  : {day_ganji}")
    print(f"   Hour : {hour_ganji}")
    
    # STEP 2: Derive
    print_section("STEP 2: Derive Module")
    features = derive_module.derive_features(pillars, target_year=2026)
    
    print(f"   Day Master: {features.day_master} ({features.day_master_element})")
    print(f"   Structure : {features.structure}")
    print(f"   Strength  : {'Strong' if features.is_strong_self else 'Weak'}")
    print(f"   Strong Elements: {features.strong_elements}")
    print(f"   Dominant TenGod: {features.dominant_ten_god}")
    
    # STEP 3: Match
    print_section("STEP 3: Match Module")
    if not match_module.loaded:
        print("   [WARN] RuleCards not loaded - trying to load...")
        
        # Find rulecards
        possible_paths = [
            backend_path / "data" / "rulecards.jsonl",
            backend_path / "temp_rulecards.jsonl",
            backend_path / "data" / "sajuos_master_db.jsonl"
        ]
        
        for p in possible_paths:
            if p.exists():
                print(f"   [INFO] RuleCards found: {p}")
                match_module.load_rulecards(str(p))
                break
    
    if not match_module.loaded:
        print(f"   [ERROR] Cannot find RuleCards file")
        return None
    
    matches = match_module.match_all_sections(features)
    
    print(f"   Total Sections: {len(matches)}")
    for section_id, section_match in matches.items():
        card_count = len(section_match.cards)
        avg_score = section_match.avg_score
        print(f"   - {section_id}: {card_count} cards, avg_score: {avg_score:.2f}")
        
        # Show top 3 cards
        for i, card in enumerate(section_match.cards[:3], 1):
            print(f"      #{i} {card.card_id} (score: {card.score:.2f})")
    
    # STEP 4: Raw JSON
    print_section("STEP 4: Raw JSON Generation")
    raw_json = match_module.generate_raw_json(features, matches)
    
    total_matched = len(raw_json["matched_rule_ids"])
    print(f"   Total Matched Cards: {total_matched}")
    print(f"   match_scores keys  : {len(raw_json['match_scores'])}")
    print(f"   fired_triggers keys: {len(raw_json['fired_triggers'])}")
    
    # Show sample
    if total_matched > 0:
        sample_id = raw_json["matched_rule_ids"][0]
        sample_score = raw_json["match_scores"].get(sample_id, 0)
        sample_triggers = raw_json["fired_triggers"].get(sample_id, [])
        print(f"\n   Sample Card: {sample_id}")
        print(f"   - Score   : {sample_score:.2f}")
        print(f"   - Triggers: {sample_triggers[:3]}")
    
    return {
        "pillars": {
            "year": year_ganji,
            "month": month_ganji,
            "day": day_ganji,
            "hour": hour_ganji
        },
        "features": features,
        "matches": matches,
        "raw_json": raw_json
    }


async def test_case_2():
    """
    Test Case 2: 1990-12-25 14:00 (different case)
    """
    print_header("TEST CASE 2: 1990-12-25 14:00")
    
    # STEP 1: Calc
    print_section("STEP 1: Calc Module")
    pillars = await calc_module.calculate_pillars(
        birth_year=1990,
        birth_month=12,
        birth_day=25,
        birth_hour=14,
        birth_minute=0
    )
    
    year_ganji = pillars.year.ganji if pillars.year else "?"
    month_ganji = pillars.month.ganji if pillars.month else "?"
    day_ganji = pillars.day.ganji if pillars.day else "?"
    hour_ganji = pillars.hour.ganji if pillars.hour else "?"
    
    print(f"   Year : {year_ganji}")
    print(f"   Month: {month_ganji}")
    print(f"   Day  : {day_ganji}")
    print(f"   Hour : {hour_ganji}")
    
    # STEP 2: Derive
    print_section("STEP 2: Derive Module")
    features = derive_module.derive_features(pillars, target_year=2026)
    
    print(f"   Day Master: {features.day_master} ({features.day_master_element})")
    print(f"   Structure : {features.structure}")
    print(f"   Strength  : {'Strong' if features.is_strong_self else 'Weak'}")
    print(f"   Strong Elements: {features.strong_elements}")
    print(f"   Dominant TenGod: {features.dominant_ten_god}")
    
    # STEP 3: Match
    print_section("STEP 3: Match Module")
    matches = match_module.match_all_sections(features)
    
    print(f"   Total Sections: {len(matches)}")
    for section_id, section_match in matches.items():
        card_count = len(section_match.cards)
        avg_score = section_match.avg_score
        print(f"   - {section_id}: {card_count} cards, avg_score: {avg_score:.2f}")
        
        # Show top 3 cards
        for i, card in enumerate(section_match.cards[:3], 1):
            print(f"      #{i} {card.card_id} (score: {card.score:.2f})")
    
    # STEP 4: Raw JSON
    print_section("STEP 4: Raw JSON Generation")
    raw_json = match_module.generate_raw_json(features, matches)
    
    total_matched = len(raw_json["matched_rule_ids"])
    print(f"   Total Matched Cards: {total_matched}")
    print(f"   match_scores keys  : {len(raw_json['match_scores'])}")
    print(f"   fired_triggers keys: {len(raw_json['fired_triggers'])}")
    
    # Show sample
    if total_matched > 0:
        sample_id = raw_json["matched_rule_ids"][0]
        sample_score = raw_json["match_scores"].get(sample_id, 0)
        sample_triggers = raw_json["fired_triggers"].get(sample_id, [])
        print(f"\n   Sample Card: {sample_id}")
        print(f"   - Score   : {sample_score:.2f}")
        print(f"   - Triggers: {sample_triggers[:3]}")
    
    return {
        "pillars": {
            "year": year_ganji,
            "month": month_ganji,
            "day": day_ganji,
            "hour": hour_ganji
        },
        "features": features,
        "matches": matches,
        "raw_json": raw_json
    }


async def verify_differences(result1, result2):
    """
    Compare two test case results
    """
    print_header("Verification Results")
    
    # 1. Check if pillars are different
    print_section("1. Pillars Difference Verification")
    pillars1 = result1["pillars"]
    pillars2 = result2["pillars"]
    
    all_different = True
    for key in ["year", "month", "day", "hour"]:
        if pillars1[key] == pillars2[key]:
            print(f"   [FAIL] {key} same: {pillars1[key]}")
            all_different = False
        else:
            print(f"   [PASS] {key} different: {pillars1[key]} vs {pillars2[key]}")
    
    if all_different:
        print(f"\n   [PASS] All pillars are different")
    else:
        print(f"\n   [WARN] Some pillars are the same")
    
    # 2. Check if matched card count is not zero
    print_section("2. Matched Card Count Verification")
    
    for case_name, result in [("Case 1", result1), ("Case 2", result2)]:
        print(f"\n   {case_name}:")
        all_non_zero = True
        for section_id, section_match in result["matches"].items():
            card_count = len(section_match.cards)
            if card_count == 0:
                print(f"      [FAIL] {section_id}: {card_count} cards (ZERO!)")
                all_non_zero = False
            else:
                print(f"      [PASS] {section_id}: {card_count} cards")
        
        if all_non_zero:
            print(f"      [PASS] All sections have matched cards")
        else:
            print(f"      [FAIL] Some sections have no cards")
    
    # 3. Check raw JSON fields
    print_section("3. Raw JSON Fields Verification")
    
    for case_name, result in [("Case 1", result1), ("Case 2", result2)]:
        print(f"\n   {case_name}:")
        raw_json = result["raw_json"]
        
        has_rule_ids = len(raw_json.get("matched_rule_ids", [])) > 0
        has_scores = len(raw_json.get("match_scores", {})) > 0
        has_triggers = len(raw_json.get("fired_triggers", {})) > 0
        
        print(f"      matched_rule_ids: {'[PASS]' if has_rule_ids else '[FAIL]'} ({len(raw_json.get('matched_rule_ids', []))} items)")
        print(f"      match_scores    : {'[PASS]' if has_scores else '[FAIL]'} ({len(raw_json.get('match_scores', {}))} items)")
        print(f"      fired_triggers  : {'[PASS]' if has_triggers else '[FAIL]'} ({len(raw_json.get('fired_triggers', {}))} items)")
        
        if has_rule_ids and has_scores and has_triggers:
            print(f"      [PASS] All required fields exist")
        else:
            print(f"      [FAIL] Some fields are missing")
    
    # 4. Check matched card differences
    print_section("4. Matched Card Difference Verification")
    
    case1_ids = set(result1["raw_json"]["matched_rule_ids"])
    case2_ids = set(result2["raw_json"]["matched_rule_ids"])
    
    common_ids = case1_ids & case2_ids
    unique_case1 = case1_ids - case2_ids
    unique_case2 = case2_ids - case1_ids
    
    print(f"   Case 1 total cards: {len(case1_ids)}")
    print(f"   Case 2 total cards: {len(case2_ids)}")
    print(f"   Common cards     : {len(common_ids)}")
    print(f"   Case 1 unique    : {len(unique_case1)}")
    print(f"   Case 2 unique    : {len(unique_case2)}")
    
    if len(unique_case1) > 0 and len(unique_case2) > 0:
        print(f"\n   [PASS] Different cards matched for each case")
    else:
        print(f"\n   [WARN] Matched cards are almost identical")
    
    # Final summary
    print_header("Final Verification Summary")
    
    checks = {
        "pillars_different": all_different,
        "cards_non_zero": all([len(sm.cards) > 0 for sm in result1["matches"].values()]) and 
                          all([len(sm.cards) > 0 for sm in result2["matches"].values()]),
        "raw_json_complete": all([
            len(result1["raw_json"].get("matched_rule_ids", [])) > 0,
            len(result1["raw_json"].get("match_scores", {})) > 0,
            len(result1["raw_json"].get("fired_triggers", {})) > 0,
            len(result2["raw_json"].get("matched_rule_ids", [])) > 0,
            len(result2["raw_json"].get("match_scores", {})) > 0,
            len(result2["raw_json"].get("fired_triggers", {})) > 0
        ]),
        "cards_differ": len(unique_case1) > 0 and len(unique_case2) > 0
    }
    
    print(f"   1. Pillars different      : {'[PASS]' if checks['pillars_different'] else '[FAIL]'}")
    print(f"   2. Cards non-zero         : {'[PASS]' if checks['cards_non_zero'] else '[FAIL]'}")
    print(f"   3. Raw JSON complete      : {'[PASS]' if checks['raw_json_complete'] else '[FAIL]'}")
    print(f"   4. Cards differ per case  : {'[PASS]' if checks['cards_differ'] else '[WARN]'}")
    
    all_pass = all(checks.values())
    print(f"\n{'=' * 70}")
    if all_pass:
        print(f"*** ALL TESTS PASSED - SajuOS V1.0 Hybrid Engine Working ***")
    else:
        print(f"*** SOME TESTS FAILED - Need Further Investigation ***")
    print(f"{'=' * 70}\n")


async def main():
    """
    Main test execution
    """
    print(f"\n")
    print(f"{'=' * 70}")
    print(f">>> SajuOS V1.0 Hybrid Engine Integration Test")
    print(f"{'=' * 70}")
    
    # Execute test case 1
    result1 = await test_case_1()
    
    if result1 is None:
        print(f"\n[ERROR] Test failed: Cannot load RuleCards")
        return
    
    # Execute test case 2
    result2 = await test_case_2()
    
    # Compare results
    await verify_differences(result1, result2)


if __name__ == "__main__":
    asyncio.run(main())
