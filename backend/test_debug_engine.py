# -*- coding: utf-8 -*-
"""
SajuOS V1.0 하이브리드 엔진 디버그 테스트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import requests
import json
from datetime import datetime

def test_debug_engine():
    """디버그 엔드포인트 테스트"""
    
    base_url = "http://localhost:8000/api/v1/debug/engine"
    
    # 테스트 케이스 2개 (입력이 다르면 결과가 달라야 함)
    test_cases = [
        {
            "name": "Case 1: 1988-05-15 10시",
            "params": {
                "birth_year": 1988,
                "birth_month": 5,
                "birth_day": 15,
                "birth_hour": 10,
                "target_year": 2026
            }
        },
        {
            "name": "Case 2: 1990-11-20 14시",
            "params": {
                "birth_year": 1990,
                "birth_month": 11,
                "birth_day": 20,
                "birth_hour": 14,
                "target_year": 2026
            }
        }
    ]
    
    results = []
    
    for case in test_cases:
        print(f"\n{'='*60}")
        print(f"🔍 {case['name']}")
        print(f"{'='*60}")
        
        try:
            response = requests.get(base_url, params=case["params"], timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # 결과 요약
            print(f"\n✅ 요청 성공 (상태 코드: {response.status_code})")
            
            # 1. Pillars 검증
            pillars = data.get("pillars", {})
            print(f"\n📅 Pillars:")
            print(f"   년주: {pillars.get('year', {}).get('ganji', 'N/A')}")
            print(f"   월주: {pillars.get('month', {}).get('ganji', 'N/A')}")
            print(f"   일주: {pillars.get('day', {}).get('ganji', 'N/A')}")
            print(f"   시주: {pillars.get('hour', {}).get('ganji', 'N/A')}")
            
            # 2. Derived Features
            derived = data.get("derived", {})
            print(f"\n🔮 Derived Features:")
            print(f"   일간: {derived.get('day_master', 'N/A')} ({derived.get('day_master_element', 'N/A')})")
            print(f"   구조: {derived.get('structure', 'N/A')}")
            print(f"   신강/약: {'신강' if derived.get('is_strong_self') else '신약'}")
            print(f"   주도 십성: {derived.get('dominant_ten_god', 'N/A')}")
            
            # 3. Match Summary
            match_summary = data.get("match_summary", {})
            print(f"\n🎯 Match Summary:")
            total_cards = 0
            for section_id, section_data in match_summary.items():
                count = section_data.get("count", 0)
                avg_score = section_data.get("avg_score", 0)
                total_cards += count
                print(f"   {section_id}: {count}장, 평균점수: {avg_score:.2f}")
            print(f"   총 매칭 카드: {total_cards}장")
            
            # 4. Raw JSON Trace
            raw_json = data.get("raw_json", {})
            matched_ids = raw_json.get("matched_rule_ids", [])
            match_scores = raw_json.get("match_scores", {})
            print(f"\n📊 Raw JSON Trace:")
            print(f"   매칭 카드 ID: {len(matched_ids)}개")
            print(f"   점수 기록: {len(match_scores)}개")
            
            # 5. Rulecard Status
            rulecard_status = data.get("rulecard_status", {})
            print(f"\n📚 Rulecard Status:")
            print(f"   로드 완료: {rulecard_status.get('loaded', False)}")
            print(f"   총 카드: {rulecard_status.get('total_cards', 0)}장")
            by_topic = rulecard_status.get("by_topic", {})
            for topic, count in by_topic.items():
                print(f"   {topic}: {count}장")
            
            # 6. Validation
            validation = data.get("validation", {})
            print(f"\n✔️ Validation:")
            print(f"   Pillars Valid: {validation.get('pillars_valid', False)}")
            print(f"   Matches Valid: {validation.get('matches_valid', False)}")
            print(f"   Scores Valid: {validation.get('scores_valid', False)}")
            print(f"   All Checks Passed: {'✅ PASS' if validation.get('all_checks_passed') else '❌ FAIL'}")
            
            # 7. 스코어링 상세 (Top 3 카드만)
            print(f"\n🎲 스코어링 상세 (각 섹션 Top 3):")
            for section_id, section_data in match_summary.items():
                top_cards = section_data.get("top_cards", [])[:3]
                if top_cards:
                    print(f"   {section_id}:")
                    for card in top_cards:
                        card_id = card.get("card_id", "N/A")
                        score = card.get("score", 0)
                        details = card.get("score_details", {})
                        print(f"      {card_id}: {score:.2f} (base:{details.get('base_score', 0):.1f}, tag:{details.get('tag_match_score', 0):.1f}, year:{details.get('year_boost', 0):.1f}, goal:{details.get('goal_boost', 0):.1f})")
            
            results.append({
                "case": case["name"],
                "pillars": pillars,
                "validation": validation,
                "match_summary": match_summary
            })
            
        except requests.exceptions.RequestException as e:
            print(f"❌ 요청 실패: {e}")
            results.append({
                "case": case["name"],
                "error": str(e)
            })
    
    # 최종 검증
    print(f"\n{'='*60}")
    print(f"🏁 최종 검증")
    print(f"{'='*60}")
    
    if len(results) >= 2:
        # 1. Pillars가 서로 다른지 확인
        pillars_1 = results[0].get("pillars", {})
        pillars_2 = results[1].get("pillars", {})
        
        pillars_diff = (
            pillars_1.get("year", {}).get("ganji") != pillars_2.get("year", {}).get("ganji") or
            pillars_1.get("month", {}).get("ganji") != pillars_2.get("month", {}).get("ganji") or
            pillars_1.get("day", {}).get("ganji") != pillars_2.get("day", {}).get("ganji")
        )
        
        print(f"\n1. ✅ Pillars가 서로 다름: {'✅ PASS' if pillars_diff else '❌ FAIL'}")
        
        # 2. 모든 섹션에 카드 존재
        all_sections_have_cards = all([
            all([
                result.get("match_summary", {}).get(section, {}).get("count", 0) > 0
                for section in ["ELEM", "TEN", "STRU", "SURV", "APPL"]
            ])
            for result in results
            if "error" not in result
        ])
        
        print(f"2. ✅ 모든 섹션에 카드 존재: {'✅ PASS' if all_sections_have_cards else '❌ FAIL'}")
        
        # 3. 모든 검증 통과
        all_validations_passed = all([
            result.get("validation", {}).get("all_checks_passed", False)
            for result in results
            if "error" not in result
        ])
        
        print(f"3. ✅ 모든 검증 통과: {'✅ PASS' if all_validations_passed else '❌ FAIL'}")
        
        # 최종 결과
        final_pass = pillars_diff and all_sections_have_cards and all_validations_passed
        print(f"\n{'='*60}")
        print(f"🏆 최종 결과: {'✅ 전체 PASS' if final_pass else '❌ 일부 FAIL'}")
        print(f"{'='*60}")
    
    # 결과 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = f"test_debug_engine_results_{timestamp}.json"
    
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n📁 결과 저장: {result_file}")


if __name__ == "__main__":
    test_debug_engine()
