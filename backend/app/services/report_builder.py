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
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 P0: 임포트 순환 및 부분 초기화 방지 선점 선언
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
premium_report_builder = None  # 파일 하단에서 실제 인스턴스로 초기화됨
report_builder = None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 마스터 샘플 로드
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
    # 정규식으로 남은 {token} 형태 모두 치환
    text = re.sub(r"\{[a-zA-Z_]+\}", "해당 항목", text)
    return text.strip()


def normalize_year(text: str, target_year: int) -> str:
    """출력에 섞인 연도(예: 2025)를 target_year로 정규화"""
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
# 프리미엄 섹션 정의
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class SectionSpec:
    id: str
    title: str
    icon: str
    order: int
    min_chars: int = 800


PREMIUM_SECTIONS: Dict[str, SectionSpec] = {
    "exec": SectionSpec(id="exec", title="2026 비즈니스 전략 기상도", icon="🌦️", order=1, min_chars=900),
    "money": SectionSpec(id="money", title="자본 유동성 및 현금흐름 최적화", icon="💰", order=2, min_chars=900),
    "business": SectionSpec(id="business", title="시장 포지셔닝 및 상품 확장 전략", icon="📍", order=3, min_chars=900),
    "team": SectionSpec(id="team", title="조직 확장 및 파트너십 가이드", icon="🤝", order=4, min_chars=900),
    "health": SectionSpec(id="health", title="오너 리스크 관리 및 번아웃 방어", icon="🧯", order=5, min_chars=900),
    "calendar": SectionSpec(id="calendar", title="12개월 비즈니스 스프린트 캘린더", icon="🗓️", order=6, min_chars=900),
    "sprint": SectionSpec(id="sprint", title="향후 90일 매출 극대화 액션플랜", icon="🚀", order=7, min_chars=900),
}


def get_master_body_markdown(section_id: str) -> str:
    if not MASTER_SAMPLES:
        return ""
    sample = MASTER_SAMPLES.get(section_id) or {}
    body = sample.get("body_markdown") or ""
    return body.strip()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# P0 Guardrails (지장간 추론 금지)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROHIBITED_INFER = [
    "지장간", "장간", "추론", "추측", "몰래", "숨겨진", "내면에 숨은", "드러나지 않은"
]


def build_truth_anchor(saju_data: Dict[str, Any]) -> str:
    """'보이는 글자' 기반의 사실 앵커 생성"""
    if not saju_data:
        return "원국 데이터가 제공되지 않았습니다."
    
    # 사주 데이터 구조 대응 (Worker v13 대응)
    y = saju_data.get("year_pillar", "")
    m = saju_data.get("month_pillar", "")
    d = saju_data.get("day_pillar", "")
    h = saju_data.get("hour_pillar", "")
    
    parts = []
    if y: parts.append(f"년주:{y}")
    if m: parts.append(f"월주:{m}")
    if d: parts.append(f"일주:{d}")
    if h: parts.append(f"시주:{h}")
    
    return " / ".join(parts) or "원국 정보가 불충분합니다."


def detect_guardrail_violations(text: str, saju_data: Dict[str, Any]) -> List[str]:
    if not text:
        return ["empty_output"]
    v = []
    # 1) 지장간/추론 금지 단어 체크
    for w in PROHIBITED_INFER:
        if w in text:
            v.append(f"prohibited:{w}")
    # 2) 템플릿 토큰 유출 체크
    v += [f"template:{t}" for t in check_template_leaks(text, context="guardrail")]
    return v


