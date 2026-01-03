-- Auto-generated seed script for master_samples (persona x section) 

CREATE TABLE IF NOT EXISTS public.master_samples (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  persona_id text NOT NULL,
  section_id text NOT NULL,
  title text NOT NULL,
  body_markdown text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS master_samples_persona_section_uidx
  ON public.master_samples (persona_id, section_id);

TRUNCATE TABLE public.master_samples;

INSERT INTO public.master_samples (persona_id, section_id, title, body_markdown) VALUES
  
('missing', 'exec', $ms$🌦️ 전략 기상도$ms$, $ms$## {year} 🌦️ 전략 기상도

**[페르소나]** 결핍형 — system/authority 기반으로 수익 그릇을 만드는 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 올해는 '사람이 아니라 시스템'을 먼저 세우는 해다. 수익은 뒤에 따라온다.

### 왜 이런 결론이 나왔나 (근거 요약)
- {persona_reason}
- {top_cards}

### 올해의 우선순위 3개
1. {priority_1}
2. {priority_2}
3. {priority_3}

### 오늘 바로 할 3가지 (30분 컷)
- {today_1}
- {today_2}
- {today_3}
$ms$),
  ('missing', 'money', $ms$💰 현금흐름$ms$, $ms$## {year} 💰 현금흐름

**[페르소나]** 결핍형 — system/authority 기반으로 수익 그릇을 만드는 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 현금은 '관리'가 아니라 '강제 시스템'으로 안정화한다.

### 현금흐름 상태 (팩트 기반)
- {cashflow_snapshot}

### 누수 차단 체크리스트 (필수 7)
- [ ] {leak_1}
- [ ] {leak_2}
- [ ] {leak_3}
- [ ] {leak_4}
- [ ] {leak_5}
- [ ] {leak_6}
- [ ] {leak_7}

### SOP 액션 (실행 순서 고정)
1) **D+7**: {money_d7}
2) **D+14**: {money_d14}
3) **D+30**: {money_d30}
4) **D+60**: {money_d60}
$ms$),
  ('missing', 'business', $ms$📍 시장전략$ms$, $ms$## {year} 📍 시장전략

**[페르소나]** 결핍형 — system/authority 기반으로 수익 그릇을 만드는 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 박리다매 대신 '권위/전문성'으로 고단가를 만든다.

### 포지셔닝 한 줄
- {positioning_one_liner}

### 상품 전략 (3단 구조)
- Entry: {offer_entry}
- Core: {offer_core}
- Premium: {offer_premium}

### 채널 우선순위
1) {channel_1}
2) {channel_2}
3) {channel_3}

### 이번 달 실전 과제
- {biz_task_1}
- {biz_task_2}
- {biz_task_3}
$ms$),
  ('missing', 'team', $ms$🤝 파트너십$ms$, $ms$## {year} 🤝 파트너십

**[페르소나]** 결핍형 — system/authority 기반으로 수익 그릇을 만드는 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 직접 고생하지 말고 '계약+문서+지표'로 사람을 굴린다.

### 팀/외주 구조 추천
- {team_structure}

### R&R(역할/책임) 최소 세트
- {rr_1}
- {rr_2}
- {rr_3}

### 파트너십 리스크 2개 + 방지장치
1) {team_risk_1} → 방지: {team_guard_1}
2) {team_risk_2} → 방지: {team_guard_2}

### 다음 14일 액션
- {team_d14_1}
- {team_d14_2}
$ms$),
  ('missing', 'health', $ms$🧯 리스크 관리$ms$, $ms$## {year} 🧯 리스크 관리

**[페르소나]** 결핍형 — system/authority 기반으로 수익 그릇을 만드는 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 완벽주의가 실행을 멈춘다. '70% 런칭'이 리스크를 줄인다.

### 리스크 레이더 (팩트 기반 상위 3)
1) {risk_1}
2) {risk_2}
3) {risk_3}

### 방어 시스템 (체크포인트)
- {defense_1}
- {defense_2}
- {defense_3}

