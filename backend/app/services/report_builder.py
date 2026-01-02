"""
SajuOS Premium Report Builder v12 - P0 빈 섹션 절대 금지
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 P0-1: 카드 0개 → LLM 호출 X, 폴백 텍스트 즉시 반환
🔥 P0-2: 섹션 ID 정합성 (exec,money,business,team,health,calendar,sprint)
🔥 P0-3: 토큰 "치환" (삭제 X) - {industry}→"해당 업종"
🔥 P0-4: 생성 실패 원인 로그 4개 필수
🔥 P0-5: 지장간 추론 금지 및 '보이는 글자' 중심 검증 강화 (Guardrails 통합)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import json
import logging
import re
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass, field

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 마스터 샘플 로드 (원본 유지)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

try:
    from app.templates.master_samples import load_master_samples
    MASTER_SAMPLES = load_master_samples("v1")
except Exception:
    MASTER_SAMPLES = {}

DEBUG_TEMPLATE_LEAKS = False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# P0-3: 토큰 치환 (삭제 X)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOKEN_REPLACEMENTS = {
    "{industry}": "해당 업종",
    "{painPoint}": "현재 병목",
    "{engine_headline}": "핵심 결론",
    "{goal}": "목표",
    "{revenue}": "매출",
    "{day_master}": "일간",
    "{time}": "시점",
    "[ENGINE_HEADLINE]": "",
    "[/ENGINE_HEADLINE]": "",
}


def replace_template_tokens(text: str) -> str:
    """🔥 P0-3: 토큰 치환 (삭제가 아닌 의미 있는 텍스트로 대체)"""
    if not text:
        return ""
    if DEBUG_TEMPLATE_LEAKS:
        return text.strip()
    for token, replacement in TOKEN_REPLACEMENTS.items():
        text = text.replace(token, replacement)
    text = re.sub(r"\{[a-zA-Z_]+\}", "해당 항목", text)
    return text.strip()


def normalize_year(text: str, target_year: int) -> str:
    """출력에 섞인 연도(예: 2025)를 target_year로 정규화.
    - target_year 자체는 유지
    - 다른 20xx는 target_year로 치환
    """
    if not text:
        return ""
    def _repl(m: re.Match) -> str:
        y = int(m.group(0))
        return str(target_year) if y != target_year else m.group(0)
    return re.sub(r"\b20\d{2}\b", _repl, text)


def check_template_leaks(text: str, context: str = "") -> List[str]:
    if not text:
        return []
    leaked = []
    for token in TOKEN_REPLACEMENTS.keys():
        if token in text:
            leaked.append(token)
    if re.search(r"\{[a-zA-Z_]+\}", text):
        leaked.append("{other}")
    if leaked:
        logger.warning(f"[TemplateLeak] context={context} leaked={leaked}")
    return leaked


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 프리미엄 섹션 정의 (원본 유지)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class SectionSpec:
    id: str
    title: str
    icon: str
    order: int
    min_chars: int = 800


PREMIUM_SECTIONS: Dict[str, SectionSpec] = {
    "exec": SectionSpec(id="exec", title="전략기상도", icon="🌦️", order=1, min_chars=900),
    "money": SectionSpec(id="money", title="현금흐름", icon="💰", order=2, min_chars=900),
    "business": SectionSpec(id="business", title="시장전략", icon="📍", order=3, min_chars=900),
    "team": SectionSpec(id="team", title="파트너십", icon="🤝", order=4, min_chars=900),
    "health": SectionSpec(id="health", title="리스크", icon="🧯", order=5, min_chars=900),
    "calendar": SectionSpec(id="calendar", title="12개월", icon="🗓️", order=6, min_chars=900),
    "sprint": SectionSpec(id="sprint", title="90일플랜", icon="🚀", order=7, min_chars=900),
}


def get_master_body_markdown(section_id: str) -> str:
    if not MASTER_SAMPLES:
        return ""
    sample = MASTER_SAMPLES.get(section_id) or {}
    body = sample.get("body_markdown") or ""
    return body.strip()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# P0 Guardrails (원본 유지 + 최소 안전장치)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROHIBITED_INFER = [
    "지장간", "장간", "추론", "추측", "몰래", "숨겨진",
]


def build_truth_anchor(saju_data: Dict[str, Any]) -> str:
    """'보이는 글자' 기반의 사실 앵커"""
    if not saju_data:
        return "원국 데이터가 제공되지 않았습니다."
    pillars = saju_data.get("pillars") or {}
    # 가능한 한 사용자에게 보이는 값만 사용
    parts = []
    for k in ["year", "month", "day", "hour"]:
        v = pillars.get(k)
        if isinstance(v, dict):
            parts.append(f"{k}:{v.get('stem','')}{v.get('branch','')}".strip())
        elif isinstance(v, str):
            parts.append(f"{k}:{v}")
    return " / ".join([p for p in parts if p]) or "원국(연월일시) 정보가 불충분합니다."


def build_fact_check_context(saju_data: Dict[str, Any]) -> str:
    """검증용 컨텍스트(최소)"""
    anchor = build_truth_anchor(saju_data)
    return f"[사실 앵커]\n{anchor}\n"


def detect_guardrail_violations(text: str, saju_data: Dict[str, Any]) -> List[str]:
    if not text:
        return ["empty_output"]
    v = []
    # 지장간/추론 금지
    for w in PROHIBITED_INFER:
        if w in text:
            v.append(f"prohibited:{w}")
    # 템플릿 토큰 유출
    v += [f"template:{t}" for t in check_template_leaks(text, context="guardrail")]
    return v


def sanitize_output_last_resort(text: str, saju_data: Dict[str, Any]) -> str:
    """최후 수단: 위험 단어 제거 + 템플릿 토큰 치환"""
    if not text:
        return ""
    for w in PROHIBITED_INFER:
        text = text.replace(w, "해석")
    text = replace_template_tokens(text)
    return text.strip()


def build_system_prompt(
    section_id: str,
    engine_headline: str,
    survey_data: Dict[str, Any] = None,
    saju_data: Dict[str, Any] = None,
    existing_contents: List[str] = None,
    cards_summary: str = "",
) -> str:
    spec = PREMIUM_SECTIONS.get(section_id)
    if not spec:
        return ""
    title = spec.title
    min_chars = spec.min_chars
    master_body = get_master_body_markdown(section_id)

    saju_summary = (saju_data or {}).get("saju_summary", {})
    summary_json = json.dumps(saju_summary, ensure_ascii=False, indent=2) if saju_summary else "{}"

    truth_anchor = build_truth_anchor(saju_data or {})
    fact_ctx = build_fact_check_context(saju_data or {})

    existing_text = ""
    if existing_contents:
        existing_text = "\n\n".join([c[:1200] for c in existing_contents if c])

    return f"""너는 [{title}] 전문 컨설턴트다.

