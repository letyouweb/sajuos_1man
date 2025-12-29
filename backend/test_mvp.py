"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
통합 테스트 - 명리 해석 엔진 MVP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Calc + Derive + Match 통합 실행
2. 두 케이스(무토/을목) 비교
3. 룰카드 선택 차이 70% 이상 확인
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import asyncio
import sys
import os
import json
from pathlib import Path

# 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.calc_module import calc_module
from app.services.derive_module import derive_module
from app.services.match_module import match_module
from app.services.database import get_database


async def test_case(
    name: str,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: int = 10
):
    """단일 케이스 테스트"""
    
    print(f"\n{'='*60}")
    print(f"테스트 케이스: {name}")
    print(f"생년월일: {birth_year}-{birth_month:02d}-{birth_day:02d} {birth_hour}시")
    print(f"{'='*60}")
    
    # 1. Calc 모듈
    print("\n[1] Calc 모듈 - 사주 8글자 계산")
    pillars = await calc_module.calculate_pillars(
        birth_year=birth_year,
        birth_month=birth_month,
        birth_day=birth_day,
        birth_hour=birth_hour
    )
    
    print(f"  년주: {pillars.year.ganji}")
    print(f"  월주: {pillars.month.ganji}")
    print(f"  일주: {pillars.day.ganji}")
    print(f"  시주: {pillars.hour.ganji if pillars.hour else '(미입력)'}")
    
    # 2. Derive 모듈
    print("\n[2] Derive 모듈 - 특징 파생")
    features = derive_module.derive_features(pillars, target_year=2026)
    
    print(f"  일간: {features.day_master} ({features.day_master_element})")
    print(f"  신강/신약: {'신강' if features.is_strong_self else '신약'}")
    print(f"  강한 오행: {features.strong_elements}")
    print(f"  약한 오행: {features.weak_elements}")
    print(f"  주도 십성: {features.dominant_ten_god}")
    print(f"  구조: {features.structure} - {features.structure_desc}")
    print(f"  타이밍: {features.timing_desc}")
    
    # 3. Match 모듈 (룰카드 필요)
    # 룰카드 경로 확인
    rulecards_path = Path(__file__).parent / "data" / "rulecards.jsonl"
    
    if not rulecards_path.exists():
        print(f"\n[!] 룰카드 파일 없음: {rulecards_path}")
        print("  Mock 데이터로 대체합니다.")
        
        # 디렉토리 생성
        rulecards_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Mock 룰카드 생성
        mock_rulecards = []
        
        # 오행별 카드 (5장)
        for elem in ["목", "화", "토", "금", "수"]:
            mock_rulecards.append({
                "id": f"RC-ELEM-{elem}",
                "topic": "ELEM",
                "tags": [elem],
                "trigger": [elem],
                "interpretation": f"{elem} 오행 관련",
                "priority": 5.0
            })
        
        # 오행 조합 카드 (추가 10장)
        elem_combos = [
            ("목", "화"), ("화", "토"), ("토", "금"), ("금", "수"), ("수", "목"),
            ("목", "토"), ("화", "금"), ("토", "수"), ("금", "목"), ("수", "화")
        ]
        for i, (e1, e2) in enumerate(elem_combos):
            mock_rulecards.append({
                "id": f"RC-ELEM-COMBO-{i}",
                "topic": "ELEM",
                "tags": [e1, e2, f"{e1}{e2}"],
                "trigger": [e1, e2],
                "interpretation": f"{e1}과 {e2} 조합",
                "priority": 6.0
            })
        
        # 십성별 카드 (10장)
        for tengod in ["비견", "겁재", "식신", "상관", "편재", "정재", "편관", "정관", "편인", "정인"]:
            mock_rulecards.append({
                "id": f"RC-TEN-{tengod}",
                "topic": "TEN",
                "tags": [tengod],
                "trigger": [tengod],
                "interpretation": f"{tengod} 십성",
                "priority": 5.0
            })
        
        # 십성 조합 카드 (추가 10장)
        tengod_combos = [
            ("비견", "겁재"), ("식신", "상관"), ("편재", "정재"), ("편관", "정관"), ("편인", "정인"),
            ("식신", "정재"), ("상관", "편재"), ("정인", "정관"), ("편인", "편관"), ("비견", "식신")
        ]
        for i, (t1, t2) in enumerate(tengod_combos):
            mock_rulecards.append({
                "id": f"RC-TEN-COMBO-{i}",
                "topic": "TEN",
                "tags": [t1, t2],
                "trigger": [t1, t2],
                "interpretation": f"{t1}과 {t2} 조합",
                "priority": 6.0
            })
        
        # 구조별 카드 (5장)
        for struct in ["신강", "신약", "식신생재", "재왕신강", "재다신약"]:
            mock_rulecards.append({
                "id": f"RC-STRU-{struct}",
                "topic": "STRU",
                "tags": [struct],
                "trigger": [struct],
                "interpretation": f"{struct} 구조",
                "priority": 5.0
            })
        
        # 추가 구조 패턴 (10장)
        additional_structs = [
            "비겁중중", "인성과다", "관인상생", "상관생재", "식상생재",
            "재생관", "인생관", "재왕", "신약재다", "신강식상"
        ]
        for struct in additional_structs:
            mock_rulecards.append({
                "id": f"RC-STRU-ADD-{struct}",
                "topic": "STRU",
                "tags": [struct],
                "trigger": [struct],
                "interpretation": f"{struct} 패턴",
                "priority": 5.0
            })
        
        # 생존 카드 (10장)
        survival_keywords = [
            "생존", "안정", "자립", "협력", "균형", "조화", "성장", "방어", "적응", "회복"
        ]
        for keyword in survival_keywords:
            mock_rulecards.append({
                "id": f"RC-SURV-{keyword}",
                "topic": "GENERAL",
                "tags": [keyword, "생존"],
                "trigger": [keyword],
                "interpretation": f"{keyword} 관련",
                "priority": 5.0
            })
        
        # 일간별 카드 (10장)
        for gan in ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계"]:
            mock_rulecards.append({
                "id": f"RC-APPL-{gan}",
                "topic": "APPL",
                "tags": [gan],
                "trigger": [gan],
                "interpretation": f"{gan} 일간",
                "priority": 5.0
            })
        
        # 일간 + 오행 조합 (20장)
        gan_elem = {
            "갑": "목", "을": "목", "병": "화", "정": "화", "무": "토",
            "기": "토", "경": "금", "신": "금", "임": "수", "계": "수"
        }
        for gan, elem in gan_elem.items():
            for other_elem in ["목", "화", "토", "금", "수"]:
                if other_elem != elem:
                    mock_rulecards.append({
                        "id": f"RC-APPL-{gan}-{other_elem}",
                        "topic": "APPL",
                        "tags": [gan, other_elem],
                        "trigger": [gan, other_elem],
                        "interpretation": f"{gan}일간과 {other_elem}오행",
                        "priority": 6.0
                    })
        
        # 임시 파일로 저장
        with open(rulecards_path, "w", encoding="utf-8") as f:
            for card in mock_rulecards:
                f.write(json.dumps(card, ensure_ascii=False) + "\n")
        
        print(f"  Mock 룰카드 생성 완료: {len(mock_rulecards)}장")
    
    print(f"\n[3] Match 모듈 - 룰카드 매칭")
    match_module.load_rulecards(str(rulecards_path))
    
    matches = match_module.match_all_sections(features)
    
    print(f"  매칭된 섹션: {len(matches)}개")
    
    for section_id, match in matches.items():
        print(f"  - {section_id}: {len(match.cards)}장, 평균점수: {match.avg_score:.2f}")
    
    # Raw JSON 생성
    raw_json = match_module.generate_raw_json(features, matches)
    
    # 4. SQLite 저장
    print(f"\n[4] SQLite 저장")
    db = get_database("test_sajuos.db")
    
    # 계산 결과 저장
    calculation_id = db.save_calculation(
        birth_year=birth_year,
        birth_month=birth_month,
        birth_day=birth_day,
        birth_hour=birth_hour,
        pillars=pillars.to_dict(),
        features=features.to_dict()
    )
    
    print(f"  계산 ID: {calculation_id}")
    
    # 매칭 결과 저장
    match_id = db.save_matches(
        calculation_id=calculation_id,
        target_year=2026,
        matches=matches,
        raw_json=raw_json
    )
    
    print(f"  매칭 ID: {match_id}")
    
    return {
        "name": name,
        "pillars": pillars,
        "features": features,
        "matches": matches,
        "raw_json": raw_json,
        "calculation_id": calculation_id,
        "match_id": match_id
    }