### 컨디션 관리 (오너 리스크)
- {health_rule_1}
- {health_rule_2}
- {health_rule_3}
$ms$),
  ('missing', 'calendar', $ms$🗓️ 12개월 캘린더$ms$, $ms$## {year} 🗓️ 12개월 캘린더

**[페르소나]** 결핍형 — system/authority 기반으로 수익 그릇을 만드는 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 상반기: 뼈대 구축 / 하반기: 운영·수익 가두기

### 분기별 목표
- 1분기: {q1_goal}
- 2분기: {q2_goal}
- 3분기: {q3_goal}
- 4분기: {q4_goal}

### 월별 체크포인트 (핵심 6개)
- {m1}
- {m2}
- {m3}
- {m4}
- {m5}
- {m6}
$ms$),
  ('missing', 'sprint', $ms$🚀 90일 액션플랜$ms$, $ms$## {year} 🚀 90일 액션플랜

**[페르소나]** 결핍형 — system/authority 기반으로 수익 그릇을 만드는 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 90일 안에 '수익 시스템' 1개를 실제로 돌려서 검증한다.

### 90일 로드맵 (고정)
- **D+7**: {d7}
- **D+14**: {d14}
- **D+30**: {d30}
- **D+60**: {d60}
- **D+90**: {d90}

### 성공 지표 (측정 가능한 3개)
- {kpi_1}
- {kpi_2}
- {kpi_3}
$ms$),
  ('overflow', 'exec', $ms$🌦️ 전략 기상도$ms$, $ms$## {year} 🌦️ 전략 기상도

**[페르소나]** 과다형 — 에너지/업무가 과도해 '가지치기'가 성과를 만드는 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 올해는 '확장'이 아니라 '집중'이다. 하나를 끝내면 돈이 남는다.

### 왜 이런 결론이 나왔나 (근거 요약)
- {persona_reason}
- {top_cards}

### 올해의 우선순위 3개
1. {priority_1}
2. {priority_2}
3. {priority_3}

### 오늘 바로 할 3가지 (30분 컷)
- {today_1}
- {today_2}
- {today_3}
$ms$),
  ('overflow', 'money', $ms$💰 현금흐름$ms$, $ms$## {year} 💰 현금흐름

**[페르소나]** 과다형 — 에너지/업무가 과도해 '가지치기'가 성과를 만드는 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 현금이 새는 구멍은 '자존심 비용'과 '충동 재투자'다.

### 현금흐름 상태 (팩트 기반)
- {cashflow_snapshot}

### 누수 차단 체크리스트 (필수 7)
- [ ] {leak_1}
- [ ] {leak_2}
- [ ] {leak_3}
- [ ] {leak_4}
- [ ] {leak_5}
- [ ] {leak_6}
- [ ] {leak_7}

### SOP 액션 (실행 순서 고정)
1) **D+7**: {money_d7}
2) **D+14**: {money_d14}
3) **D+30**: {money_d30}
4) **D+60**: {money_d60}
$ms$),
  ('overflow', 'business', $ms$📍 시장전략$ms$, $ms$## {year} 📍 시장전략

**[페르소나]** 과다형 — 에너지/업무가 과도해 '가지치기'가 성과를 만드는 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 포지션을 좁히면 전환율이 오른다. 메시지와 상품을 단일화한다.

### 포지셔닝 한 줄
- {positioning_one_liner}

### 상품 전략 (3단 구조)
- Entry: {offer_entry}
- Core: {offer_core}
- Premium: {offer_premium}

### 채널 우선순위
1) {channel_1}
2) {channel_2}
3) {channel_3}

### 이번 달 실전 과제
- {biz_task_1}
- {biz_task_2}
- {biz_task_3}
$ms$),
  ('overflow', 'team', $ms$🤝 파트너십$ms$, $ms$## {year} 🤝 파트너십

**[페르소나]** 과다형 — 에너지/업무가 과도해 '가지치기'가 성과를 만드는 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 리더가 병목이다. 권한 위임과 기준을 세우면 속도가 난다.

### 팀/외주 구조 추천
- {team_structure}

### R&R(역할/책임) 최소 세트
- {rr_1}
- {rr_2}
- {rr_3}

### 파트너십 리스크 2개 + 방지장치
1) {team_risk_1} → 방지: {team_guard_1}
2) {team_risk_2} → 방지: {team_guard_2}

