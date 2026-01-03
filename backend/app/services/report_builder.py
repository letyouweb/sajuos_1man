"""
report_builder.py
Premium section generator:
- 🔥🔥🔥 마스터 샘플 템플릿 기반 (빈칸 채우기 방식)
- Uses selected RuleCards
- Injects dynamic Truth Anchor to prevent hallucinations
- 🔥 P0: LLM 거절 응답 감지 시 1회 자동 재시도
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.services.truth_anchor import build_truth_anchor
from app.services.persona_classifier import classify_persona, get_persona_description
from app.services.supabase_service import supabase_service

logger = logging.getLogger(__name__)


# -----------------------------
# Section specs
# -----------------------------

@dataclass(frozen=True)
class SectionSpec:
    section_id: str
    title: str
    min_chars: int = 800


# Keep aligned with UI tabs / MasterSamples keys
PREMIUM_SECTIONS: Dict[str, SectionSpec] = {
    "business": SectionSpec("business", "사업/전략 기상도", 900),
    "money": SectionSpec("money", "현금흐름", 900),
    "team": SectionSpec("team", "파트너십/팀", 800),
    "health": SectionSpec("health", "오너 리스크", 700),
    "calendar": SectionSpec("calendar", "12개월 캘린더", 800),
    "sprint": SectionSpec("sprint", "12개월 스프린트", 900),
    "exec": SectionSpec("exec", "90일 실행 플랜", 900),
}

# -----------------------------
# 🔥 P0: 거절 패턴 감지
# -----------------------------

REJECTION_PATTERNS = [
    "죄송",
    "추가 정보",
    "추가정보",
    "작성할 수 없",
    "작성이 어렵",
    "제공된 정보를 바탕으로",
    "분석할 수 없",
    "분석이 어렵",
    "정보가 부족",
    "더 많은 정보",
    "구체적인 정보",
]


def _detect_rejection(text: str) -> Tuple[bool, List[str]]:
    """LLM 응답에서 거절 패턴 감지"""
    if not text:
        return True, ["empty_response"]
    
    found = []
    for pattern in REJECTION_PATTERNS:
        if pattern in text:
            found.append(pattern)
    
    return len(found) > 0, found


# -----------------------------
# 🔥🔥🔥 호칭 처리 함수 (귀하 → {name}님)
# -----------------------------

def apply_name_style(body: str, user_name: str) -> str:
    """
    호칭 치환: 귀하 → {name}님
    
    - user_name이 있으면: 귀하 → {name}님으로 치환
    - user_name이 없으면: 귀하 그대로 유지
    """
    if not user_name or not body:
        return body
    
    # 조사별 치환 (순서 중요: 긴 패턴 먼저)
    replacements = [
        ("귀하의", f"{user_name}님의"),
        ("귀하께서", f"{user_name}님께서"),
        ("귀하에게", f"{user_name}님에게"),
        ("귀하가", f"{user_name}님이"),
        ("귀하는", f"{user_name}님은"),
        ("귀하를", f"{user_name}님을"),
        ("귀하", f"{user_name}님"),
    ]
    
    result = body
    for old, new in replacements:
        result = result.replace(old, new)
    
    return result


def ensure_addressee(body: str, user_name: str) -> str:
    """
    호칭 강제 삽입 안전장치
    
    - body에 user_name이나 '님'이 전혀 없으면 첫 문장 앞에 호칭 추가
    - user_name이 없으면 그대로 반환 (귀하 유지)
    """
    if not body:
        return body
    
    # user_name이 없으면 귀하가 있는지 확인하고 없으면 추가
    if not user_name:
        if "귀하" not in body and "님" not in body:
            # 첫 문단 앞에 귀하 추가
            return f"귀하, {body}"
        return body
    
    # user_name이 있는 경우
    if user_name in body or "님" in body:
        return body
    
    # 호칭이 전혀 없으면 첫 문단 앞에 주입
    return f"{user_name}님, {body}"


def postprocess_body(body: str, user_name: str) -> str:
    """
    본문 후처리: 호칭 치환 + 강제 삽입
    """
    body = apply_name_style(body, user_name)
    body = ensure_addressee(body, user_name)
    return body


# -----------------------------
# 🔥 호칭 관련 프롬프트 규칙
# -----------------------------

def get_addressee_rule(user_name: str) -> str:
    """
    호칭 사용 규칙 (프롬프트용)
    
    - user_name이 있으면: {name}님 사용 강제
    - user_name이 없으면: 귀하 사용 허용
    """
    if user_name:
        return f"""## 🎯 호칭 규칙 (필수)
