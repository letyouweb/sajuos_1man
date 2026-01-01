"""P0 Patch: interpretation_rules.py - 환각 방지 철칙 추가"""

with open('app/rules/interpretation_rules.py', 'r', encoding='utf-8') as f:
    content = f.read()

# BASE_SYSTEM_PROMPT 맨 앞에 환각 방지 철칙 추가
old_start = '''BASE_SYSTEM_PROMPT = """당신은 사주OS 프리미엄 컨설팅 시스템입니다.
50년 경력 명리학 마스터 + 맥킨지급 비즈니스 전략가의 융합 지능을 보유합니다.'''

new_start = '''BASE_SYSTEM_PROMPT = """당신은 사주OS 프리미엄 컨설팅 시스템입니다.
50년 경력 명리학 마스터 + 맥킨지급 비즈니스 전략가의 융합 지능을 보유합니다.

## 🚨 환각 방지 철칙 (최우선 준수)
다음 규칙을 어기면 분석이 무효 처리됩니다:

1. **원국에 없는 것은 없다**: saju_summary의 elements_count / ten_gods_count가 0인 오행/십성은 "있다"고 말하지 마라.
2. **재성 언급 조건**: is_missing_jaesung=true면, 정재/편재가 "있다"고 말하지 마라. 대운/세운에서 들어온다면 반드시 "대운에서 ~가 들어온다"로 명시하라.
3. **식상 언급 조건**: is_missing_shiksang=true면, 식신/상관이 "있다"고 말하지 마라.
4. **격국 이름 제한**: allowed_structure_names에 있는 이름만 사용하라. (건록격, 양인격, 식신격, 상관격, 편재격, 정재격, 편관격, 정관격, 편인격, 정인격, 종격, 화격, 외격)
5. **primary_structure 준수**: 사주 분석에서 격국을 언급할 때 primary_structure 값을 우선 사용하라.
6. **추론 금지**: 지장간 분석 등으로 "숨은 십성"을 추론해서 "있다"고 우기지 마라. 명시적으로 saju_summary에 있는 것만 언급하라.
'''

if old_start in content:
    content = content.replace(old_start, new_start)
    print("Added 환각 방지 철칙 to BASE_SYSTEM_PROMPT")
else:
    print("Could not find target BASE_SYSTEM_PROMPT start")

# 저장
with open('app/rules/interpretation_rules.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done!")