### 다음 14일 액션
- {team_d14_1}
- {team_d14_2}
$ms$),
  ('overflow', 'health', $ms$🧯 리스크 관리$ms$, $ms$## {year} 🧯 리스크 관리

**[페르소나]** 과다형 — 에너지/업무가 과도해 '가지치기'가 성과를 만드는 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 번아웃이 가장 큰 적. 지속 가능한 텐션으로 운영해야 한다.

### 리스크 레이더 (팩트 기반 상위 3)
1) {risk_1}
2) {risk_2}
3) {risk_3}

### 방어 시스템 (체크포인트)
- {defense_1}
- {defense_2}
- {defense_3}

### 컨디션 관리 (오너 리스크)
- {health_rule_1}
- {health_rule_2}
- {health_rule_3}
$ms$),
  ('overflow', 'calendar', $ms$🗓️ 12개월 캘린더$ms$, $ms$## {year} 🗓️ 12개월 캘린더

**[페르소나]** 과다형 — 에너지/업무가 과도해 '가지치기'가 성과를 만드는 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 분기마다 '정리→집중→시스템화→수확'로 누수 방지

### 분기별 목표
- 1분기: {q1_goal}
- 2분기: {q2_goal}
- 3분기: {q3_goal}
- 4분기: {q4_goal}

### 월별 체크포인트 (핵심 6개)
- {m1}
- {m2}
- {m3}
- {m4}
- {m5}
- {m6}
$ms$),
  ('overflow', 'sprint', $ms$🚀 90일 액션플랜$ms$, $ms$## {year} 🚀 90일 액션플랜

**[페르소나]** 과다형 — 에너지/업무가 과도해 '가지치기'가 성과를 만드는 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 90일 동안 새로 시작 금지. '끝내기'로 순이익을 만든다.

### 90일 로드맵 (고정)
- **D+7**: {d7}
- **D+14**: {d14}
- **D+30**: {d30}
- **D+60**: {d60}
- **D+90**: {d90}

### 성공 지표 (측정 가능한 3개)
- {kpi_1}
- {kpi_2}
- {kpi_3}
$ms$),
  ('crisis', 'exec', $ms$🌦️ 전략 기상도$ms$, $ms$## {year} 🌦️ 전략 기상도

**[페르소나]** 위기형 — 외부 변수/리스크가 커서 '방어'가 곧 수익인 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 올해는 '공격'보다 '방어'가 이기는 해다. 현금·계약·평판을 지켜라.

### 왜 이런 결론이 나왔나 (근거 요약)
- {persona_reason}
- {top_cards}

### 올해의 우선순위 3개
1. {priority_1}
2. {priority_2}
3. {priority_3}

### 오늘 바로 할 3가지 (30분 컷)
- {today_1}
- {today_2}
- {today_3}
$ms$),
  ('crisis', 'money', $ms$💰 현금흐름$ms$, $ms$## {year} 💰 현금흐름

**[페르소나]** 위기형 — 외부 변수/리스크가 커서 '방어'가 곧 수익인 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 생존력 = 현금 유보율. 투자를 멈추고 회수를 최우선으로 둔다.

### 현금흐름 상태 (팩트 기반)
- {cashflow_snapshot}

### 누수 차단 체크리스트 (필수 7)
- [ ] {leak_1}
- [ ] {leak_2}
- [ ] {leak_3}
- [ ] {leak_4}
- [ ] {leak_5}
- [ ] {leak_6}
- [ ] {leak_7}

### SOP 액션 (실행 순서 고정)
1) **D+7**: {money_d7}
2) **D+14**: {money_d14}
3) **D+30**: {money_d30}
4) **D+60**: {money_d60}
$ms$),
  ('crisis', 'business', $ms$📍 시장전략$ms$, $ms$## {year} 📍 시장전략

**[페르소나]** 위기형 — 외부 변수/리스크가 커서 '방어'가 곧 수익인 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 대중확장 금지. 기존 고객 중심의 폐쇄형 모델로 안정성을 만든다.

### 포지셔닝 한 줄
- {positioning_one_liner}

### 상품 전략 (3단 구조)
- Entry: {offer_entry}
- Core: {offer_core}
- Premium: {offer_premium}

### 채널 우선순위
1) {channel_1}
2) {channel_2}
3) {channel_3}