- 반드시 "{user_name}님" 또는 "{user_name}님의" 형태로 호칭한다.
- "귀하" 사용 금지.
- 섹션 첫 문단에 반드시 "{user_name}님"을 1회 이상 포함한다.
- 예: "{user_name}님의 원국은...", "{user_name}님께서는..."
"""
    else:
        return """## 🎯 호칭 규칙
- "귀하" 또는 "귀하의" 형태로 호칭한다.
- 섹션 첫 문단에 반드시 호칭을 1회 이상 포함한다.
- 예: "귀하의 원국은...", "귀하께서는..."
"""


def _generate_fallback_content(
    section_id: str,
    title: str,
    saju_data: Dict[str, Any],
    survey_data: Dict[str, Any],
    target_year: int,
) -> str:
    """
    🔥 P0: 재시도 후에도 거절 시 사용하는 Fallback 템플릿
    - 사과/거절 문구 없음
    - 최소 600자 이상
    - 일반적인 비즈니스 전략 제시
    """
    industry = survey_data.get("industry", "비즈니스")
    goal = survey_data.get("goal", "성장")
    day_master = saju_data.get("day_master", "")
    
    # 섹션별 Fallback 템플릿
    fallback_templates = {
        "exec": f"""## {target_year}년 90일 실행 플랜

### 1단계: 기반 구축 (1-30일)
- 현재 운영 프로세스 점검 및 개선점 파악
- 핵심 성과 지표(KPI) 설정 및 측정 체계 구축
- 팀/파트너 역할 재정의 및 커뮤니케이션 채널 정비

### 2단계: 성장 가속 (31-60일)
- 마케팅 채널 다각화 및 신규 고객 확보 전략 실행
- 기존 고객 관리 강화 및 재구매율 향상 활동
- 운영 효율화를 위한 자동화 도구 도입 검토

### 3단계: 안정화 (61-90일)
- 성과 측정 및 데이터 기반 의사결정 체계 정착
- 다음 분기 전략 수립 및 리소스 재배분
- 팀 역량 강화 및 지속 성장 기반 마련

💡 **확인 사항**: 현재 가장 시급한 과제와 가용 리소스를 검토 후 우선순위를 조정하시기 바랍니다.""",

        "money": f"""## {target_year}년 현금흐름 최적화 전략

### 수익 구조 분석
현재 {industry} 분야에서의 수익 구조를 점검하고, 다음 영역에서 개선 기회를 탐색합니다:

1. **매출 다각화**: 기존 제품/서비스 외 신규 수익원 발굴
2. **가격 전략 최적화**: 고객 가치 기반 가격 재설정 검토
3. **비용 구조 개선**: 고정비 대비 변동비 비율 최적화

### 현금흐름 관리 포인트
- 매출채권 회수 주기 단축 (목표: 30일 이내)
- 재고/원가 관리 효율화
- 계절성/시기별 현금흐름 변동 대비 운전자금 확보

### 실행 액션
1. 월별 현금흐름 예측표 작성
2. 주요 비용 항목 분석 및 절감 기회 파악
3. 긴급 자금 확보 옵션 사전 준비

💡 **확인 사항**: 현재 평균 매출채권 회수 기간과 주요 비용 구조를 확인하시기 바랍니다.""",

        "business": f"""## {target_year}년 비즈니스 전략 기상도

### 시장 환경 분석
{industry} 분야에서 {target_year}년 주목해야 할 트렌드와 기회 요인을 검토합니다.

