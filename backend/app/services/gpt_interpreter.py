"""
GPT Interpreter - Production Ready
- Chat Completions API only
- Detailed error logging for Railway
- Robust fallback handling
- 🔥 P0: Truth Anchor (환각 방지 강화) 적용
"""
import json
import logging
import random
import asyncio
import re
from typing import Optional, Dict, Any, Tuple, Set
from openai import AsyncOpenAI, APIError, RateLimitError, APIConnectionError, AuthenticationError
import httpx

from app.config import get_settings
from app.models.schemas import ConcernType, InterpretResponse
from app.rules.interpretation_rules import get_full_system_prompt
from app.services.openai_key import get_openai_api_key, key_fingerprint, key_tail

logger = logging.getLogger(__name__)

# P0: 원국 글자 환각 방지용 기준 데이터
_ALL_STEMS_BRANCHES: Set[str] = set(list("갑을병정무기경신임계자축인묘진사오미신유술해"))

GUARDRAIL_ADDON = """
## Rules
1. No specific person names
2. Professional consulting tone
3. No lecture-style language
4. Use JSON output only
"""

class GptInterpreter:
    def __init__(self):
        self._client = None
    
    def _get_client(self) -> AsyncOpenAI:
        settings = get_settings()
        api_key = get_openai_api_key()
        return AsyncOpenAI(
            api_key=api_key,
            timeout=httpx.Timeout(float(settings.sajuos_timeout), connect=15.0),
            max_retries=0
        )

    def _build_truth_anchor(self, saju_data: Dict[str, Any]) -> str:
        """
        🔥 P0: 동적 Truth Anchor
        - 원국(년/월/일/시)에서 등장한 천간/지지 글자만 허용
        - 금지 글자 목록을 명시하여 환각을 원천 봉쇄
        """
        saju_data = saju_data or {}
        y = saju_data.get("year_pillar") or ""
        m = saju_data.get("month_pillar") or ""
        d = saju_data.get("day_pillar") or ""
        h = saju_data.get("hour_pillar") or ""

        # 실제 존재하는 글자 추출
        pillars = [p for p in [y, m, d, h] if isinstance(p, str) and p]
        joined = "".join(pillars)
        allowed = sorted(set([ch for ch in joined if ch in _ALL_STEMS_BRANCHES]))
        allowed_set = set(allowed)
        
        # 금지된 글자 목록 생성
        forbidden = sorted([ch for ch in _ALL_STEMS_BRANCHES if ch not in allowed_set])
        forbidden_preview = "".join(forbidden[:14]) + ("…" if len(forbidden) > 14 else "")
        allowed_preview = "".join(allowed) if allowed else "(unknown)"

        # 엔진 확정 데이터 (십성, 오행, 격국)
        summary = saju_data.get("saju_summary") or {}
        ten_present = summary.get("ten_gods_present") or saju_data.get("ten_gods_present") or []
        elements_count = summary.get("elements_count") or {}
        elements_present = [k for k, v in elements_count.items() if isinstance(v, (int, float)) and v > 0]
        allowed_structures = summary.get("allowed_structure_names") or []
        primary_structure = summary.get("primary_structure") or ""

        return f"""
## 🚨 ZERO TOLERANCE RULES (절대 준수)
1) **허용 글자만 언급**: 이 원국에서 언급 가능한 천간/지지 = [{allowed_preview}] 뿐이다.
2) **금지 글자 언급 금지**: [{forbidden_preview}] 및 허용 밖 글자는 절대 언급하지 마라.
3) **상상 금지**: 지장간/숨은 글자/추론으로 "있다"고 말하지 마라.
4) **오타 금지**: '걸록격' 사용 금지. (건록격으로 표기)
5) **데이터 정합성**: 
   - '있다'고 단정 가능한 십성: {', '.join(ten_present) if ten_present else '(none)'}
   - 실제로 존재하는 오행: {', '.join(elements_present) if elements_present else '(unknown)'}
   - 허용된 격국: {', '.join(allowed_structures[:12]) if allowed_structures else '(unknown)'}
   - 최우선 격국: {primary_structure or '(unknown)'}
""".strip()

    async def _call_llm_json(self, system_prompt: str, user_prompt: str) -> Tuple[Dict[str, Any], int]:
        settings = get_settings()
        client = self._get_client()
        full_system = system_prompt + "\n\n" + GUARDRAIL_ADDON
        
        for attempt in range(settings.sajuos_max_retries):
            try:
                response = await client.chat.completions.create(
                    model=settings.openai_model,
                    messages=[
                        {"role": "system", "content": full_system},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=settings.max_output_tokens,
                    temperature=0.3,
                    response_format={"type": "json_object"}
                )
                content = response.choices[0].message.content
                tokens_used = response.usage.total_tokens if response.usage else 0
                
                parsed = self._parse_json(content)
                if parsed:
                    return parsed, tokens_used
            except Exception as e:
                logger.error(f"[LLM] Error: {str(e)}")
                await asyncio.sleep(1.0)
        
        raise Exception("LLM call failed after retries")

    def _parse_json(self, content: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(content)
        except:
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                try: return json.loads(match.group())
                except: pass
        return None

    async def interpret(self, saju_data: Dict[str, Any], name: str, gender: Optional[str], concern_type: ConcernType, question: str) -> InterpretResponse:
        settings = get_settings()
        try:
            system_prompt = get_full_system_prompt(concern_type)
            user_prompt = self._build_prompt(saju_data, name, gender, concern_type, question)
            data, tokens = await self._call_llm_json(system_prompt, user_prompt)
            result = self._build_result(data, name)
            result["model_used"] = settings.openai_model
            result["tokens_used"] = tokens
            return InterpretResponse(**result)
        except Exception as e:
            logger.error(f"[INTERPRET] Failed: {str(e)}")
            return self._fallback(name)

    def _build_prompt(self, saju_data: Dict, name: str, gender: Optional[str], concern_type: ConcernType, question: str) -> str:
        # 사주 데이터 정리
        y = self._get_pillar(saju_data, "year_pillar")
        m = self._get_pillar(saju_data, "month_pillar")
        d = self._get_pillar(saju_data, "day_pillar")
        h = self._get_pillar(saju_data, "hour_pillar") or "N/A"
        
        day_master = saju_data.get("day_master", d[0] if d else "")
        day_master_elem = saju_data.get("day_master_element", "")
        
        gender_text = "Male" if gender == "male" else "Female" if gender == "female" else "N/A"
        
        saju_summary = saju_data.get("saju_summary", {})
        summary_json = json.dumps(saju_summary, ensure_ascii=False, indent=2) if saju_summary else "{}"
        
        # 🔥 P0: Truth Anchor 생성 (지시서 순서 적용)
        truth_anchor = self._build_truth_anchor(saju_data)
        
        return f"""[User Info]
- Gender: {gender_text}
- Concern: {concern_type}
- Question: {question}

[Saju]
- Year: {y} / Month: {m} / Day: {d} / Hour: {h}

[Day Master]
- Stem: {day_master} / Element: {day_master_elem}

{truth_anchor}

[🔴 Ground Truth saju_summary - 이 데이터가 정답이다]
{summary_json}

Analyze and respond in JSON format."""

    def _get_pillar(self, data: Dict, key: str) -> str:
        pillar = data.get(key, "")
        if isinstance(pillar, dict): return pillar.get("ganji", str(pillar))
        return str(pillar)

    def _build_result(self, data: Dict[str, Any], name: str) -> Dict[str, Any]:
        return {
            "success": True,
            "summary": data.get("summary", "분석 완료"),
            "structure": data,
            "day_master_analysis": data.get("day_master_analysis", ""),
            "strengths": data.get("strengths", []),
            "risks": data.get("risks", []),
            "answer": data.get("answer", ""),
            "action_plan": data.get("action_plan", []),
            "lucky_periods": data.get("lucky_periods", []),
            "caution_periods": data.get("caution_periods", []),
            "lucky_elements": data.get("lucky_elements", {}),
            "blessing": data.get("blessing", f"{name}님을 응원합니다!"),
            "disclaimer": "본 분석 결과는 참고용입니다."
        }

    def _fallback(self, name: str) -> InterpretResponse:
        return InterpretResponse(success=False, summary="Service error", blessing=f"{name}님, 잠시 후 다시 시도해주세요.")

gpt_interpreter = GptInterpreter()