### 이번 달 실전 과제
- {biz_task_1}
- {biz_task_2}
- {biz_task_3}
$ms$),
  ('crisis', 'team', $ms$🤝 파트너십$ms$, $ms$## {year} 🤝 파트너십

**[페르소나]** 위기형 — 외부 변수/리스크가 커서 '방어'가 곧 수익인 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 가까운 사람이 리스크가 된다. 구두를 없애고 문서로 통제한다.

### 팀/외주 구조 추천
- {team_structure}

### R&R(역할/책임) 최소 세트
- {rr_1}
- {rr_2}
- {rr_3}

### 파트너십 리스크 2개 + 방지장치
1) {team_risk_1} → 방지: {team_guard_1}
2) {team_risk_2} → 방지: {team_guard_2}

### 다음 14일 액션
- {team_d14_1}
- {team_d14_2}
$ms$),
  ('crisis', 'health', $ms$🧯 리스크 관리$ms$, $ms$## {year} 🧯 리스크 관리

**[페르소나]** 위기형 — 외부 변수/리스크가 커서 '방어'가 곧 수익인 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 법무/세무/평판 방어가 매출이다. 검증 시스템을 먼저 깐다.

### 리스크 레이더 (팩트 기반 상위 3)
1) {risk_1}
2) {risk_2}
3) {risk_3}

### 방어 시스템 (체크포인트)
- {defense_1}
- {defense_2}
- {defense_3}

### 컨디션 관리 (오너 리스크)
- {health_rule_1}
- {health_rule_2}
- {health_rule_3}
$ms$),
  ('crisis', 'calendar', $ms$🗓️ 12개월 캘린더$ms$, $ms$## {year} 🗓️ 12개월 캘린더

**[페르소나]** 위기형 — 외부 변수/리스크가 커서 '방어'가 곧 수익인 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 1H: 방어·잠행 / 2H: 위기대응·정리

### 분기별 목표
- 1분기: {q1_goal}
- 2분기: {q2_goal}
- 3분기: {q3_goal}
- 4분기: {q4_goal}

### 월별 체크포인트 (핵심 6개)
- {m1}
- {m2}
- {m3}
- {m4}
- {m5}
- {m6}
$ms$),
  ('crisis', 'sprint', $ms$🚀 90일 액션플랜$ms$, $ms$## {year} 🚀 90일 액션플랜

**[페르소나]** 위기형 — 외부 변수/리스크가 커서 '방어'가 곧 수익인 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 90일 목표는 성장보다 '순이익 방어'와 '현금 확보'다.

### 90일 로드맵 (고정)
- **D+7**: {d7}
- **D+14**: {d14}
- **D+30**: {d30}
- **D+60**: {d60}
- **D+90**: {d90}

### 성공 지표 (측정 가능한 3개)
- {kpi_1}
- {kpi_2}
- {kpi_3}
$ms$),
  ('standard', 'exec', $ms$🌦️ 전략 기상도$ms$, $ms$## {year} 🌦️ 전략 기상도

**[페르소나]** 정석형 — 조화/추진력이 좋아 '스케일업'이 가능한 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 올해는 '스케일업'의 해다. 프리미엄 포지션을 고정하고 확장하라.

### 왜 이런 결론이 나왔나 (근거 요약)
- {persona_reason}
- {top_cards}

### 올해의 우선순위 3개
1. {priority_1}
2. {priority_2}
3. {priority_3}

### 오늘 바로 할 3가지 (30분 컷)
- {today_1}
- {today_2}
- {today_3}
$ms$),
  ('standard', 'money', $ms$💰 현금흐름$ms$, $ms$## {year} 💰 현금흐름

**[페르소나]** 정석형 — 조화/추진력이 좋아 '스케일업'이 가능한 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 초과 이익을 '자산화'하는 속도가 복리의 차이를 만든다.

### 현금흐름 상태 (팩트 기반)
- {cashflow_snapshot}

### 누수 차단 체크리스트 (필수 7)
- [ ] {leak_1}
- [ ] {leak_2}
- [ ] {leak_3}
- [ ] {leak_4}
- [ ] {leak_5}
- [ ] {leak_6}
- [ ] {leak_7}

### SOP 액션 (실행 순서 고정)
1) **D+7**: {money_d7}
2) **D+14**: {money_d14}
3) **D+30**: {money_d30}
4) **D+60**: {money_d60}
$ms$),
  ('standard', 'business', $ms$📍 시장전략$ms$, $ms$## {year} 📍 시장전략

**[페르소나]** 정석형 — 조화/추진력이 좋아 '스케일업'이 가능한 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 가치 경쟁으로 시장을 리드한다. 프리미엄 지배력을 강화한다.

### 포지셔닝 한 줄
- {positioning_one_liner}

### 상품 전략 (3단 구조)
- Entry: {offer_entry}
- Core: {offer_core}
- Premium: {offer_premium}

### 채널 우선순위
1) {channel_1}
2) {channel_2}
3) {channel_3}

