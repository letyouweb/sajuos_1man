"""
gpt_interpreter.py
Used for "interpret" endpoint (short answer / Q&A style).
We inject Truth Anchor so the model cannot invent stems/ten-gods.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

import httpx

from app.services.truth_anchor import build_truth_anchor

logger = logging.getLogger(__name__)


class GPTInterpreter:
    def __init__(
        self,
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 900,
        timeout: float = 45.0,
    ):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.temperature = float(temperature)
        self.max_tokens = int(max_tokens)
        self.timeout = float(timeout)

    def _build_prompt(self, saju_data: Dict[str, Any], question: str, target_year: Optional[int] = None) -> str:
        summary = saju_data.get("saju_summary") or {}
        summary_json = json.dumps(summary, ensure_ascii=False, indent=2)

        # 🔥 P0: 올바른 시그니처로 호출
        truth_anchor = build_truth_anchor(
            saju_data=saju_data,
            target_year=target_year,
            section_id="interpret",
        )

        return f"""{truth_anchor}

## 🔴 Ground Truth saju_summary - 이 데이터가 정답이다
{summary_json}

## 답변 규칙
- 질문에 대해 '비즈니스/실행' 관점으로 답해라.
- 원국/룰카드에 없는 오행/십성/격국을 만들지 마라.
- 추론(지장간/숨은 십성) 금지.
- '추가 정보 필요', '분석 불가' 같은 거절 문구 금지.

## 사용자 질문
{question}
""".strip()

    async def _call_openai(self, prompt: str) -> str:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY") or ""
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is missing")

        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": prompt},
            ],
        }
        headers = {"Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            return (data["choices"][0]["message"]["content"] or "").strip()

    async def interpret(self, saju_data: Dict[str, Any], question: str, target_year: Optional[int] = None) -> str:
        prompt = self._build_prompt(saju_data, question, target_year=target_year)
        try:
            return await self._call_openai(prompt)
        except Exception as e:
            logger.error(f"[Interpreter] OpenAI 호출 실패: {e}")
            return f"[해석 생성 오류: {str(e)[:100]}]"


gpt_interpreter = GPTInterpreter()

__all__ = ["GPTInterpreter", "gpt_interpreter"]