def sanitize_output_last_resort(text: str, saju_data: Dict[str, Any]) -> str:
    """최후 수단: 위험 단어 강제 치환 및 토큰 정리"""
    if not text:
        return ""
    for w in PROHIBITED_INFER:
        text = text.replace(w, "기질적")
    text = replace_template_tokens(text)
    return text.strip()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 프롬프트 빌더
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_system_prompt(
    section_id: str,
    saju_data: Dict[str, Any],
    rulecards: List[Dict[str, Any]],
    survey_data: Dict[str, Any],
    target_year: int,
    user_question: str = "",
    existing_contents: List[str] = None,
) -> str:
    spec = PREMIUM_SECTIONS.get(section_id)
    title = spec.title if spec else section_id
    min_chars = spec.min_chars if spec else 800
    master_body = get_master_body_markdown(section_id)

    # 룰카드 요약
    cards_text = ""
    for i, c in enumerate(rulecards[:8]): # 상위 8개 활용
        cards_text += f"[{i+1}] {c.get('topic')}: {c.get('interpretation')}\n- 액션: {c.get('action')}\n"

    saju_summary = saju_data.get("saju_summary", {})
    truth_anchor = build_truth_anchor(saju_data)

    existing_text = ""
    if existing_contents:
        existing_text = "\n\n".join([c[:1000] for c in existing_contents if c])

    return f"""너는 사주 분석 기반 비즈니스 전략가이며, 현재 작성 중인 섹션은 [{title}]이다.

[작성 목표]
1. 반드시 한국어로 작성하며, 최소 {min_chars}자 이상의 풍부한 분량을 확보하라.
2. 제공된 [룰카드]의 핵심 해석과 액션을 비즈니스 관점에서 구체화하라.
3. "보이는 글자(원국)" 기반 사실만 사용하고, '지장간'이나 '숨겨진 글자'에 대한 추론은 절대 금지한다.
4. 템플릿 토큰({{industry}} 등)은 절대 노출하지 말고 자연스러운 문장으로 풀어서 써라.

[사용자 비즈니스 정보]
- 업종: {survey_data.get('industry', '정보 없음')}
- 현재 고민: {user_question or survey_data.get('painPoint', '정보 없음')}
- 목표: {survey_data.get('goal', '정보 없음')}

[사주 사실 앵커 (보이는 글자)]
{truth_anchor}
- 일간: {saju_data.get('day_master', '정보 없음')}
- 특징: {json.dumps(saju_summary.get('core_traits', []), ensure_ascii=False)}

[분석 엔진 추천 룰카드]
{cards_text}

[이전 섹션 내용 (중복 방지)]
{existing_text}

[마스터 샘플 문체 참고]
{master_body}

[작성 가이드라인]
- 도입부에서 사주적 배경을 설명하고, 중반부에서 구체적인 비즈니스 전략을, 결론에서 실행 가능한 액션 아이템을 제시하라.
- 전문적이지만 따뜻하고 신뢰감 있는 컨설팅 어조를 유지하라.
"""


def generate_fallback_body(section_id: str, survey_data: Dict[str, Any]) -> str:
    """LLM 실패 시 비지 않도록 즉시 반환되는 폴백 텍스트 (P0)"""
    spec = PREMIUM_SECTIONS.get(section_id)
    title = spec.title if spec else section_id
    industry = survey_data.get("industry") or "해당 업종"
    
    return f"""# {spec.icon if spec else "📌"} {title}

현재 시스템 부하 또는 분석 엔진의 일시적 오류로 인해 해당 섹션의 상세 분석 결과를 불러오지 못했습니다. 
하지만 귀하의 **{industry}** 비즈니스 목표를 달성하기 위해 가장 우선적으로 고려해야 할 핵심 원칙은 다음과 같습니다.

## 비즈니스 핵심 액션 가이드
1. **현재 병목 구간의 데이터화**: 주관적인 판단보다는 실제 수치(문의량, 전환율 등)를 기록하여 의사결정의 근거를 마련하십시오.
2. **리스크 분산 전략**: 한 가지 채널이나 상품에 의존하기보다, 현재 상황에서 즉시 시도할 수 있는 작은 대안을 마련하십시오.
3. **오너의 컨디션 관리**: 1인 기업가에게 가장 큰 리스크는 오너의 번아웃입니다. 매일 최소 30분의 완전한 휴식 시간을 확보하십시오.

*해당 내용은 시스템에 의해 자동 생성된 기본 가이드입니다. 상세한 사주 맞춤형 분석은 잠시 후 다시 시도해 주시기 바랍니다.*
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OpenAI Key Provider
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_openai_api_key() -> str:
    try:
        from app.config import settings
        return settings.OPENAI_API_KEY
    except Exception:
        import os
        return os.getenv("OPENAI_API_KEY", "")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Builder Class
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
            repair_user = f"""너는 아래 작성된 초안에서 '규칙 위반 사항'을 제거하고 보완하여 다시 작성한다.
