# SajuOS V1.0 하이브리드 엔진 - 빠른 시작 가이드

## 🚀 서버 실행

```bash
cd C:\Users\mongshilymom\dev\sajuos\backend
python -m uvicorn app.main:app --reload --port 8000
```

서버 시작 시 로그 확인:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 SajuOS V1.0 하이브리드 엔진 가동 시작
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ RuleCards 로드 완료: 총 100장
📊 토픽별 분포:
   - ELEMENTS: 20장
   - TEN_GODS: 25장
   ...

✅ Match 모듈에 RuleCards 주입 완료
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Startup 완료 - SajuOS V1.0 준비 완료
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🔍 디버그 엔드포인트 테스트

### 1. 브라우저에서 직접 테스트
```
http://localhost:8000/api/v1/debug/engine?birth_year=1988&birth_month=5&birth_day=15&birth_hour=10
```

### 2. curl로 테스트
```bash
curl "http://localhost:8000/api/v1/debug/engine?birth_year=1988&birth_month=5&birth_day=15&birth_hour=10&target_year=2026"
```

### 3. 응답 예시
```json
{
  "pillars": {
    "year": {"ganji": "무진", "gan": "무", "ji": "진"},
    "month": {"ganji": "정사", "gan": "정", "ji": "사"},
    "day": {"ganji": "무인", "gan": "무", "ji": "인"},
    "hour": {"ganji": "정사", "gan": "정", "ji": "사"}
  },
  "derived": {
    "day_master": "무",
    "day_master_element": "토",
    "structure": "신강",
    "dominant_ten_god": "식신",
    ...
  },
  "match_summary": {
    "ELEM": {
      "count": 8,
      "top_cards": [
        {"card_id": "RC-ELEM-COMBO-0", "score": 13.20},
        ...
      ],
      "avg_score": 12.95
    },
    ...
  },
  "raw_json": {
    "matched_rule_ids": ["RC-ELEM-COMBO-0", ...],
    "match_scores": {"RC-ELEM-COMBO-0": 13.20, ...},
    "fired_triggers": {"RC-ELEM-COMBO-0": ["화", "목화"], ...}
  },
  "rulecard_status": {
    "loaded": true,
    "total_cards": 100,
    "by_topic": {"ELEMENTS": 20, "TEN_GODS": 25, ...}
  },
  "validation": {
    "pillars_valid": true,
    "matches_valid": true,
    "scores_valid": true,
    "all_checks_passed": true
  }
}
```

---

## 🧪 통합 테스트 실행

```bash
cd C:\Users\mongshilymom\dev\sajuos\backend
python test_engine_integration_v2.py
```

**기대 출력**:
```
======================================================================
>>> SajuOS V1.0 Hybrid Engine Integration Test
======================================================================

>>> TEST CASE 1: 1988-05-15 10:00
   Year : 무진(戊辰)
   Month: 정사(丁巳)
   Day  : 무인(戊寅)
   Hour : 정사(丁巳)
   
   Total Sections: 5
   - ELEM: 8 cards, avg_score: 12.95
   - TEN: 7 cards, avg_score: 14.38
   ...

>>> TEST CASE 2: 1990-12-25 14:00
   Year : 경오(庚午)
   Month: 무자(戊子)
   Day  : 병술(丙戌)
   Hour : 정미(丁未)
   
   Total Sections: 5
   - ELEM: 8 cards, avg_score: 12.96
   - TEN: 8 cards, avg_score: 14.27
   ...

>>> Final Verification Summary
   1. Pillars different      : [PASS]
   2. Cards non-zero         : [PASS]
   3. Raw JSON complete      : [PASS]
   4. Cards differ per case  : [PASS]

======================================================================
*** ALL TESTS PASSED - SajuOS V1.0 Hybrid Engine Working ***
======================================================================
```

---

## 📊 핵심 엔드포인트

### 1. Health Check
```bash
GET http://localhost:8000/health
```

### 2. Ready Check
```bash
GET http://localhost:8000/ready
```
응답:
```json
{
  "status": "ready",
  "checks": {
    "rulecards": true,
    "rulecards_count": 100,
    "openai": true,
    "supabase": true
  }
}
```

### 3. Debug Engine
```bash
GET http://localhost:8000/api/v1/debug/engine?birth_year=YYYY&birth_month=MM&birth_day=DD&birth_hour=HH&target_year=2026
```

### 4. Calculate Saju
```bash
POST http://localhost:8000/api/v1/calculate
```
Body:
```json
{
  "birth_year": 1988,
  "birth_month": 5,
  "birth_day": 15,
  "birth_hour": 10,
  "birth_minute": 0
}
```

---

## 🔧 트러블슈팅

### 1. 룰카드 로드 실패
**증상**: "RuleCards 파일을 찾을 수 없습니다" 경고

**해결**:
1. 룰카드 파일이 다음 경로 중 하나에 있는지 확인:
   - `C:\Users\mongshilymom\dev\sajuos\backend\data\rulecards.jsonl`
   - `C:\Users\mongshilymom\dev\sajuos\backend\temp_rulecards.jsonl`

2. 파일이 없으면 생성:
```bash
# 샘플 룰카드 파일 생성
echo '{"id":"RC-SAMPLE-1","topic":"ELEMENTS","tags":["토","화"],"priority":5,"trigger":["토","화"],"interpretation":"샘플 해석"}' > data/rulecards.jsonl
```

### 2. Match 모듈 에러
**증상**: "룰카드가 로드되지 않았습니다" 에러

**해결**:
- 서버 재시작
- 디버그 엔드포인트는 자동으로 룰카드 로드 시도

### 3. Supabase 연결 실패
**증상**: Supabase 관련 에러

**해결**:
1. `.env` 파일 확인:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

2. 환경 변수 설정 확인:
```bash
echo $env:SUPABASE_URL
echo $env:SUPABASE_SERVICE_ROLE_KEY
```

---

## 📁 주요 파일 위치

```
backend/
├── app/
│   ├── main.py                    # 메인 앱 (Startup 로그)
│   ├── routers/
│   │   ├── debug.py              # 디버그 엔드포인트
│   │   ├── calculate.py          # 사주 계산 엔드포인트
│   │   └── reports.py            # 리포트 생성 엔드포인트
│   └── services/
│       ├── engine_v2.py          # 사주 계산 엔진 (KASI + ephem)
│       ├── calc_module.py        # Calc 모듈
│       ├── derive_module.py      # Derive 모듈
│       ├── match_module.py       # Match 모듈 (스코어링)
│       ├── rulecards_store.py    # 룰카드 로더 (tags 자동 생성)
│       ├── supabase_service.py   # Supabase 저장
│       └── report_worker.py      # 리포트 워커
├── data/
│   └── rulecards.jsonl           # 룰카드 데이터
├── test_engine_integration_v2.py # 통합 테스트
└── COMPLETION_REPORT.md          # 완료 보고서
```

---

## 🎯 다음 단계

1. **프론트엔드 연동**:
   - 디버그 엔드포인트 호출
   - pillars, derived, match_summary 표시

2. **리포트 생성 테스트**:
   - 2개의 다른 입력으로 리포트 생성
   - Supabase에 저장된 content 확인

3. **성능 측정**:
   - 룰카드 로드 시간
   - Match 스코어링 시간
   - 리포트 생성 시간

---

## 📞 지원

문제 발생 시:
1. 서버 로그 확인 (콘솔 출력)
2. `test_engine_integration_v2.py` 실행하여 시스템 상태 확인
3. `COMPLETION_REPORT.md` 참조

---

**버전**: SajuOS V1.0  
**마지막 업데이트**: 2024-12-29