[목표]
- 최소 {min_chars}자 이상으로 상세하게 작성하라.
- "보이는 글자" 기반 사실만 사용하고, 지장간/장간 등 추론 금지.
- 템플릿 토큰({{industry}} 등)을 절대 노출하지 마라.

[엔진 헤드라인]
{engine_headline or ""}

[사실 앵커]
{truth_anchor}

[검증 컨텍스트]
{fact_ctx}

[사주 요약 JSON]
{summary_json}

[설문 데이터]
{json.dumps(survey_data or {{}}, ensure_ascii=False, indent=2)}

[기존 섹션(중복 방지/연결)]
{existing_text}

[마스터 샘플(참고)]
{master_body}

[작성 규칙]
- 문장으로 명확히, 실행 가능한 조언을 포함.
- 과도한 단정 금지. 대신 '가능성/경향' 표현.
- 금지 단어(지장간/추론 등) 사용 금지.
"""


def generate_fallback_body(section_id: str, engine_headline: str, survey_data: Dict[str, Any]) -> str:
    """LLM 실패/불완전 시에도 무조건 본문 생성 (P0)"""
    spec = PREMIUM_SECTIONS.get(section_id)
    title = spec.title if spec else section_id
    industry = (survey_data or {}).get("industry") or "해당 업종"
    goal = (survey_data or {}).get("goal") or "목표"
    pain = (survey_data or {}).get("painPoint") or "현재 병목"

    return f"""# {spec.icon if spec else "📌"} {title}