### 핵심 전략 방향
1. **차별화 강화**: 경쟁사 대비 명확한 가치 제안 정립
2. **고객 경험 개선**: 구매 여정 전반의 만족도 향상
3. **운영 효율화**: 핵심 업무 집중 및 비핵심 업무 외주/자동화

### 분기별 중점 과제
- Q1: 기반 구축 및 전략 정교화
- Q2: 성장 동력 확보
- Q3: 확장 및 안정화
- Q4: 성과 점검 및 차년도 준비

💡 **확인 사항**: 현재 가장 큰 성장 저해 요인이 무엇인지 검토하시기 바랍니다.""",
    }
    
    # 기본 템플릿
    default_template = f"""## {target_year}년 {title}

### 현황 분석
{industry} 분야에서 {goal}을 위한 전략적 접근이 필요합니다.

### 핵심 실행 방안
1. **현재 상태 점검**: 강점과 개선 필요 영역 파악
2. **목표 설정**: 측정 가능한 단기/중기 목표 수립
3. **실행 계획**: 구체적인 액션 아이템과 일정 수립
4. **모니터링**: 주기적인 성과 측정 및 조정

### 다음 단계
- 현재 가장 시급한 과제 우선순위 결정
- 가용 리소스(시간/예산/인력) 점검
- 30일 단위 마일스톤 설정

💡 **확인 사항**: 현재 상황에 맞는 구체적인 실행 계획 수립을 위해 추가 정보가 필요합니다."""

    return fallback_templates.get(section_id, default_template)


# -----------------------------
# Prompt rules (P0) - 🔥 톤 변경: "실패" → "대체 출력"
# -----------------------------

ENGINE_HEADLINE = "첫 문장 = ENGINE_HEADLINE. 수정/부정/희석 금지."

ROOT_CAUSE_RULE = """## 🧠 Root Cause Rule (핵심 원칙)
1) 결론(원인)은 반드시 '사주/룰카드'에서 시작한다. 설문은 '증상'이다.
2) 설문(industry/painPoint/goal/time)은 "현장에서 어떻게 드러났는지" 설명에만 사용한다.
3) 금지: "고객님이 설문에서 ~라고 하셔서"를 원인으로 확정하는 서술.
4) 정답 패턴: "원국/룰카드 구조(원인) 때문에 {industry} 현장에서 {painPoint}로 발현(증상)"
5) 첫 문장 = ENGINE_HEADLINE. 수정/부정/희석 금지.
"""

# 🔥 P0 FIX: "위반시 실패" 제거, "대체 출력" 방식으로 변경
DATA_COMPLIANCE_RULE = """## 📋 데이터 준수 규칙 (출력 지속)
1) saju_summary에 없는 오행/십성을 "있다"고 단정하지 마라. → 없으면 "(미확인)" 표기 후 계속 작성.
2) is_missing_jaesung=true면 정재/편재 "있다" 금지 → "현금흐름 보완 전략"으로 대체 서술.
3) is_missing_shiksang=true면 식신/상관 "있다" 금지 → "마케팅/표현력 강화 방안"으로 대체 서술.
4) 모르는 격국은 "(격국 미확인)" 표기 후 일반 전략으로 계속 작성.
5) 지장간/숨은 십성 추론 금지 → 확인된 데이터만 사용.

