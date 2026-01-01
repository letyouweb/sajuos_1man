"""P0 Patch: gpt_interpreter.py - saju_summary 주입"""

with open('app/services/gpt_interpreter.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1) _build_prompt 끝부분에 saju_summary 추가
old_prompt = '''        return f"""[User Info]
- Gender: {gender_text}
- Concern: {concern_text}
- Question: {question}

[Saju]
- Year: {year_p}
- Month: {month_p}
- Day: {day_p}
- Hour: {hour_p}

[Day Master]
- Stem: {day_master}
- Element: {day_master_elem}

Analyze and respond in JSON format."""'''

new_prompt = '''        # 🔥 P0: saju_summary 정답지 추출
        saju_summary = saju_data.get("saju_summary", {})
        summary_json = json.dumps(saju_summary, ensure_ascii=False, indent=2) if saju_summary else "{}"
        
        return f"""[User Info]
- Gender: {gender_text}
- Concern: {concern_text}
- Question: {question}

[Saju]
- Year: {year_p}
- Month: {month_p}
- Day: {day_p}
- Hour: {hour_p}

[Day Master]
- Stem: {day_master}
- Element: {day_master_elem}

[🔴 Ground Truth saju_summary - 이 데이터가 정답이다]
{summary_json}

[환각 방지 규칙]
1. 위 saju_summary에 없는 십성/오행을 "있다"고 주장하지 마라.
2. is_missing_shiksang=true면, 식상/상관이 "있다"고 말하지 마라.
3. is_missing_jaesung=true면, 재성이 "있다"고 말하지 마라.
4. allowed_structure_names 외의 격국 이름을 사용하지 마라.

Analyze and respond in JSON format."""'''

if old_prompt in content:
    content = content.replace(old_prompt, new_prompt)
    print("Added saju_summary to _build_prompt")
else:
    print("Could not find target _build_prompt block")

# 2) 저장
with open('app/services/gpt_interpreter.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done!")
