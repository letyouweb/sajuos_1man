# -*- coding: utf-8 -*-
"""
API Endpoint Test - Debug Engine
"""
import requests
import json

# API Base URL
BASE_URL = "http://127.0.0.1:8000"

# Test cases
test_cases = [
    {
        "name": "Case 1 - 1988-05-15 10:00",
        "params": {
            "birth_year": 1988,
            "birth_month": 5,
            "birth_day": 15,
            "birth_hour": 10,
            "target_year": 2026
        }
    },
    {
        "name": "Case 2 - 1990-12-25 14:00",
        "params": {
            "birth_year": 1990,
            "birth_month": 12,
            "birth_day": 25,
            "birth_hour": 14,
            "target_year": 2026
        }
    }
]

def test_debug_engine():
    """Test /api/v1/debug/engine endpoint"""
    print("\n" + "="*80)
    print("Testing /api/v1/debug/engine endpoint")
    print("="*80)
    
    for case in test_cases:
        print(f"\n[TEST] {case['name']}")
        print("-" * 80)
        
        try:
            # Make request
            url = f"{BASE_URL}/api/v1/debug/engine"
            response = requests.get(url, params=case['params'], timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check pillars
                pillars = data.get('pillars', {})
                print(f"[OK] Pillars:")
                print(f"   Year: {pillars.get('year_pillar', 'N/A')}")
                print(f"   Month: {pillars.get('month_pillar', 'N/A')}")
                print(f"   Day: {pillars.get('day_pillar', 'N/A')}")
                print(f"   Hour: {pillars.get('hour_pillar', 'N/A')}")
                
                # Check derived
                derived = data.get('derived', {})
                print(f"\n[OK] Derived:")
                print(f"   Day Master: {derived.get('day_master', 'N/A')} ({derived.get('day_master_element', 'N/A')})")
                print(f"   Structure: {derived.get('structure', 'N/A')}")
                print(f"   Strength: {'Strong' if derived.get('is_strong_self') else 'Weak'}")
                print(f"   Dominant Ten God: {derived.get('dominant_ten_god', 'N/A')}")
                
                # Check match_summary
                match_summary = data.get('match_summary', {})
                print(f"\n[OK] Match Summary:")
                for section_id, summary in match_summary.items():
                    count = summary.get('count', 0)
                    avg_score = summary.get('avg_score', 0)
                    print(f"   {section_id}: {count} cards, avg_score: {avg_score}")
                
                # Check rulecard_status
                rulecard_status = data.get('rulecard_status', {})
                total_cards = rulecard_status.get('total_cards', 0)
                print(f"\n[OK] Rulecard Status:")
                print(f"   Total: {total_cards} cards")
                print(f"   Loaded: {rulecard_status.get('loaded', False)}")
                
                # Check validation
                validation = data.get('validation', {})
                print(f"\n[OK] Validation:")
                print(f"   Pillars Valid: {validation.get('pillars_valid', False)}")
                print(f"   Matches Valid: {validation.get('matches_valid', False)}")
                print(f"   Scores Valid: {validation.get('scores_valid', False)}")
                print(f"   All Checks Passed: {validation.get('all_checks_passed', False)}")
                
                # Overall status
                if validation.get('all_checks_passed'):
                    print(f"\n[PASS] Test passed!")
                else:
                    print(f"\n[FAIL] Test failed!")
                
            else:
                print(f"[ERROR] Status: {response.status_code}")
                print(f"Response: {response.text}")
                
        except requests.exceptions.ConnectionError:
            print(f"[ERROR] Connection failed - Server not running at {BASE_URL}")
            print(f"Please start the backend server with: uvicorn main:app --reload")
            return False
        except Exception as e:
            print(f"[ERROR] {e}")
            return False
    
    print("\n" + "="*80)
    print("[FINAL] All API tests completed")
    print("="*80)
    return True

if __name__ == "__main__":
    test_debug_engine()