[위반 목록]
{chr(10).join(f"- {v}" for v in violations)}

[수정 대상 초안]
{draft_markdown}
"""
            response = await self._client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": repair_user},
                ],
                temperature=0.2,
                max_tokens=2000,
            )
            out = (response.choices[0].message.content or "").strip()
            if len(out) < min_chars * 0.7: # 너무 짧아지면 원본 유지
                return draft_markdown
            return out
        except Exception as e:
            logger.error(f"[Builder] repair 실패 section={section_id}: {e}")
            return draft_markdown

    async def regenerate_single_section(
        self,
        section_id: str,
        saju_data: Dict[str, Any],
        rulecards: List[Dict[str, Any]],
        feature_tags: List[str],
        target_year: int,
        user_question: str,
        survey_data: Dict[str, Any],
        job_id: str = None,
    ) -> Dict[str, Any]:
        """Worker v13 인터페이스에 맞춘 단일 섹션 생성 로직 (P0 보강)"""
        
        # 1) 카드 0개 체크 (P0-1)
        if not rulecards:
            logger.warning(f"[Builder] 카드 없음 section={section_id} job={job_id}")
            return {
                "ok": True,
                "section": {
                    "section_id": section_id,
                    "title": PREMIUM_SECTIONS.get(section_id).title if PREMIUM_SECTIONS.get(section_id) else section_id,
                    "body_markdown": generate_fallback_body(section_id, survey_data)
                }
            }

        spec = PREMIUM_SECTIONS.get(section_id)
        min_chars = spec.min_chars if spec else 800
        
        # 2) 프롬프트 생성
        system_prompt = build_system_prompt(
            section_id=section_id,
            saju_data=saju_data,
            rulecards=rulecards,
            survey_data=survey_data,
            target_year=target_year,
            user_question=user_question
        )
        
        user_prompt = f"## {target_year}년 비즈니스 운세 분석 및 [{spec.title if spec else section_id}] 전략 리포트를 작성해줘."

        body_markdown = ""
        llm_response_len = 0
        
        try:
            async with self._semaphore:
                response = await self._client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.4,
                    max_tokens=2200,
                )
                body_markdown = (response.choices[0].message.content or "").strip()
                llm_response_len = len(body_markdown)
        except Exception as e:
            logger.error(f"[Builder] LLM 호출 실패 section={section_id} job={job_id}: {e}")
            # P0: 실패 시 절대 비우지 않고 폴백 반환
            return {
                "ok": False,
                "error": str(e),
                "section": {
                    "section_id": section_id,
                    "body_markdown": generate_fallback_body(section_id, survey_data)
                }
            }

        # 3) 분량 미달 체크 및 폴백 적용
        if not body_markdown or len(body_markdown) < 200:
            body_markdown = generate_fallback_body(section_id, survey_data)

        # 4) P0 Guardrail 검증 및 수정
        violations = detect_guardrail_violations(body_markdown, saju_data)
        repaired = False
        if violations:
            logger.warning(f"[Builder] Guardrail 위반 탐지 ({section_id}): {violations}")
            repaired_text = await self._repair_output_once(section_id, system_prompt, body_markdown, violations, min_chars)
            if repaired_text != body_markdown:
                repaired = True
                body_markdown = repaired_text

            # 2차 검증 실패 시 최후 수단 (강제 치환)
            violations2 = detect_guardrail_violations(body_markdown, saju_data)
            if violations2:
                body_markdown = sanitize_output_last_resort(body_markdown, saju_data)

        # 5) 토큰 치환 및 연도 정규화 (P0-3)
        body_markdown = replace_template_tokens(body_markdown)
        body_markdown = normalize_year(body_markdown, target_year)

        return {
            "ok": True,
            "section": {
                "section_id": section_id,
                "title": spec.title if spec else section_id,
                "body_markdown": body_markdown,
                "char_count": len(body_markdown),
                "llm_response_len": llm_response_len,
                "guardrail_violations": violations,
                "repaired": repaired
            }
        }

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 P0: 인스턴스 초기화 및 할당
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
premium_report_builder = PremiumReportBuilder()
report_builder = premium_report_builder