⚠️ 중요: 입력이 비어도 작성은 반드시 진행한다.
- 불확실한 부분은 '가정' 또는 '(확인 필요)'로 표기
- 2~3개 확인 질문은 본문 맨 끝에만 추가 (사과/거절 금지)
"""

# 🔥 P0: 재시도용 강화 프롬프트 (거절 방지)
NO_REJECTION_RULE = """## 🚫 절대 금지 (사과/거절 금지)
- "죄송합니다", "추가 정보가 필요합니다", "작성할 수 없습니다" 등 거절 문구 절대 금지.
- 정보가 부족해도 반드시 실행 가능한 플랜을 작성한다.
- 불확실한 부분은 "[가정]" 또는 "[확인 필요]"로 표기하고 계속 작성.
- 본문은 최소 800자 이상, 실행 액션 3~7개 포함 필수.
- 질문이 있으면 본문 맨 끝 "💡 확인 사항" 섹션에만 2~3개 추가.
"""


class _SafeDict(dict):
    def __missing__(self, key):
        return "미입력"


def _safe_format(template: str, vars: Dict[str, Any]) -> str:
    if not template:
        return ""
    try:
        out = template.format_map(_SafeDict(vars))
    except Exception:
        out = template
    out = re.sub(r"\{[a-zA-Z0-9_]+\}", "미입력", out)
    return out


# -----------------------------
# Master sample loader (🔥 Supabase 기반)
# -----------------------------

async def get_master_sample_from_db(section_id: str, persona_id: str = "standard") -> Dict[str, Any]:
    """
    🔥 마스터 샘플 조회 (Supabase)
    - persona 매칭 → standard 폴백
    """
    try:
        sample = await supabase_service.get_master_sample(persona_id, section_id)
        if sample:
            return sample
    except Exception as e:
        logger.warning(f"[Builder] 마스터샘플 조회 실패: {e}")
    
    return {"title": "", "body_markdown": ""}


def get_master_body_markdown(section_id: str) -> str:
    """Optional: loads master sample markdown. If unavailable, returns empty."""
    # 🔥 Deprecated: 동기 버전 (하위 호환)
    try:
        from app.templates.master_samples.index import get_master_sample  # type: ignore
        sample = get_master_sample(section_id)
        return sample.get("body_markdown") or sample.get("markdown") or ""
    except Exception:
        return ""


# -----------------------------
# System prompt builder (🔥 마스터 샘플 템플릿 채우기 방식)
# -----------------------------

def build_system_prompt(
    section_id: str,
    saju_data: Dict[str, Any],
    rulecards: List[Dict[str, Any]],
    survey_data: Dict[str, Any],
    target_year: int,
    user_question: str = "",
    existing_contents: Optional[List[str]] = None,
    truth_anchor_override: Optional[str] = None,
    is_retry: bool = False,
    master_template: str = "",
    persona_id: str = "standard",
    user_name: str = "",  # 🔥 호칭 처리용
) -> str:
    spec = PREMIUM_SECTIONS.get(section_id) or SectionSpec(section_id, section_id, 800)
    title = spec.title
    min_chars = spec.min_chars
    
    # 🔥 마스터 템플릿이 없으면 기존 방식
    master_body = master_template or get_master_body_markdown(section_id)
    
    # 🔥🔥🔥 호칭 규칙 (user_name 유무에 따라 다름)
    addressee_rule = get_addressee_rule(user_name)

    # dynamic truth anchor
    if truth_anchor_override:
        truth_anchor = truth_anchor_override
    else:
        truth_anchor = build_truth_anchor(
            saju_data=saju_data,
            target_year=target_year,
            section_id=section_id,
        )

    # compact rulecards text (top 8)
    cards_text = []
    for i, c in enumerate(rulecards[:8]):
        cards_text.append(
            f"[{i+1}] topic={c.get('topic','')}\n"
            f"- interpretation: {c.get('interpretation','')}\n"
            f"- action: {c.get('action','')}\n"
        )
    cards_block = "\n".join(cards_text).strip()

    # survey facts (비어도 OK)
    industry = survey_data.get("industry") or "(미입력 - 일반 비즈니스로 가정)"
    pain = user_question or survey_data.get("painPoint") or "(미입력 - 성장/수익 개선으로 가정)"
    goal = survey_data.get("goal") or "(미입력 - 안정적 성장으로 가정)"
    timeframe = survey_data.get("time") or "(미입력 - 12개월로 가정)"

    # ground truth summary json
    summary = saju_data.get("saju_summary") or {}
    summary_json = json.dumps(summary, ensure_ascii=False, indent=2)

    existing = "\n\n".join(existing_contents or [])
    if existing:
        existing = f"## 기존 생성 내용(중복 금지 참고)\n{existing}\n"

    # 🔥 재시도 시 강화 프롬프트 추가
    retry_block = NO_REJECTION_RULE if is_retry else ""
    
    # 🔥🔥🔥 마스터 샘플 기반 프롬프트 (템플릿 채우기 방식)
    if master_body:
        return f"""{truth_anchor}