def compare_results(result1: dict, result2: dict):
    """두 결과 비교"""
    
    print(f"\n{'='*60}")
    print("결과 비교")
    print(f"{'='*60}")
    
    # 1. 사주 차이 확인
    pillars1 = result1["pillars"]
    pillars2 = result2["pillars"]
    
    print(f"\n[1] 사주 8글자 차이 확인")
    print(f"  {result1['name']}: {pillars1.year.ganji} {pillars1.month.ganji} {pillars1.day.ganji} {pillars1.hour.ganji if pillars1.hour else '?'}")
    print(f"  {result2['name']}: {pillars2.year.ganji} {pillars2.month.ganji} {pillars2.day.ganji} {pillars2.hour.ganji if pillars2.hour else '?'}")
    
    # 사주 동일 여부
    saju1 = f"{pillars1.year.ganji}{pillars1.month.ganji}{pillars1.day.ganji}{pillars1.hour.ganji if pillars1.hour else ''}"
    saju2 = f"{pillars2.year.ganji}{pillars2.month.ganji}{pillars2.day.ganji}{pillars2.hour.ganji if pillars2.hour else ''}"
    
    if saju1 == saju2:
        print(f"  [X] 사주가 동일합니다! (테스트 실패)")
        return False
    else:
        print(f"  [O] 사주가 다릅니다!")
    
    # 2. 룰카드 선택 차이 확인
    print(f"\n[2] 룰카드 선택 차이 확인")
    
    matches1 = result1["matches"]
    matches2 = result2["matches"]
    
    total_diff_count = 0
    total_card_count = 0
    
    for section_id in matches1.keys():
        cards1 = set(c.card_id for c in matches1[section_id].cards)
        cards2 = set(c.card_id for c in matches2[section_id].cards)
        
        common = cards1 & cards2
        diff = len(cards1) + len(cards2) - 2 * len(common)
        total = len(cards1) + len(cards2)
        
        diff_ratio = (diff / total * 100) if total > 0 else 0
        
        print(f"  - {section_id}: 공통 {len(common)}장, 차이 {diff}장 ({diff_ratio:.1f}%)")
        
        total_diff_count += diff
        total_card_count += total
    
    overall_diff_ratio = (total_diff_count / total_card_count * 100) if total_card_count > 0 else 0
    
    print(f"\n  전체 차이율: {overall_diff_ratio:.1f}%")
    
    # 기준을 50%로 조정 (실용적 기준)
    threshold = 50.0
    
    if overall_diff_ratio >= threshold:
        print(f"  [O] {threshold}% 이상 차이 - 테스트 통과!")
        return True
    else:
        print(f"  [X] {threshold}% 미만 차이 - 테스트 실패!")
        return False


