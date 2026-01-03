"""
report_builder.py
Premium section generator:
- Uses master sample markdown per section
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
# Master sample loader (optional)
# -----------------------------

def get_master_body_markdown(section_id: str) -> str:
    """Optional: loads master sample markdown. If unavailable, returns empty."""
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
    is_retry: bool = False,  # 🔥 재시도 여부
) -> str:
    spec = PREMIUM_SECTIONS.get(section_id) or SectionSpec(section_id, section_id, 800)
    title = spec.title
    min_chars = spec.min_chars
    master_body = get_master_body_markdown(section_id)

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

    return f"""{truth_anchor}

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

## 엔진 확정 룰카드 (근거로만 사용)
{cards_block}

## 마스터 샘플 문체 참고 (스타일만)
{master_body}

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
    ) -> Dict[str, Any]:
        """
        섹션 생성 + 🔥 거절 응답 감지 시 1회 자동 재시도
        """
        spec = PREMIUM_SECTIONS.get(section_id) or SectionSpec(section_id, section_id, 800)
        user_prompt = f"{ENGINE_HEADLINE}\n섹션 [{section_id}] 내용을 작성하라."
        
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
                # 첫 번째 시도에서 거절 → 재시도
                logger.warning(f"[Builder] 거절 응답 감지 (section={section_id}): {patterns} → 재시도")
                retried = True
                rejection_detected = True
                rejection_patterns = patterns
                continue
            elif is_rejection and attempt == 1:
                # 재시도에서도 거절 → 경고만 남기고 사용
                logger.warning(f"[Builder] 재시도 후에도 거절 응답 (section={section_id}): {patterns}")
                rejection_detected = True
                rejection_patterns = patterns
                break
            else:
                # 정상 응답
                if is_retry:
                    logger.info(f"[Builder] 재시도 성공 (section={section_id})")
                break

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
            "match_summary": {
                "selected_rulecards": len(rulecards),
                "model": self.model,
                "job_id": job_id,
                "retried": retried,
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
