"""
report_builder.py
Premium section generator:
- Uses master sample markdown per section
- Uses selected RuleCards
- Injects dynamic Truth Anchor to prevent hallucinations
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from app.services.truth_anchor import build_truth_anchor

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
# Prompt rules (P0)
# -----------------------------

ENGINE_HEADLINE = "첫 문장 = ENGINE_HEADLINE. 수정/부정/희석 금지."

ROOT_CAUSE_RULE = """## 🧠 Root Cause Rule (P0, 절대규칙)
1) 결론(원인)은 반드시 '사주/룰카드'에서 시작한다. 설문은 '증상'이다.
2) 설문(industry/painPoint/goal/time)은 "현장에서 어떻게 드러났는지" 설명에만 사용한다.
3) 금지(실패): "고객님이 설문에서 ~라고 하셔서"를 원인으로 확정하는 서술.
4) 허용(정답): "원국/룰카드 구조(원인) 때문에 {industry} 현장에서 {painPoint}로 발현(증상)"
5) 첫 문장 = ENGINE_HEADLINE. 수정/부정/희석 금지.
"""

DATA_COMPLIANCE_RULE = """## 🔴 데이터 준수 철칙 (위반시 실패)
1) 아래 'Ground Truth saju_summary'에 없는 오행/십성은 "있다"고 주장하지 마라.
2) is_missing_jaesung=true면, 정재/편재가 "있다"고 말하지 마라.
3) is_missing_shiksang=true면, 식신/상관이 "있다"고 말하지 마라.
4) allowed_structure_names 밖의 격국 이름 사용 금지.
5) 지장간/숨은 십성으로 억지 추론 금지.
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
# Master sample loader (optional)
# -----------------------------

def get_master_body_markdown(section_id: str) -> str:
    """
    Optional: loads master sample markdown. If unavailable, returns empty.
    """
    try:
        from app.templates.master_samples.index import get_master_sample  # type: ignore
        sample = get_master_sample(section_id)
        return sample.get("body_markdown") or sample.get("markdown") or ""
    except Exception:
        return ""


# -----------------------------
# System prompt builder
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
) -> str:
    spec = PREMIUM_SECTIONS.get(section_id) or SectionSpec(section_id, section_id, 800)
    title = spec.title
    min_chars = spec.min_chars
    master_body = get_master_body_markdown(section_id)

    # dynamic truth anchor (P0) - 외부에서 주입된 것이 있으면 사용, 없으면 자체 생성
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

    # survey facts
    industry = survey_data.get("industry") or ""
    pain = user_question or survey_data.get("painPoint") or ""
    goal = survey_data.get("goal") or ""
    timeframe = survey_data.get("time") or ""

    # ground truth summary json
    summary = saju_data.get("saju_summary") or {}
    summary_json = json.dumps(summary, ensure_ascii=False, indent=2)

    existing = "\n\n".join(existing_contents or [])
    if existing:
        existing = f"## 기존 생성 내용(중복 금지 참고)\n{existing}\n"

    return f"""{truth_anchor}

{ROOT_CAUSE_RULE}

{DATA_COMPLIANCE_RULE}

## Ground Truth saju_summary (정답지)
{summary_json}

## 사용자 비즈니스 정보
- 업종: {industry}
- 고민/질문: {pain}
- 목표: {goal}
- 기간: {timeframe}

## 엔진 확정 룰카드 (근거로만 사용)
{cards_block}

## 마스터 샘플 문체 참고 (스타일만)
{master_body}

{existing}

## 작성 지시
- 섹션: [{title}] (section_id={section_id})
- 반드시 {min_chars}자 이상
- 루프: (원국/룰카드 구조) → (현장 발현) → (실행 액션 3~7개)
- 금지: '추가 정보 필요', '분석할 수 없음', 사주 지식 자랑, 지장간 추론.
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
        truth_anchor: Optional[str] = None,  # 외부에서 주입 가능
    ) -> Dict[str, Any]:
        system_prompt = build_system_prompt(
            section_id=section_id,
            saju_data=saju_data,
            rulecards=rulecards,
            survey_data=survey_data,
            target_year=target_year,
            user_question=user_question,
            existing_contents=existing_contents,
            truth_anchor_override=truth_anchor,
        )
        user_prompt = f"{ENGINE_HEADLINE}\n섹션 [{section_id}] 내용을 작성하라."
        
        try:
            body = await self._call_openai(system_prompt, user_prompt)
        except Exception as e:
            logger.error(f"[Builder] OpenAI 호출 실패: {e}")
            body = f"[섹션 생성 오류: {str(e)[:100]}]"

        spec = PREMIUM_SECTIONS.get(section_id) or SectionSpec(section_id, section_id, 800)

        used_ids = [c.get("id") for c in rulecards if c.get("id")]

        return {
            "section_id": section_id,
            "title": spec.title,
            "body_markdown": body,
            "char_count": len(body),
            "llm_response_len": len(body),
            "guardrail_violations": [],
            "repaired": False,
            "match_summary": {"selected_rulecards": len(rulecards), "model": self.model, "job_id": job_id},
            "used_rulecard_ids": used_ids[:50],
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    async def regenerate_single_section(self, *args, **kwargs) -> Dict[str, Any]:
        # Alias for retry logic
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