{addressee_rule}

## 🔥🔥🔥 핵심 원칙: 템플릿 빈칸 채우기 (구조 유지)
1) 아래 [마스터 템플릿]의 **구조와 헤더를 그대로 유지**한다.
2) {{변수명}} 형태의 빈칸을 [팩트 앵커]와 [룰카드]의 정보로 채운다.
3) 문장은 자연스럽게 다듬되, **새로운 사실을 추가로 생성하지 않는다.**
4) [팩트 앵커]나 [룰카드]에 없는 사주 용어 사용 금지.
5) 템플릿의 섹션 순서, 제목, 구조를 **절대 변경하지 않는다.**

{retry_block}

## Ground Truth saju_summary (정답지)
{summary_json}

## 사용자 비즈니스 정보
- 업종: {industry}
- 고민/질문: {pain}
- 목표: {goal}
- 기간: {timeframe}
- 페르소나: {persona_id} ({get_persona_description(persona_id)})
- 사용자명: {user_name or "(미입력 - 귀하 사용)"}

## 엔진 확정 룰카드 (근거로만 사용)
{cards_block}

## [마스터 템플릿] - 이 구조를 유지하며 빈칸만 채워라
---
{master_body}
---

{existing}

## 작성 지시
- 섹션: [{title}] (section_id={section_id})
- 반드시 {min_chars}자 이상
- **템플릿 구조 유지 필수**: 헤더, 섹션 순서 변경 금지
- **추가 사실 생성 금지**: 팩트 앵커/룰카드에 없는 내용 금지
- **사주 용어 제한**: 팩트 앵커에 명시된 용어만 사용
- 금지: 사과, 거절, '추가 정보 필요', '분석할 수 없음'
""".strip()
    
    # 🔥 마스터 템플릿 없을 때 기존 방식
    return f"""{truth_anchor}

{addressee_rule}

{ROOT_CAUSE_RULE}

{DATA_COMPLIANCE_RULE}

{retry_block}

## Ground Truth saju_summary (정답지)
{summary_json}

## 사용자 비즈니스 정보
- 업종: {industry}
- 고민/질문: {pain}
- 목표: {goal}
- 기간: {timeframe}
- 사용자명: {user_name or "(미입력 - 귀하 사용)"}

## 엔진 확정 룰카드 (근거로만 사용)
{cards_block}

{existing}