### 이번 달 실전 과제
- {biz_task_1}
- {biz_task_2}
- {biz_task_3}
$ms$),
  ('standard', 'team', $ms$🤝 파트너십$ms$, $ms$## {year} 🤝 파트너십

**[페르소나]** 정석형 — 조화/추진력이 좋아 '스케일업'이 가능한 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 인재가 모이는 흐름. C-Level/파트너 구조로 스케일을 준비한다.

### 팀/외주 구조 추천
- {team_structure}

### R&R(역할/책임) 최소 세트
- {rr_1}
- {rr_2}
- {rr_3}

### 파트너십 리스크 2개 + 방지장치
1) {team_risk_1} → 방지: {team_guard_1}
2) {team_risk_2} → 방지: {team_guard_2}

### 다음 14일 액션
- {team_d14_1}
- {team_d14_2}
$ms$),
  ('standard', 'health', $ms$🧯 리스크 관리$ms$, $ms$## {year} 🧯 리스크 관리

**[페르소나]** 정석형 — 조화/추진력이 좋아 '스케일업'이 가능한 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 성장기일수록 관료화가 위험. 레드팀으로 민첩성을 유지한다.

### 리스크 레이더 (팩트 기반 상위 3)
1) {risk_1}
2) {risk_2}
3) {risk_3}

### 방어 시스템 (체크포인트)
- {defense_1}
- {defense_2}
- {defense_3}

### 컨디션 관리 (오너 리스크)
- {health_rule_1}
- {health_rule_2}
- {health_rule_3}
$ms$),
  ('standard', 'calendar', $ms$🗓️ 12개월 캘린더$ms$, $ms$## {year} 🗓️ 12개월 캘린더

**[페르소나]** 정석형 — 조화/추진력이 좋아 '스케일업'이 가능한 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 계단식 성장. 분기마다 한 단계 점프

### 분기별 목표
- 1분기: {q1_goal}
- 2분기: {q2_goal}
- 3분기: {q3_goal}
- 4분기: {q4_goal}

### 월별 체크포인트 (핵심 6개)
- {m1}
- {m2}
- {m3}
- {m4}
- {m5}
- {m6}
$ms$),
  ('standard', 'sprint', $ms$🚀 90일 액션플랜$ms$, $ms$## {year} 🚀 90일 액션플랜

**[페르소나]** 정석형 — 조화/추진력이 좋아 '스케일업'이 가능한 타입

**[팩트 앵커]**
{truth_anchor}
**[엔진 결론]** 90일 안에 시장 점유율을 수치로 증명한다.

### 90일 로드맵 (고정)
- **D+7**: {d7}
- **D+14**: {d14}
- **D+30**: {d30}
- **D+60**: {d60}
- **D+90**: {d90}

### 성공 지표 (측정 가능한 3개)
- {kpi_1}
- {kpi_2}
- {kpi_3}
$ms$)
;
