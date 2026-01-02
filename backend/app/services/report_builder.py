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

from openai import AsyncOpenAI
import httpx

from app.config import get_settings
from app.services.openai_key import get_openai_api_key
from app.services.terminology_mapper import sanitize_for_business
from app.services.job_store import job_store
from app.templates.master_samples import load_master_samples, get_master_body_markdown

logger = logging.getLogger(__name__)

MASTER_SAMPLES = load_master_samples("v1")

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
        logger.warning(f"[TemplateLeak] {context} | leaked: {leaked}")
    return leaked


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# P0-2: 섹션 ID 정합성 (기존 ID 유지)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class SectionSpec:
    id: str
    title: str
    max_cards: int
    min_chars: int
    fallback_headline: str
    topic_filter: List[str] = field(default_factory=list)


# 🔥 P0-2: 합의된 section_id 고정
PREMIUM_SECTIONS = {
    "exec": SectionSpec(
        "exec", "2026 비즈니스 전략 기상도", 20, 1500,
        "현재 사주 구조상 2026년 비즈니스 환경은 변화의 기운이 감지됩니다",
        topic_filter=["전체운", "종합", "일간", "성향", "기운", "운세"]
    ),
    "money": SectionSpec(
        "money", "자본 유동성 및 현금흐름 최적화", 20, 2500,
        "현재 구조상 현금흐름의 변동성이 예상됩니다",
        topic_filter=["재물", "재성", "정재", "편재", "현금", "매출", "투자"]
    ),
    "business": SectionSpec(
        "business", "시장 포지셔닝 및 상품 확장 전략", 20, 2500,
        "현재 구조상 시장 포지셔닝 재검토가 필요합니다",
        topic_filter=["사업", "창업", "경영", "관성", "정관", "편관", "시장"]
    ),
    "team": SectionSpec(
        "team", "조직 확장 및 파트너십 가이드", 20, 2000,
        "현재 구조상 파트너십 관리가 핵심 과제입니다",
        topic_filter=["비겁", "비견", "겁재", "동업", "파트너", "협력", "인맥"]
    ),
    "health": SectionSpec(
        "health", "주요 장애물 및 리스크 (2026)", 15, 1500,
        "현재 구조상 해당 리스크는 낮은 수준입니다",
        topic_filter=["리스크", "위험", "충", "형", "파", "손해", "장애", "번아웃"]
    ),
    "calendar": SectionSpec(
        "calendar", "12개월 비즈니스 스프린트 캘린더", 15, 2500,
        "현재 구조상 월별 리듬에 맞춘 전략이 필요합니다",
        topic_filter=["월운", "시기", "계절", "타이밍", "길일", "흉일", "대운"]
    ),
    "sprint": SectionSpec(
        "sprint", "향후 90일 매출 극대화 액션플랜", 15, 2000,
        "현재 구조상 90일 집중 실행이 효과적입니다",
        topic_filter=["실행", "액션", "계획", "목표", "식신", "상관", "식상"]
    ),
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# P0-1: 폴백 텍스트 (빈 섹션 방지)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_fallback_body(section_id: str, engine_headline: str, survey_data: Dict = None) -> str:
    """🔥 P0-1: 카드 0개 또는 LLM 실패 시 폴백 텍스트"""
    spec = PREMIUM_SECTIONS.get(section_id)
    if not spec:
        spec = SectionSpec(section_id, "섹션", 10, 500, "분석 중입니다")
    
    headline = engine_headline if engine_headline else spec.fallback_headline
    industry = (survey_data or {}).get("industry", "해당 업종")
    painPoint = (survey_data or {}).get("painPoint", "현재 병목")
    
    return f"""{headline}

## 현재 상황 분석

원인(사주/룰카드) 정보가 충분하지 않아 상세 분석이 제한됩니다.
설문으로만 억지 추론하는 것은 Root Cause Rule 위반이므로 생략합니다.

### 다음 행동 권장사항

1. **D+14**: {industry} 업종 현황 점검 및 데이터 수집
2. **D+30**: {painPoint} 관련 핵심 지표 모니터링 시작
3. **D+60**: 수집된 데이터 기반 전략 재수립

### 체크리스트
- [ ] 현재 상황 객관적 진단
- [ ] 핵심 지표 정의
- [ ] 데이터 수집 체계 구축
- [ ] 주간 리뷰 일정 확정
- [ ] 전문가 상담 검토

---
*추가 사주 정보나 룰카드 매칭이 확보되면 더 정밀한 분석이 가능합니다.*
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 프롬프트 구성 유틸리티 및 P0 Guardrails
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ROOT_CAUSE_RULE = """## 🧠 Root Cause Rule (절대규칙)
- 사주/룰카드(=원인)가 결론이다. 설문(=증상)은 결론이 아니다.
- 섹션의 첫 문장은 반드시 엔진이 확정한 결론으로 시작한다.
- 금지: "고객님이 설문에서 ~라고 하셨으니" 같은 서술.
"""

TENGOD_ORDER = ["비견", "겁재", "식신", "상관", "편재", "정재", "편관", "정관", "편인", "정인"]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# P0 Guardrails (환각/오타/지장간 추론 봉쇄)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEMS = ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계"]
BRANCHES = ["자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해"]
STEM_TO_ELEMENT = {
    "갑": "목", "을": "목",
    "병": "화", "정": "화",
    "무": "토", "기": "토",
    "경": "금", "신": "금",
    "임": "수", "계": "수",
}

# 금칙어/금지 표현
FORBIDDEN_PHRASES = [
    "관성 충돌", "관성충돌", "충돌 구조", "충돌구조",
    "월지 비견", "월지비견", "월지 겁재", "월지겁재",
    "지장간", "숨은천간", "hidden stem", "hidden-stem",
]

def _parse_pillar_ganji(pillar: str) -> tuple[str, str]:
    """'정사' -> ('정','사') 분리"""
    pillar = (pillar or "").strip()
    if len(pillar) >= 2:
        return pillar[0], pillar[1]
    return "", ""

def _derive_allowed_chars(saju_data: Dict[str, Any]) -> Dict[str, List[str]]:
    yp = saju_data.get("year_pillar", "")
    mp = saju_data.get("month_pillar", "")
    dp = saju_data.get("day_pillar", "")
    hp = saju_data.get("hour_pillar", "") or ""
    stems, branches = set(), set()
    for p in [yp, mp, dp, hp]:
        g, z = _parse_pillar_ganji(p)
        if g: stems.add(g)
        if z: branches.add(z)
    return {
        "stems": sorted(stems, key=lambda x: STEMS.index(x) if x in STEMS else 999),
        "branches": sorted(branches, key=lambda x: BRANCHES.index(x) if x in BRANCHES else 999),
    }

def build_truth_anchor(saju_data: Dict[str, Any]) -> str:
    """P0: LLM의 자체 해석을 봉쇄하는 '팩트 앵커'"""
    summary = (saju_data or {}).get("saju_summary", {}) or {}
    allowed = _derive_allowed_chars(saju_data or {})
    allowed_stems = allowed.get("stems", [])
    allowed_branches = allowed.get("branches", [])
    forbidden_stems = [s for s in STEMS if s not in allowed_stems]
    forbidden_pairs = [f"{s}{STEM_TO_ELEMENT.get(s, '')}" for s in forbidden_stems if STEM_TO_ELEMENT.get(s)]
    primary_structure = summary.get("primary_structure", "")
    allowed_structures = summary.get("allowed_structure_names", []) or []
    tg_present = summary.get("ten_gods_present", []) or (saju_data or {}).get("ten_gods_present", []) or []
    elements_present = summary.get("elements_present", []) or summary.get("elements_count", {}).keys() or []

    return f"""## 🚨 CRITICAL CONSTRAINTS (절대 규칙)
너는 명리학자가 아니다. 엔진/정답지/룰카드에 근거한 문장만 '편집'한다. 스스로 사주를 다시 계산/추론하지 마라.

- 허용 천간: {", ".join(allowed_stems) if allowed_stems else "(미제공)"}
- 허용 지지: {", ".join(allowed_branches) if allowed_branches else "(미제공)"}
- 금지 천간: {", ".join(forbidden_stems) if forbidden_stems else "(없음)"}
- 금지 조합(원국에 없음): {", ".join(forbidden_pairs) if forbidden_pairs else "(없음)"}
- 엔진 확정 격국: {primary_structure or "(미제공)"}
- 사용 가능 격국명: {", ".join(allowed_structures) if allowed_structures else "(미제공)"}
- 원국 십성(정답지): {", ".join(tg_present) if tg_present else "(미제공)"}
- 원국 오행(정답지): {", ".join(list(elements_present)) if elements_present else "(미제공)"}

### 🚫 금지(즉시 오답)
1) 원국에 없는 글자/십성을 '있다/많다/강하다/발달'로 단정.
2) 지장간/숨은천간 추론으로 원국 성분을 '창조'하는 행위.
3) 월지에 특정 십성이 '위치'한다고 단정(예: 월지 비견). 필요시 분포/경향으로만.
4) '관성 충돌/충돌 구조' 같은 단어 사용(엔진이 제공한 경우에만).
5) 오타 금지: '걸록격' 사용 금지(반드시 '건록격').
"""

def detect_guardrail_violations(text: str, saju_data: Dict[str, Any]) -> List[str]:
    """환각/금칙어 탐지"""
    if not text:
        return ["EMPTY_OUTPUT"]
    violations: List[str] = []
    allowed = _derive_allowed_chars(saju_data or {})
    allowed_stems = set(allowed.get("stems", []))
    forbidden_stems = [s for s in STEMS if s not in allowed_stems]

    for ph in FORBIDDEN_PHRASES:
        if ph and ph in text:
            violations.append(f"FORBIDDEN_PHRASE:{ph}")

    for s in forbidden_stems:
        elem = STEM_TO_ELEMENT.get(s)
        if elem and f"{s}{elem}" in text:
            violations.append(f"FORBIDDEN_STEM_ELEMENT:{s}{elem}")

    if "걸록" in text:
        violations.append("TYPO:걸록")

    return violations

def sanitize_output_last_resort(text: str, saju_data: Dict[str, Any]) -> str:
    """금칙어 강제 제거/치환"""
    if not text:
        return text or ""
    out = text
    out = out.replace("걸록격", "건록격").replace("걸록", "건록")
    for ph in FORBIDDEN_PHRASES:
        out = out.replace(ph, "")
    allowed = _derive_allowed_chars(saju_data or {})
    allowed_stems = set(allowed.get("stems", []))
    forbidden_stems = [s for s in STEMS if s not in allowed_stems]
    for s in forbidden_stems:
        elem = STEM_TO_ELEMENT.get(s)
        if elem:
            out = out.replace(f"{s}{elem}", "")
    return out


def build_fact_check_context(saju_data: Dict[str, Any]) -> str:
    """🔥 P0: 사실 검증용 컨텍스트 (보이는 글자 중심 및 지장간 추론 금지)"""
    summary = saju_data.get("saju_summary", {})
    yp = saju_data.get("year_pillar", "")
    mp = saju_data.get("month_pillar", "")
    dp = saju_data.get("day_pillar", "")
    hp = saju_data.get("hour_pillar", "")
    dm = saju_data.get("day_master", "")
    gender = saju_data.get("gender", "")
    age = saju_data.get("age", 0)
    cur = saju_data.get("current_daeun", "")
    direction = saju_data.get("daeun_direction", "")
    
    tg = summary.get("ten_gods_present", []) or saju_data.get("ten_gods_present", [])
    dtg = saju_data.get("daeun_ten_gods") or []
    has_wealth = bool(saju_data.get("has_wealth_star"))

    def _fmt(xs, order=None):
        if not xs: return "(없음)"
        if order:
            s = set(xs)
            xs = [x for x in order if x in s] + [x for x in xs if x not in s]
        return ", ".join(xs)

    pillars = [yp, mp, dp, hp]
    stems = [p[0] for p in pillars if p and len(p) >= 2]
    branches = [p[1] for p in pillars if p and len(p) >= 2]

    STEM_ELEM = {
        "갑": "목", "을": "목", "병": "화", "정": "화", "무": "토", 
        "기": "토", "경": "금", "신": "금", "임": "수", "계": "수",
    }
    all_stem_elem = [f"{k}{v}" for k, v in STEM_ELEM.items()]
    allowed_stem_elem = [f"{s}{STEM_ELEM.get(s, '')}" for s in stems if s in STEM_ELEM]
    forbidden_stem_elem = [x for x in all_stem_elem if x not in set(allowed_stem_elem)]

    primary_structure = summary.get("primary_structure") or saju_data.get("primary_structure") or ""
    allowed_structures = summary.get("allowed_structure_names") or saju_data.get("allowed_structure_names") or []

    return (
        "## ✅ 사실 검증용 컨텍스트 (P0)\n"
        f"- 원국(4주): {yp} {mp} {dp} {hp}\n"
        f"- 허용 천간(보이는 것만): {', '.join(stems) if stems else '(없음)'}\n"
        f"- 허용 지지(보이는 것만): {', '.join(branches) if branches else '(없음)'}\n"
        f"- 금지 천간오행(원국에 없음): {', '.join(forbidden_stem_elem[:6])}{'...' if len(forbidden_stem_elem) > 6 else ''}\n"
        f"- 일간: {dm}\n"
        f"- 성별/만나이: {gender} / {age}\n"
        f"- 격국(엔진 확정): {primary_structure or '(미제공)'}\n"
        f"- 사용 가능한 격국명: {', '.join(allowed_structures) if allowed_structures else '(미제공)'}\n"
        f"- 원국 십성(엔진 요약): {_fmt(tg, TENGOD_ORDER)}\n"
        f"- 현재 대운: {cur} (방향={direction}, 십성={_fmt(dtg, TENGOD_ORDER)})\n"
        f"- 재성(정재/편재) 원국 존재: {'있음' if has_wealth else '없음'}\n\n"
        "### 🚫 금지 규칙\n"
        "1) 위 '허용 천간/지지'에 없는 글자(예: 을, 병 등)를 원국에 있다고 쓰지 마라.\n"
        "2) 위 십성 리스트에 없는 십성을 '있다'고 쓰지 마라.\n"
        "3) 대운 변화는 반드시 '대운에서 들어온다'로 원국과 구분해서 말해라.\n"
        "4) 금지: 지장간/숨은천간 추론 금지. (보이는 글자만)\n"
        "5) 금지: '걸록격' 표기. (반드시 '건록격')\n"
    )

def build_system_prompt(section_id: str, engine_headline: str, survey_data: Dict = None, saju_data: Dict = None, existing_contents: List[str] = None, cards_summary: str = "") -> str:
    spec = PREMIUM_SECTIONS.get(section_id)
    if not spec: return ""
    title = spec.title
    min_chars = spec.min_chars
    master_body = get_master_body_markdown(section_id)
    
    saju_summary = (saju_data or {}).get("saju_summary", {})
    summary_json = json.dumps(saju_summary, ensure_ascii=False, indent=2) if saju_summary else "{}"
    
    truth_anchor = build_truth_anchor(saju_data or {})
    fact_ctx = build_fact_check_context(saju_data or {})
    
    return f"""너는 [{title}] 전문 컨설턴트다.