## 작성 지시
- 섹션: [{title}] (section_id={section_id})
- 반드시 {min_chars}자 이상
- 루프: (원국/룰카드 구조) → (현장 발현) → (실행 액션 3~7개)
- 금지: 사과, 거절, '추가 정보 필요', '분석할 수 없음'
- 허용: 불확실한 부분 "[가정]" 표기 후 계속 작성
""".strip()


# -----------------------------
# Builder class
# -----------------------------

class PremiumReportBuilder:
    def __init__(
        self,
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1600,
        timeout: float = 60.0,
    ):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.temperature = float(temperature)
        self.max_tokens = int(max_tokens)
        self.timeout = float(timeout)

    async def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY") or ""
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is missing")

        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {"Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            return (data["choices"][0]["message"]["content"] or "").strip()

    async def generate_single_section(
        self,
        section_id: str,
        saju_data: Dict[str, Any],
        rulecards: List[Dict[str, Any]],
        survey_data: Dict[str, Any],
        target_year: int,
        user_question: str = "",
        existing_contents: Optional[List[str]] = None,
        job_id: Optional[str] = None,
        truth_anchor: Optional[str] = None,
        persona_id: Optional[str] = None,
        user_name: str = "",  # 🔥 호칭 처리용
    ) -> Dict[str, Any]:
        """
        섹션 생성 + 🔥 마스터 샘플 기반 + 거절 응답 감지 시 1회 자동 재시도
        """
        spec = PREMIUM_SECTIONS.get(section_id) or SectionSpec(section_id, section_id, 800)
        user_prompt = f"{ENGINE_HEADLINE}\n섹션 [{section_id}] 내용을 작성하라."
        
        # 🔥 페르소나 분류
        if not persona_id:
            persona_id = classify_persona(saju_data)
        
        # 🔥 마스터 샘플 조회 (Supabase)
        master_sample = await get_master_sample_from_db(section_id, persona_id)
        master_template = master_sample.get("body_markdown", "")
        
        logger.info(f"[Builder] 섹션 생성 시작: {section_id} | persona={persona_id} | user={user_name or '귀하'} | template={len(master_template)}자")
        
        body = ""
        retried = False
        rejection_detected = False
        rejection_patterns = []
        
        # 🔥 최대 2회 시도 (최초 1회 + 재시도 1회)
        for attempt in range(2):
            is_retry = (attempt > 0)
            
            system_prompt = build_system_prompt(
                section_id=section_id,
                saju_data=saju_data,
                rulecards=rulecards,
                survey_data=survey_data,
                target_year=target_year,
                user_question=user_question,
                existing_contents=existing_contents,
                truth_anchor_override=truth_anchor,
                is_retry=is_retry,
                master_template=master_template,
                persona_id=persona_id,
                user_name=user_name,  # 🔥 호칭 처리 전달
            )
            
            try:
                body = await self._call_openai(system_prompt, user_prompt)
            except Exception as e:
                logger.error(f"[Builder] OpenAI 호출 실패 (attempt={attempt+1}): {e}")
                body = f"[섹션 생성 오류: {str(e)[:100]}]"
                break
            
            # 🔥 거절 패턴 감지
            is_rejection, patterns = _detect_rejection(body)
            
            if is_rejection and attempt == 0:
                logger.warning(f"[Builder] 거절 응답 감지 (section={section_id}, attempt=1, matched_patterns={patterns}) → 재시도")
                retried = True
                rejection_detected = True
                rejection_patterns = patterns
                continue
            elif is_rejection and attempt == 1:
                logger.error(f"[Builder] 재시도 후에도 거절 (section={section_id}, attempt=2, matched_patterns={patterns}) → Fallback 사용")
                rejection_detected = True
                rejection_patterns = patterns
                body = _generate_fallback_content(section_id, spec.title, saju_data, survey_data, target_year)
                break
            else:
                if is_retry:
                    logger.info(f"[Builder] ✅ 재시도 성공 (section={section_id})")
                break

        # 🔥🔥🔥 호칭 후처리: 귀하 → {name}님 치환 + 강제 삽입
        body = postprocess_body(body, user_name)

        used_ids = [c.get("id") for c in rulecards if c.get("id")]

        return {
            "section_id": section_id,
            "title": spec.title,
            "body_markdown": body,
            "char_count": len(body),
            "llm_response_len": len(body),
            "guardrail_violations": rejection_patterns if rejection_detected else [],
            "repaired": retried,
            "rejection_detected": rejection_detected,
            "fallback_used": rejection_detected and retried,
            "persona_id": persona_id,
            "user_name": user_name or "귀하",  # 🔥 사용된 호칭
            "master_template_used": bool(master_template),
            "match_summary": {
                "selected_rulecards": len(rulecards),
                "model": self.model,
                "job_id": job_id,
                "retried": retried,
                "persona": persona_id,
                "user_name": user_name or "귀하",
            },
            "used_rulecard_ids": used_ids[:50],
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    async def regenerate_single_section(self, *args, **kwargs) -> Dict[str, Any]:
        """Alias for retry logic (외부 호출용)"""
        return await self.generate_single_section(*args, **kwargs)


# Public singleton used across routers/workers
premium_report_builder = PremiumReportBuilder()

__all__ = [
    "PREMIUM_SECTIONS",
    "SectionSpec",
    "PremiumReportBuilder",
    "premium_report_builder",
    "build_system_prompt",
]