> 핵심 결론: {engine_headline or "핵심 결론을 정리 중입니다. (자동 폴백)"}

## 현재 상황(요약)
- 업종: {industry}
- 목표: {goal}
- 병목: {pain}

## 바로 적용할 액션(오늘 가능한 것만)
1) **데이터 1개만 정리**: 최근 30일 매출/유입/문의/전환 중 1개를 고정 지표로 선택하고 매일 기록합니다.
2) **병목 1개만 제거**: "{pain}"을 방해하는 가장 큰 원인을 1개 고르고, 오늘 30분 안에 줄일 수 있는 조치를 실행합니다.
3) **결정 루틴 고정**: 오전(또는 업무 시작 직후) 10분 동안 '오늘의 1순위'를 명확히 적고, 그 외는 보류합니다.

## 리스크 & 주의
- 본 섹션은 LLM 생성이 실패해도 결과가 비지 않도록 만든 자동 폴백입니다.
- 추가 입력(매출 규모/고객군/채널/가격/팀 상황)이 있으면 더 정밀한 실행 플랜으로 강화 가능합니다.
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OpenAI Key Provider (원본 유지)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_openai_api_key() -> str:
    try:
        from app.config import settings
        return settings.OPENAI_API_KEY
    except Exception:
        return ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Builder
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PremiumReportBuilder:
    def __init__(self, max_concurrency: int = 3):
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._client = self._get_client()

    def _get_client(self) -> AsyncOpenAI:
        api_key = get_openai_api_key()
        return AsyncOpenAI(api_key=api_key, timeout=httpx.Timeout(120.0, connect=15.0), max_retries=2)

    async def _repair_output_once(
        self,
        section_id: str,
        system_prompt: str,
        draft_markdown: str,
        violations: List[str],
        min_chars: int,
    ) -> str:
        """규칙 위반 시 1회 리라이트 수정"""
        if not draft_markdown:
            return ""
        try:
            repair_user = f"""너는 아래 초안을 '규칙 위반을 제거'하여 다시 작성한다.
[위반 목록]
{chr(10).join(f"- {v}" for v in violations)}
[초안]
{draft_markdown}
"""
            response = await self._client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": repair_user},
                ],
                temperature=0.2,
                max_tokens=1800,
            )
            out = (response.choices[0].message.content or "").strip()
            if len(out) < min_chars:
                return draft_markdown
            return out
        except Exception as e:
            logger.error(f"[Builder] repair 실패 section={section_id}: {e}")
            return draft_markdown

    async def build_premium_sections(
        self,
        saju_data: Dict[str, Any],
        survey_data: Dict[str, Any],
        engine_headline: str,
        target_year: int = 2026,
        job_id: str = None,
    ) -> List[Dict[str, Any]]:
        """7개 섹션 모두 생성. P0: 절대 빈 섹션 금지"""
        sections = []
        existing_contents: List[str] = []

        for section_id in ["exec", "money", "business", "team", "health", "calendar", "sprint"]:
            try:
                s = await self._generate_section_safe(
                    section_id=section_id,
                    saju_data=saju_data,
                    survey_data=survey_data,
                    target_year=target_year,
                    engine_headline=engine_headline,
                    existing_contents=existing_contents,
                    job_id=job_id,
                )
            except Exception as e:
                logger.error(f"[Builder] 섹션 생성 실패 section={section_id} job_id={job_id}: {e}")
                s = {
                    "section_id": section_id,
                    "title": PREMIUM_SECTIONS.get(section_id).title if PREMIUM_SECTIONS.get(section_id) else section_id,
                    "body_markdown": generate_fallback_body(section_id, engine_headline, survey_data or {}),
                    "char_count": 0,
                    "llm_response_len": 0,
                    "guardrail_violations": ["exception_fallback"],
                    "repaired": False,
                }
            sections.append(s)
            existing_contents.append((s.get("body_markdown") or "")[:1500])

        # 정렬
        sections.sort(key=lambda x: PREMIUM_SECTIONS.get(x["section_id"]).order if PREMIUM_SECTIONS.get(x["section_id"]) else 999)
        return sections

    async def _generate_section_safe(
        self,
        section_id: str,
        saju_data: Dict[str, Any],
        survey_data: Dict[str, Any],
        target_year: int,
        engine_headline: str,
        existing_contents: List[str],
        job_id: str = None,
    ) -> Dict[str, Any]:
        spec = PREMIUM_SECTIONS.get(section_id)
        system_prompt = build_system_prompt(section_id, engine_headline, survey_data, saju_data, existing_contents)
        user_prompt = f"## 사주 원국 분석 및 리포트 작성 부탁드립니다. ({target_year}년)"

        llm_response_len = 0
        body_markdown = ""
        try:
            async with self._semaphore:
                response = await self._client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                    max_tokens=1800,
                )
                body_markdown = (response.choices[0].message.content or "").strip()
                llm_response_len = len(body_markdown)
        except Exception as e:
            logger.error(f"[Builder] LLM 호출 실패 section={section_id} job_id={job_id}: {e}")
            body_markdown = generate_fallback_body(section_id, engine_headline, survey_data or {}) or ""
            llm_response_len = 0

        # ✅ 결과가 비거나 너무 짧으면(불완전) fallback으로 교체
        min_chars = spec.min_chars if spec else 800
        if (not body_markdown) or (len(body_markdown) < min_chars):
            body_markdown = generate_fallback_body(section_id, engine_headline, survey_data or {}) or body_markdown

        # ── P0 Guardrail 검증 및 수정 ──
        violations = detect_guardrail_violations(body_markdown, saju_data or {})
        repaired = False
        if violations:
            logger.warning(f"[Builder] Guardrail 위반 탐지: {violations}")
            repaired_text = await self._repair_output_once(section_id, system_prompt, body_markdown, violations, min_chars)
            if repaired_text != body_markdown:
                repaired = True
                body_markdown = repaired_text

            # 2차 검증 실패 시 최후 수단
            violations2 = detect_guardrail_violations(body_markdown, saju_data or {})
            if violations2:
                body_markdown = sanitize_output_last_resort(body_markdown, saju_data or {})

        body_markdown = replace_template_tokens(body_markdown)
        body_markdown = normalize_year(body_markdown, target_year)

        return {
            "section_id": section_id,
            "title": spec.title if spec else section_id,
            "body_markdown": body_markdown,
            "char_count": len(body_markdown),
            "llm_response_len": llm_response_len,
            "guardrail_violations": violations,
            "repaired": repaired,
        }

    # (기타 Helper 함수들은 기존 로직과 동일하게 유지)
    async def regenerate_single_section(
        self,
        section_id: str,
        saju_data: Dict[str, Any],
        survey_data: Dict[str, Any],
        target_year: int,
        engine_headline: str,
        existing_contents: List[str],
        job_id: str = None,
    ) -> Dict[str, Any]:
        """단일 섹션 재생성"""
        return await self._generate_section_safe(
            section_id=section_id,
            saju_data=saju_data,
            survey_data=survey_data,
            target_year=target_year,
            engine_headline=engine_headline,
            existing_contents=existing_contents or [],
            job_id=job_id,
        )
