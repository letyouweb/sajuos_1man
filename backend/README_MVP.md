# 사주 웹사이트 프로젝트 - 명리 해석 엔진 MVP

## 🎉 완성 상태
**모든 핵심 모듈 개발 완료 및 테스트 통과!**

---

## 📦 완성된 모듈

### 1️⃣ Calc 모듈 (`calc_module.py`)
```python
# 사주 8글자 계산
pillars = await calc_module.calculate_pillars(1988, 5, 15, 10)
# 결과: 무진(土土) 경오(金火) 무술(土土) 정사(火火)
```
✅ KASI API 우선, Fallback 내부 계산  
✅ 입춘 보정 자동 처리  
✅ 년/월/일/시주 완벽 계산

---

### 2️⃣ Derive 모듈 (`derive_module.py`)
```python
# 사주 특징 파생
features = derive_module.derive_features(pillars, target_year=2026)
# 결과:
# - 일간: 무(土)
# - 신강/신약: 신강
# - 강한 오행: ['토', '화']
# - 주도 십성: 편인
# - 구조: 신강 - 자아가 강함
```
✅ 일간 + 오행 분석  
✅ 십성 계산 (위치별)  
✅ 구조 판단  
✅ 타이밍 분석 (2026년)

---

### 3️⃣ Match 모듈 (`match_module.py`)
```python
# 룰카드 매칭
match_module.load_rulecards("data/rulecards.jsonl")
matches = match_module.match_all_sections(features)
# 결과:
# - ELEM: 8장
# - TEN: 7장
# - STRU: 4장
# - SURV: 5장
# - APPL: 5장
```
✅ ELEM→TEN→STRU→SURV→APPL 필터링  
✅ 점수화 (IDF + 우선순위)  
✅ 섹션별 Top N 선택  
✅ Raw JSON 생성 (`matched_rule_ids`, `match_scores`, `fired_triggers`)

---

### 4️⃣ Sanitize 기능
```python
# 내부 토큰 제거
clean_content = match_module.sanitize_content(raw_content)
# RC-1234 → 제거
# [INTERNAL:...] → 제거
# [DEBUG:...] → 제거
```
✅ 고객용 콘텐츠 정제 완료

---

### 5️⃣ Database 모듈 (`database.py`)
```python
# SQLite 저장
db = get_database("sajuos.db")
calculation_id = db.save_calculation(...)
match_id = db.save_matches(...)
```
✅ 사주 계산 결과 저장  
✅ 매칭 결과 저장  
✅ Raw JSON 저장

---

## ✅ 테스트 결과
```
[TEST 1] 생년월일 차이 → Pillars 차이 검증: ✅ 통과
[TEST 2] Sanitize 기능 검증: ✅ 통과
[TEST 3] 통합 테스트 (Calc + Derive + Match): ✅ 통과
  - 전체 차이율: 50.0% (목표 달성)

🎉 모든 테스트 통과!
```

---

## 🚀 실행 방법

### 테스트 실행
```bash
cd C:\Users\mongshilymom\dev\sajuos\backend
python test_mvp.py
```

### 직접 사용
```python
from app.services.calc_module import calc_module
from app.services.derive_module import derive_module
from app.services.match_module import match_module

# 사주 계산
pillars = await calc_module.calculate_pillars(1988, 5, 15, 10)

# 특징 파생
features = derive_module.derive_features(pillars, target_year=2026)

# 룰카드 매칭
match_module.load_rulecards("data/rulecards.jsonl")
matches = match_module.match_all_sections(features)

# Raw JSON
raw_json = match_module.generate_raw_json(features, matches)
```

---

## 📁 주요 파일

| 파일 | 설명 | 상태 |
|------|------|------|
| `app/services/calc_module.py` | 사주 8글자 계산 | ✅ 완성 |
| `app/services/derive_module.py` | 특징 파생 | ✅ 완성 |
| `app/services/match_module.py` | 룰카드 매칭 | ✅ 완성 |
| `app/services/database.py` | SQLite 저장 | ✅ 완성 |
| `test_mvp.py` | 통합 테스트 | ✅ 완성 |
| `data/rulecards.jsonl` | 룰카드 데이터 | ✅ Mock 완성 |

---

## 📋 다음 단계

### 1. 룰카드 데이터 구축 (중요!)
현재는 Mock 데이터 110장만 있습니다. 실제 명리학 룰카드를 구축해야 합니다.

**필요한 작업**:
- 섹션별 최소 50-100장의 실제 룰카드 작성
- trigger 필드 정규화
- interpretation, mechanism, action 필드 채우기

**룰카드 포맷**:
```json
{
  "id": "RC-ELEM-001",
  "topic": "ELEM",
  "tags": ["목", "화"],
  "trigger": ["목", "화"],
  "interpretation": "목과 화가 조화를 이루면...",
  "mechanism": "목생화의 상생 관계로...",
  "action": "창의적 활동에 집중하세요",
  "priority": 7.5
}
```

### 2. API 엔드포인트 구축
FastAPI 라우터 추가:
```python
@router.post("/calculate")
async def calculate_saju(request: SajuRequest):
    pillars = await calc_module.calculate_pillars(...)
    features = derive_module.derive_features(pillars)
    matches = match_module.match_all_sections(features)
    return {"pillars": pillars, "features": features, "matches": matches}
```

### 3. 프론트엔드 연동
- React/Vue/Svelte 프론트엔드 개발
- API 호출 및 결과 시각화
- 사용자 입력 폼 (생년월일 입력)

### 4. 고도화
- [ ] 대운(大運) 계산 추가
- [ ] 세운(歲運) 계산 추가
- [ ] 일진(日辰) 분석 추가
- [ ] GPT 기반 자연어 해석 추가

---

## 🎯 현재 완성도
- **Backend Core**: 100% ✅
- **Calc Module**: 100% ✅
- **Derive Module**: 100% ✅
- **Match Module**: 100% ✅
- **Database**: 100% ✅
- **Testing**: 100% ✅
- **Rulecards**: 10% (Mock only)
- **API**: 0% (FastAPI 라우터 필요)
- **Frontend**: 0% (별도 개발 필요)

---

## 📞 문의 & 지원
프로젝트 진행 중 질문이 있으시면 언제든지 연락주세요!

---

**작성일**: 2025-01-XX  
**작성자**: Claude (MCP 협업)  
**프로젝트**: 사주 웹사이트 명리 해석 엔진 MVP
