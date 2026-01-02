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
from typing import Optional, Dict, Any, Tuple
from openai import AsyncOpenAI, APIError, RateLimitError, APIConnectionError, AuthenticationError
import httpx

from app.config import get_settings
from app.models.schemas import ConcernType, InterpretResponse
from app.rules.interpretation_rules import get_full_system_prompt
from app.services.openai_key import get_openai_api_key, key_fingerprint, key_tail

logger = logging.getLogger(__name__)

# P0: 원국 글자 환각 방지(천간/지지)
STEMS = ["갑","을","병","정","무","기","경","신","임","계"]
BRANCHES = ["자","축","인","묘","진","사","오","미","신","유","술","해"]
STEM_TO_ELEMENT = {
    "갑": "목", "을": "목",
    "병": "화", "정": "화",
    "무": "토", "기": "토",
    "경": "금", "신": "금",
    "임": "수", "계": "수",
}

def _parse_pillar(p: str) -> tuple[str, str]:
    """간지 문자열 분리"""
    p = (p or "").strip()
    return (p[0], p[1]) if len(p) >= 2 else ("", "")

def _allowed_chars_from_saju(saju_data: dict) -> dict:
    """사주 데이터에서 실제 존재하는 천간/지지 추출"""
    stems, branches = set(), set()
    for k in ["year_pillar","month_pillar","day_pillar","hour_pillar"]:
        g, z = _parse_pillar(saju_data.get(k, ""))
        if g: stems.add(g)
        if z: branches.add(z)
    return {"stems": sorted(stems), "branches": sorted(branches)}


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
        """Get or create OpenAI client with fresh settings"""
        settings = get_settings()
        api_key = get_openai_api_key()
        logger.debug("OpenAI client fp=%s tail=%s", key_fingerprint(api_key), key_tail(api_key))
        return AsyncOpenAI(
            api_key=api_key,
            timeout=httpx.Timeout(float(settings.sajuos_timeout), connect=15.0),
            max_retries=0
        )

    def _build_truth_anchor(self, saju_data: Dict[str, Any]) -> str:
        """
        🔥 P0: report_builder의 truth_anchor와 동일 계열.
        최종 프롬프트에서도 '없는 건 언급 금지'를 다시 못 박아 환각을 줄인다.
        """
        saju_data = saju_data or {}
        y = saju_data.get("year_pillar") or ""
        m = saju_data.get("month_pillar") or ""
        d = saju_data.get("day_pillar") or ""
        h = saju_data.get("hour_pillar") or ""

        pillars = [p for p in [y, m, d, h] if isinstance(p, str) and p]
        allowed_chars = sorted({ch for p in pillars for ch in p if ch.strip()})

        summary = saju_data.get("saju_summary") or {}
        if not isinstance(summary, dict):
            summary = {}

        ten_present = summary.get("ten_gods_present") or saju_data.get("ten_gods_present") or []
        if not isinstance(ten_present, list):
            ten_present = []

        elements_count = summary.get("elements_count") or {}
        if not isinstance(elements_count, dict):
            elements_count = {}
        elements_present = [k for k, v in elements_count.items() if isinstance(v, (int, float)) and v > 0]

        primary_structure = summary.get("primary_structure") or ""
        allowed_structures = summary.get("allowed_structure_names") or []
        if not isinstance(allowed_structures, list):
            allowed_structures = []

        return f"""[ZERO TOLERANCE RULES]
- 너는 해석가가 아니라 문장 조립기다. 엔진이 준 팩트만 써라.
- 4주에 실제로 등장하는 글자만 언급 허용: {''.join(allowed_chars) if allowed_chars else '(unknown)'}
- 위 목록에 없는 글자(예: 을/병/자 등) 언급 금지. 지장간/추론/일반론 금지.
- '있다'고 단정 가능한 십성: {', '.join(ten_present) if ten_present else '(none)'}
- 실제로 존재하는 오행: {', '.join(elements_present) if elements_present else '(unknown)'}
- 격국은 allowed_structure_names 안에서만: {', '.join(allowed_structures[:12]) if allowed_structures else '(unknown)'}
- primary_structure(최우선): {primary_structure or '(unknown)'}
[엔진 확정 4주] year={y} / month={m} / day={d} / hour={h}
"""

    async def _call_llm_json(self, system_prompt: str, user_prompt: str) -> Tuple[Dict[str, Any], int]:
        """Direct LLM call - no ping, no model list check"""
        settings = get_settings()
        client = self._get_client()
        full_system = system_prompt + "\n\n" + GUARDRAIL_ADDON
        last_error = None
        
        for attempt in range(settings.sajuos_max_retries):
            try:
                logger.info(f"[LLM] Attempt {attempt + 1}/{settings.sajuos_max_retries} | Model: {settings.openai_model}")
                
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
                model_used = response.model
                
                logger.info(f"[LLM] Success | Tokens: {tokens_used} | Model: {model_used}")
                
                parsed = self._parse_json(content)
                if parsed:
                    return parsed, tokens_used
                
                logger.warning("[LLM] JSON parse failed, retrying")
                last_error = Exception("JSON parsing failed")
                
            except AuthenticationError as e:
                error_detail = self._extract_error_detail(e)
                api_key = get_openai_api_key()
                logger.error(f"[LLM] AUTH_ERROR (401) | {error_detail}")
                raise Exception(f"Authentication failed: {error_detail}")
                
            except RateLimitError as e:
                error_detail = self._extract_error_detail(e)
                if "insufficient_quota" in str(e).lower():
                    logger.error(f"[LLM] QUOTA_EXHAUSTED | {error_detail}")
                    raise Exception("API quota exhausted - add billing credits")
                
                last_error = e
                delay = self._backoff(attempt, settings)
                logger.warning(f"[LLM] RATE_LIMIT | Waiting {delay:.1f}s | {error_detail}")
                await asyncio.sleep(delay)
                
            except Exception as e:
                last_error = e
                logger.error(f"[LLM] UNEXPECTED_ERROR | Type: {type(e).__name__} | {str(e)[:200]}")
                delay = self._backoff(attempt, settings)
                await asyncio.sleep(delay)
        
        raise Exception(f"LLM call failed after {settings.sajuos_max_retries} retries")

    def _extract_error_detail(self, error: Exception) -> str:
        try:
            if hasattr(error, 'message'):
                return str(error.message)[:200]
            return str(error)[:200]
        except:
            return str(error)[:200]

    def _backoff(self, attempt: int, settings) -> float:
        delay = min(settings.sajuos_retry_base_delay * (2 ** attempt), settings.sajuos_retry_max_delay)
        return delay * random.uniform(0.5, 1.5)

    def _parse_json(self, content: str) -> Optional[Dict[str, Any]]:
        if not content: return None
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:] if lines[0].startswith("```") else lines
            lines = lines[:-1] if lines and lines[-1].strip() == "```" else lines
            text = "\n".join(lines)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r'\{[\s\S]*\}', text)
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
            logger.error(f"[INTERPRET] Failed | Error: {type(e).__name__} | {str(e)}")
            return self._fallback(name, type(e).__name__, str(e))

    def _build_prompt(self, saju_data: Dict, name: str, gender: Optional[str], concern_type: ConcernType, question: str) -> str:
        year_p = self._get_pillar(saju_data, "year_pillar", "year")
        month_p = self._get_pillar(saju_data, "month_pillar", "month")
        day_p = self._get_pillar(saju_data, "day_pillar", "day")
        hour_p = self._get_pillar(saju_data, "hour_pillar", "hour") or "N/A"
        
        day_master = saju_data.get("day_master", day_p[0] if day_p else "")
        day_master_elem = saju_data.get("day_master_element", "")
        
        gender_map = {"male": "Male", "female": "Female", "other": "Other"}
        gender_text = gender_map.get(gender, "N/A")
        
        concern_map = {
            ConcernType.LOVE: "Love/Marriage",
            ConcernType.WEALTH: "Wealth/Finance",
            ConcernType.CAREER: "Career/Business",
            ConcernType.GENERAL: "General Fortune"
        }
        concern_text = concern_map.get(concern_type, "General")
        
        saju_summary = saju_data.get("saju_summary", {})
        summary_json = json.dumps(saju_summary, ensure_ascii=False, indent=2) if saju_summary else "{}"
        
        # 🔥 P0: 진실의 닻(Truth Anchor) 생성 호출
        truth_anchor = self._build_truth_anchor(saju_data)
        
        return f"""[User Info]
- Gender: {gender_text}
- Concern: {concern_text}
- Question: {question}

[Saju]
- Year: {year_p}
- Month: {month_p}
- Day: {day_p}
- Hour: {hour_p}

[Day Master]
- Stem: {day_master}
- Element: {day_master_elem}

[🔴 Ground Truth saju_summary - 이 데이터가 정답이다]
{summary_json}

[환각 방지 규칙]
1. 위 saju_summary에 없는 십성/오행을 "있다"고 주장하지 마라.
2. is_missing_shiksang=true면, 식상/상관이 "있다"고 말하지 마라.
3. is_missing_jaesung=true면, 재성이 "있다"고 말하지 마라.
4. allowed_structure_names 외의 격국 이름을 사용하지 마라.
5. 지장간/숨은천간으로 원국 성분을 창조하지 마라.

{truth_anchor}
Analyze and respond in JSON format."""

    def _get_pillar(self, data: Dict, key1: str, key2: str) -> str:
        pillar = data.get(key1, data.get(key2, ""))
        if isinstance(pillar, dict): return pillar.get("ganji", str(pillar))
        return str(pillar) if pillar else ""

    def _build_result(self, data: Dict[str, Any], name: str) -> Dict[str, Any]:
        legacy = data.get("legacy_fields", {})
        summary = data.get("summary") or legacy.get("summary") or "분석 완료"
        day_master_analysis = data.get("day_master_analysis") or legacy.get("day_master_analysis") or ""
        blessing = data.get("blessing") or legacy.get("blessing") or f"{name}님을 응원합니다!"
        
        return {
            "success": True,
            "summary": summary,
            "structure": data,
            "day_master_analysis": day_master_analysis,
            "strengths": data.get("strengths", []),
            "risks": data.get("risks", []),
            "answer": data.get("answer", ""),
            "action_plan": data.get("action_plan", []),
            "lucky_periods": data.get("lucky_periods", []),
            "caution_periods": data.get("caution_periods", []),
            "lucky_elements": data.get("lucky_elements", {}),
            "blessing": blessing,
            "disclaimer": data.get("disclaimer", "참고용입니다.")
        }

    def _fallback(self, name: str, error_code: str = "UNKNOWN", error_msg: str = "") -> InterpretResponse:
        return InterpretResponse(success=False, summary="Service error", blessing=f"{name}, we'll be back!", model_used=f"fallback_{error_code}", tokens_used=0)

gpt_interpreter = GptInterpreter()

_NORMALIZE_REPLACEMENTS = {
    "걸록격": "건록격",
    "걸록": "건록",
    "비견이 월지": "편인이 월지",
    "자수와 을목": "원국의 기운",
}

def normalize_generated_text(text: str) -> str:
    if not text: return ""
    out = text
    for k, v in _NORMALIZE_REPLACEMENTS.items():
        out = out.replace(k, v)
    return out