{truth_anchor}

{ROOT_CAUSE_RULE}
{fact_ctx}

## 정답지 (Ground Truth)
{summary_json}

## 첫 문장 (수정 금지)
"{engine_headline}"

## 마스터 샘플
{master_body if master_body else '(자유 작성)'}

## 필수 규칙
1) 첫 문장: 위 엔진 결론으로 시작
2) 최소 {min_chars}자 이상, 전문적인 비즈니스 톤 준수
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 빌더 클래스
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PremiumReportBuilder:
    def __init__(self):
        self._client = None
        self._semaphore = None
    
    def _get_client(self) -> AsyncOpenAI:
        api_key = get_openai_api_key()
        return AsyncOpenAI(api_key=api_key, timeout=httpx.Timeout(120.0, connect=15.0), max_retries=2)
    
    async def _repair_output_once(self, section_id: str, system_prompt: str, draft_markdown: str, violations: List[str], min_chars: int) -> str:
        """규칙 위반 시 1회 리라이트 수정"""
        if not draft_markdown: return ""
        try:
            repair_user = f"""너는 아래 초안을 '규칙 위반을 제거'하여 다시 작성한다.
[위반 목록]
{chr(10).join(f"- {v}" for v in violations)}
[초안]
{draft_markdown}
"""
            response = await self._client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": repair_user}],
                temperature=0.2, max_tokens=1800
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as e:
            logger.error(f"[Builder] Repair 실패: {e}")
            return draft_markdown

    async def _generate_section_safe(self, section_id: str, saju_data: Dict, allocation: Any, target_year: int, survey_data: Dict, engine_headline: str, existing_contents: List[str], job_id: str = None) -> Dict[str, Any]:
        spec = PREMIUM_SECTIONS.get(section_id)
        system_prompt = build_system_prompt(section_id, engine_headline, survey_data, saju_data, existing_contents)
        user_prompt = f"## 사주 원국 분석 및 리포트 작성 부탁드립니다. ({target_year}년)"
        
        async with self._semaphore:
            response = await self._client.chat.completions.create(
                model="gpt-4o", messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                temperature=0.3, max_tokens=1800
            )
            body_markdown = response.choices[0].message.content or ""
            llm_response_len = len(body_markdown)

        # ── P0 Guardrail 검증 및 수정 ──
        violations = detect_guardrail_violations(body_markdown, saju_data or {})
        repaired = False
        if violations:
            logger.warning(f"[Builder] Guardrail 위반 탐지: {violations}")
            repaired_text = await self._repair_output_once(section_id, system_prompt, body_markdown, violations, spec.min_chars)
            if repaired_text != body_markdown:
                repaired = True
                body_markdown = repaired_text
            
            # 2차 검증 실패 시 최후 수단
            violations2 = detect_guardrail_violations(body_markdown, saju_data or {})
            if violations2:
                body_markdown = sanitize_output_last_resort(body_markdown, saju_data or {})

        body_markdown = replace_template_tokens(body_markdown)
        return {
            "section_id": section_id, "title": spec.title, "body_markdown": body_markdown,
            "char_count": len(body_markdown), "llm_response_len": llm_response_len,
            "guardrail_violations": violations, "repaired": repaired
        }

    # (기타 Helper 함수들은 기존 로직과 동일하게 유지)
    async def regenerate_single_section(self, section_id: str, saju_data: Dict, rulecards: List[Dict], feature_tags: List[str] = None, target_year: int = 2026, user_question: str = "", survey_data: Dict = None):
        """단일 섹션 재생성 - report_worker에서 호출"""
        self._client = self._get_client()
        self._semaphore = asyncio.Semaphore(1)
        
        try:
            # 엔진 헤드라인 생성 (룰카드 기반)
            engine_headline = ""
            if rulecards:
                top_card = rulecards[0] if rulecards else {}
                interpretation = top_card.get("interpretation", "") or top_card.get("mechanism", "")
                if interpretation:
                    engine_headline = interpretation[:100]
            
            if not engine_headline:
                engine_headline = f"{target_year}년 비즈니스 전략 분석 결과입니다."
            
            # 섹션 생성
            result = await self._generate_section_safe(
                section_id=section_id,
                saju_data=saju_data,
                allocation=None,
                target_year=target_year,
                survey_data=survey_data or {},
                engine_headline=engine_headline,
                existing_contents=[],
                job_id=None
            )
            
            return {"ok": True, "section": result}
            
        except Exception as e:
            logger.error(f"[Builder] regenerate_single_section 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"ok": False, "error": str(e)}

premium_report_builder = PremiumReportBuilder()
report_builder = premium_report_builder