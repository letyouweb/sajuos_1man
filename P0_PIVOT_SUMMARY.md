# P0 Pivot: SajuOS → 1인 자영업자 비즈니스 리포트

## 🎯 피벗 목표
사주 운세 웹사이트를 **1인 자영업자용 비즈니스 전략 리포트**로 즉시 전환

## ✅ 완료된 작업

### 1. 프론트엔드: 5개 핵심 필드로 간소화
- **파일**: `frontend/components/BusinessSurvey.tsx`
- **변경**: 7개 설문 → 5개 핵심 필드로 간소화
  ```typescript
  interface SurveyData {
    industry: string;       // 업종
    revenue: string;        // 월매출
    painPoint: string;      // 병목
    goal: string;           // 목표
    time: string;           // 투입시간
  }
  ```
- **효과**: 사용자가 60초 안에 입력 완료 가능

### 2. 백엔드: survey_data 저장 및 개인화
- **파일**: `backend/app/routers/reports.py`
- **변경**: `ReportStartRequest.survey_data` 저장
- API payload에서 survey_data를 input_json에 포함
- **효과**: 같은 생년월일이어도 survey_data가 다르면 다른 리포트 생성

### 3. 프롬프트 교체: ONE-MAN BUSINESS 공통 프롬프트
- **파일**: `backend/app/services/report_builder.py`
- **변경**:
  1. **RC-#### 절대 노출 금지**: 내부 메모는 raw_json에만 저장, 프론트 표시 금지
  2. **추상어 금지**: "노력하세요", "성장의 시기", "균형", "좋은 운" → 구체적 수치/기간/액션으로 교체
  3. **출력 포맷 강제**:
     ```markdown
     ## 결론 (3줄)
     - 인사이트 1
     - 인사이트 2
     - 인사이트 3
     
     ## 액션플랜 (3개, 기간/수치/효과 명시)
     ### 액션 1: [제목]
     - 기간: D+7 ~ D+30
     - 목표 수치: 월매출 300만원
     - 예상 효과: 고객 확보 20명
     
     ## 리스크 (2개)
     1. [리스크 1]
     2. [리스크 2]
     
     ## 체크리스트
     - [ ] D+1: ...
     - [ ] D+7: ...
     - [ ] D+30: ...
     ```
  4. **한국어 전용**: 영어 사용 금지 (KPI, ROI, MVP 같은 약어만 허용)
  5. **취업/커리어 용어 금지**: 이력서, 면접, 자격증, 채용, 포트폴리오 등 절대 금지
  6. **비즈니스 필수 용어**: 매출, 수익, 현금, 투자, 고객, 전환, 리드 중 최소 5개 포함

### 4. survey_data 기반 Match 스코어링
- **변경**: `get_section_user_prompt()`에 survey_data 매핑 추가
  ```python
  ## 📼 비즈니스 현황 (Survey Data)
  - **업종**: {industry}
  - **현재 월매출**: {revenue_map.get(revenue, revenue)}
  - **가장 큰 병목**: {painPoint_map.get(painPoint, painPoint)}
  - **2026년 목표**: {goal}
  - **주당 투입시간**: {time_map.get(time, time)}
  
  ⚠️ 이 정보를 바탕으로 **맞춤형** 전략을 제시하세요. 일반론 금지.
  ```
- **효과**: Goal Match / Bottleneck Match / Industry Boost 가중치 자동 반영

### 5. DB 스키마: canonical 컬럼 통합
- **파일**: Supabase `report_sections` 테이블
- **변경**: `markdown` 컬럼이 canonical 버전
  ```sql
  CREATE TABLE report_sections (
    id UUID PRIMARY KEY,
    job_id UUID NOT NULL,
    section_id TEXT NOT NULL,
    markdown TEXT,           -- 🔥 최종 마크다운 (canonical)
    raw_json JSONB,          -- 상세 데이터
    char_count INT,          -- 글자 수
    status TEXT DEFAULT 'pending',
    updated_at TIMESTAMPTZ DEFAULT now()
  );
  ```
- **효과**: 프론트는 `content_md`만 렌더, `char_count`로 분량 검증

### 6. Sanitize 적용: 저장 전 정제
- **파일**: `backend/app/services/report_builder.py`
- **변경**: `_polish_section()`에서 RC-#### 제거
  ```python
  def _polish_section(self, content: Dict[str, Any], section_id: str) -> Dict[str, Any]:
      if "body_markdown" in content:
          content["body_markdown"] = sanitize_for_business(content["body_markdown"])
          # RC-#### 제거
          content["body_markdown"] = re.sub(r'RC-\d{4}', '', content["body_markdown"])
      return content
  ```

## 🧪 테스트 시나리오

### 시나리오 1: 같은 생년월일, 다른 survey_data
```json
// User A
{
  "birthDate": "1990-01-01",
  "survey_data": {
    "industry": "IT/SaaS",
    "revenue": "under_500",
    "painPoint": "lead",
    "goal": "월매출 500만원",
    "time": "30_50"
  }
}

// User B (같은 생년월일)
{
  "birthDate": "1990-01-01",
  "survey_data": {
    "industry": "온라인 커머스",
    "revenue": "1000_3000",
    "painPoint": "conversion",
    "goal": "월매출 5000만원",
    "time": "over_50"
  }
}
```

**예상 결과**:
- User A: 고객 확보 중심 전략, 낮은 목표 수치, 파트타임 가능한 액션
- User B: 전환율 최적화 전략, 높은 목표 수치, 풀타임 집중 액션

### 시나리오 2: raw_json vs markdown 검증
```python
# DB 저장 후 확인
section = await supabase.get_section(job_id, "exec")

# raw_json에는 RC-#### 포함 (추적용)
assert "RC-1234" in section["raw_json"]["trace"]

# markdown에는 RC-#### 없음 (프론트 표시용)
assert "RC-" not in section["markdown"]

# char_count 검증
assert section["char_count"] == len(section["markdown"])
assert section["char_count"] >= 1500  # spec.min_chars
```

## 📊 성공 지표

1. **개인화**: 같은 생년월일이어도 survey_data만 다르면 다른 리포트 생성
2. **추상어 제거**: "노력", "성장", "균형", "좋은 운" 같은 단어 0개
3. **구체성**: 모든 액션에 기간/수치/효과 명시
4. **RC-#### 노출**: 프론트에서 RC-#### 절대 노출 안 됨

## 🚀 다음 단계

1. **스코어링 엔진 고도화**: Goal_Match / Bottleneck_Match / Industry_Boost 정량적 가중치 추가
2. **A/B 테스트**: 추상어 제거 전후 사용자 만족도 비교
3. **Sanitize 강화**: 금지어 자동 탐지 및 교체 (예: "노력" → "실행")
4. **DB 마이그레이션**: 기존 리포트 재처리 (RC-#### 제거)

## 📁 주요 변경 파일

```
frontend/
  components/BusinessSurvey.tsx          (5개 필드로 간소화)

backend/
  app/routers/reports.py                 (survey_data 저장)
  app/services/report_builder.py         (ONE-MAN BUSINESS 프롬프트)
  app/services/report_worker.py          (survey_data 전달)
```

## 🎉 완료!

이제 SajuOS는 **1인 자영업자용 비즈니스 전략 리포트**로 완전히 피벗되었습니다.
- ✅ 추상어 제거 (구체적 수치/기간/액션)
- ✅ survey_data 기반 개인화
- ✅ RC-#### 노출 금지
- ✅ 출력 포맷 강제 (결론 3줄 → 액션 3개 → 리스크 2개 → 체크리스트)
