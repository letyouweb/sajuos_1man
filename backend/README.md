# 🔮 사주 AI 서비스

한국 전통 사주 명리학을 AI로 해석하는 서비스입니다.

## 📋 주요 기능

### `/api/v1/calculate` - 사주 계산
- 양력 생년월일 → 사주 원국 (년/월/일/시주) 계산
- 절기 기준 보정
- 대운 정보 제공

### `/api/v1/interpret` - AI 해석
- GPT 기반 사주 해석
- 고민 유형별 특화 분석 (연애/재물/직장/건강/학업/종합)
- 구조화된 JSON 응답

## 🚀 빠른 시작

### 1. 환경 설정

```bash
cd backend

# 가상환경 생성 (권장)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정

```bash
# .env 파일 생성
copy .env.example .env  # Windows
# cp .env.example .env  # Linux/Mac

# .env 파일 편집
# OPENAI_API_KEY=sk-your-key-here
# KASI_API_KEY=your-kasi-key-here (선택)
```

### 3. 서버 실행

```bash
# 개발 모드 (자동 리로드)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 또는 직접 실행
python -m app.main
```

### 4. API 문서 확인

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 📡 API 사용 예시

### 사주 계산

```bash
curl -X POST http://localhost:8000/api/v1/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "birth_year": 1996,
    "birth_month": 5,
    "birth_day": 20,
    "birth_hour": 14,
    "gender": "female"
  }'
```

**응답:**
```json
{
  "success": true,
  "birth_info": "1996년 5월 20일 14시",
  "saju": {
    "year_pillar": {"gan": "병", "ji": "자", "ganji": "병자", ...},
    "month_pillar": {"gan": "계", "ji": "사", "ganji": "계사", ...},
    "day_pillar": {"gan": "무", "ji": "인", "ganji": "무인", ...},
    "hour_pillar": {...}
  },
  "day_master": "무",
  "day_master_element": "토",
  "day_master_description": "큰 산(戊土) - 안정적이고 묵직한 기운",
  "is_boundary_date": false
}
```

### 사주 해석

```bash
curl -X POST http://localhost:8000/api/v1/interpret \
  -H "Content-Type: application/json" \
  -d '{
    "year_pillar": "병자",
    "month_pillar": "계사",
    "day_pillar": "무인",
    "name": "홍길동",
    "gender": "female",
    "concern_type": "love",
    "question": "2026년에 결혼할 수 있을까요?"
  }'
```

**응답:**
```json
{
  "success": true,
  "summary": "2026년 결혼 가능성 높음",
  "day_master_analysis": "무토(戊土) 일간은 안정적이고...",
  "strengths": ["진실된 마음", "책임감"],
  "risks": ["고집", "변화 거부"],
  "answer": "2026년은 관성이 들어와...",
  "action_plan": ["적극적인 만남 시도", "자기 계발", "열린 마음 유지"],
  "lucky_periods": ["2026년 봄", "2026년 가을"],
  "blessing": "홍길동님의 사랑이 이루어지길 바랍니다 🌸",
  "disclaimer": "본 해석은 오락/참고 목적으로 제공됩니다."
}
```

## 🧪 테스트

```bash
# 전체 테스트
pytest tests/ -v

# 특정 테스트
pytest tests/test_calculate.py -v
pytest tests/test_interpret.py -v
```

## 📁 프로젝트 구조

```
backend/
├── app/
│   ├── main.py              # FastAPI 앱
│   ├── config.py            # 설정
│   ├── routers/
│   │   ├── calculate.py     # /calculate 엔드포인트
│   │   └── interpret.py     # /interpret 엔드포인트
│   ├── services/
│   │   ├── saju_engine.py   # 만세력 계산 엔진
│   │   ├── kasi_api.py      # 한국천문연구원 API
│   │   ├── gpt_interpreter.py # GPT 해석
│   │   └── cache.py         # 캐시 서비스
│   ├── models/
│   │   └── schemas.py       # Pydantic 스키마
│   └── rules/
│       └── interpretation_rules.py  # 해석 룰셋
├── tests/
│   ├── test_calculate.py
│   ├── test_interpret.py
│   └── test_data.json       # 테스트 데이터
├── requirements.txt
├── .env.example
└── README.md
```

## 💰 비용 추정

GPT-4o-mini 기준 (2024년):
- 입력: $0.15 / 1M tokens
- 출력: $0.60 / 1M tokens

**예상 비용 (건당):**
- 입력 ~1,500 토큰 + 출력 ~1,000 토큰
- 약 **1~2원/건** (환율 1,400원 기준)

## ⚠️ 면책 조항

본 서비스는 **오락/참고 목적**으로 제공되며, 의학/법률/투자 등 전문적 조언을 대체하지 않습니다.

## 🔧 추가 설정 (선택)

### 한국천문연구원 API (KASI)

더 정확한 간지 계산을 위해 공공데이터포털에서 API 키 발급:
1. https://www.data.go.kr 접속
2. "음양력 정보" 검색
3. API 키 발급 후 `.env`에 설정

### Redis 캐시 (프로덕션)

대규모 서비스 시 Redis 연동 권장 (현재는 메모리 캐시)

## 📜 라이선스

MIT License