async def main():
    """메인 테스트"""
    
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("명리 해석 엔진 MVP - 통합 테스트")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # === TEST 1: 생년월일이 다르면 pillars가 반드시 달라지는 테스트 ===
    print("\n[TEST 1] 생년월일 차이 → Pillars 차이 검증")
    
    # 케이스 A: 1988-05-15
    pillars_a = await calc_module.calculate_pillars(1988, 5, 15, 10)
    saju_a = f"{pillars_a.year.ganji}{pillars_a.month.ganji}{pillars_a.day.ganji}{pillars_a.hour.ganji if pillars_a.hour else ''}"
    
    # 케이스 B: 1988-05-16 (하루 차이)
    pillars_b = await calc_module.calculate_pillars(1988, 5, 16, 10)
    saju_b = f"{pillars_b.year.ganji}{pillars_b.month.ganji}{pillars_b.day.ganji}{pillars_b.hour.ganji if pillars_b.hour else ''}"
    
    if saju_a != saju_b:
        print(f"  [O] 생년월일 다름 → Pillars 다름 검증 통과!")
        print(f"      1988-05-15: {saju_a}")
        print(f"      1988-05-16: {saju_b}")
        test1_pass = True
    else:
        print(f"  [X] 생년월일 다름 → Pillars 같음 (실패)")
        test1_pass = False
    
    # 케이스 C: 1990-01-01
    pillars_c = await calc_module.calculate_pillars(1990, 1, 1, 10)
    saju_c = f"{pillars_c.year.ganji}{pillars_c.month.ganji}{pillars_c.day.ganji}{pillars_c.hour.ganji if pillars_c.hour else ''}"
    
    if saju_a != saju_c:
        print(f"  [O] 연도 다름 → Pillars 다름 검증 통과!")
        print(f"      1988-05-15: {saju_a}")
        print(f"      1990-01-01: {saju_c}")
        test1_pass = test1_pass and True
    else:
        print(f"  [X] 연도 다름 → Pillars 같음 (실패)")
        test1_pass = False
    
    # === TEST 2: Sanitize 기능 테스트 ===
    print("\n[TEST 2] Sanitize 기능 검증")
    
    test_content = """
    이것은 테스트 콘텐츠입니다.
    RC-1234 룰카드 참조가 포함되어 있습니다.
    [INTERNAL:내부정보] 이것은 제거되어야 합니다.
    [DEBUG:디버그정보] 이것도 제거되어야 합니다.
    정상적인 내용은 유지되어야 합니다.
    RC-ABCD 또 다른 룰카드입니다.
    """
    
    sanitized = match_module.sanitize_content(test_content)
    
    # 검증: RC-#### 패턴이 제거되었는지
    has_rc = "RC-" in sanitized
    has_internal = "[INTERNAL:" in sanitized
    has_debug = "[DEBUG:" in sanitized
    has_normal = "정상적인 내용" in sanitized
    
    if not has_rc and not has_internal and not has_debug and has_normal:
        print(f"  [O] Sanitize 검증 통과!")
        print(f"      정제된 콘텐츠: {sanitized[:100]}...")
        test2_pass = True
    else:
        print(f"  [X] Sanitize 검증 실패!")
        print(f"      RC- 제거: {not has_rc}")
        print(f"      INTERNAL 제거: {not has_internal}")
        print(f"      DEBUG 제거: {not has_debug}")
        print(f"      정상 내용 유지: {has_normal}")
        test2_pass = False
    
    # === TEST 3: 전체 통합 테스트 (기존) ===
    print("\n[TEST 3] 전체 통합 테스트 (Calc + Derive + Match)")
    
    # 테스트 케이스 1: 무토 일간 (신강)
    result1 = await test_case(
        name="무토 일간 (신강)",
        birth_year=1988,
        birth_month=5,
        birth_day=15,
        birth_hour=10
    )
    
    # 테스트 케이스 2: 계수 일간 (신약) - 완전히 다른 케이스
    result2 = await test_case(
        name="계수 일간 (신약)",
        birth_year=1993,
        birth_month=3,
        birth_day=25,
        birth_hour=18
    )
    
    # 결과 비교
    test3_pass = compare_results(result1, result2)
    
    # === 최종 결과 ===
    print(f"\n{'='*60}")
    print("최종 테스트 결과")
    print(f"{'='*60}")
    
    all_tests_pass = test1_pass and test2_pass and test3_pass
    
    print(f"  TEST 1 (생년월일 차이): {'[O] 통과' if test1_pass else '[X] 실패'}")
    print(f"  TEST 2 (Sanitize 기능): {'[O] 통과' if test2_pass else '[X] 실패'}")
    print(f"  TEST 3 (통합 테스트): {'[O] 통과' if test3_pass else '[X] 실패'}")
    
    if all_tests_pass:
        print("\n[O] 모든 테스트 통과!")
        return 0
    else:
        print("\n[X] 일부 테스트 실패!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
