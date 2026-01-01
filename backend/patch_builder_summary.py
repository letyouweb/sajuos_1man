"""P0 Patch: report_builder.py - saju_summary 주입 + temperature 조정"""
import re

with open('app/services/report_builder.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1) import json 추가 (없으면)
if 'import json' not in content:
    content = content.replace(
        'import logging',
        'import json\nimport logging'
    )
    print("Added import json")

# 2) fact_ctx 앞에 saju_summary 블록 추가
old_block = '''    existing_block = ""
    if existing_contents:
        existing_block = f"\\n## 이전 섹션 (반복 금지)\\n{chr(10).join(existing_contents[-2:])}\\n"
    
    # 🔥 P0: 원국 팩트 체크 블록 추가
    fact_ctx = build_fact_check_context(saju_data or {})'''

new_block = '''    existing_block = ""
    if existing_contents:
        existing_block = f"\\n## 이전 섹션 (반복 금지)\\n{chr(10).join(existing_contents[-2:])}\\n"
    
    # 🔥 P0: saju_summary 정답지 추출
    saju_summary = (saju_data or {}).get("saju_summary", {})
    summary_json = json.dumps(saju_summary, ensure_ascii=False, indent=2) if saju_summary else "{}"
    
    # 🔥 P0: 데이터 준수 철칙 블록
    data_compliance_rule = f"""
## 🔴 데이터 준수 철칙 (위반시 실패)
1. 아래 원국 통계(정답지)에 없는 십성/오행을 "있다"고 주장하지 마라.
2. 원국에 재성(정재/편재)이 0개면, "재성이 있다"고 말하지 마라.
3. 원국에 식상(식신/상관)이 0개면, "식상이 있다"고 말하지 마라.
4. 대운에서 들어오는 기운은 반드시 "대운에서 ~가 들어온다"로 명시하라.
5. allowed_structure_names 외의 격국 이름을 사용하지 마라.

## 원국 통계(정답지) - Ground Truth
{summary_json}
"""
    
    # 🔥 P0: 원국 팩트 체크 블록 추가
    fact_ctx = build_fact_check_context(saju_data or {})'''

if old_block in content:
    content = content.replace(old_block, new_block)
    print("Added saju_summary block")
else:
    print("Could not find target block for saju_summary")

# 3) return 문에 data_compliance_rule 추가
old_return = '''{ROOT_CAUSE_RULE}
{fact_ctx}

## 첫 문장 (수정 금지)'''

new_return = '''{ROOT_CAUSE_RULE}
{data_compliance_rule}
{fact_ctx}

## 첫 문장 (수정 금지)'''

if old_return in content:
    content = content.replace(old_return, new_return)
    print("Added data_compliance_rule to prompt")
else:
    print("Could not find target return for data_compliance_rule")

# 4) temperature 조정 (0.7 -> 0.3)
content = re.sub(r'temperature\s*=\s*0\.7', 'temperature=0.3', content)
print("Adjusted temperature to 0.3")

# 5) 저장
with open('app/services/report_builder.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done!")
