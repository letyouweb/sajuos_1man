"""
SajuOS Premium Report Builder v12 - P0 빈 섹션 절대 금지
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 P0-1: 카드 0개 → LLM 호출 X, 폴백 텍스트 즉시 반환
🔥 P0-2: 섹션 ID 정합성 (exec,money,business,team,health,calendar,sprint)
🔥 P0-3: 토큰 "치환" (삭제 X) - {industry}→"해당 업종"
🔥 P0-4: 생성 실패 원인 로그 4개 필수
🔥 P0-5: 지장간 추론 금지 및 '보이는 글자' 중심 검증 강화
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import asyncio
import json
import logging
import re
from typing import Dict, Any, List
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


# 🔥 P0-2: 합의된 section_id 고정 (exec, money, business, team, health, calendar, sprint)
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
# 데이터 구조 및 헬퍼
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class SectionRuleCardAllocation:
    section_id: str
    allocated_count: int
    allocated_card_ids: List[str]
    context_text: str
    cards: List[Dict[str, Any]] = field(default_factory=list)


def score_card_for_section(card: Dict, section_id: str, survey_data: Dict = None) -> float:
    spec = PREMIUM_SECTIONS.get(section_id)
    if not spec:
        return 1.0
    score = 1.0
    topic = (card.get("topic") or "").lower()
    mechanism = (card.get("mechanism") or "").lower()
    tags = " ".join(card.get("tags") or []).lower()
    card_text = f"{topic} {mechanism} {tags}"
    for tf in spec.topic_filter:
        if tf.lower() in card_text:
            score += 3.0
    if survey_data:
        pain = (survey_data.get("painPoint") or "").lower()
        pain_tags = {"lead": ["인맥", "귀인"], "retention": ["비겁", "비견"], "conversion": ["재성", "정재"], "funding": ["재성", "투자"]}
        for tag in pain_tags.get(pain, []):
            if tag.lower() in card_text:
                score += 2.0
    return score


def allocate_rulecards_to_section(all_cards: List[Dict], section_id: str, max_cards: int, used_ids: set, survey_data: Dict = None) -> SectionRuleCardAllocation:
    scored = []
    for card in all_cards:
        cid = card.get("id", card.get("_id", ""))
        if cid in used_ids:
            continue
        score = score_card_for_section(card, section_id, survey_data)
        scored.append((score, card))
    scored.sort(key=lambda x: x[0], reverse=True)
    
    filtered = [(s, c) for s, c in scored if s > 1.0]
    if not filtered:
        logger.warning(f"[CardAlloc] section={section_id} topic_filter hit=0 → fallback")
        if scored:
            filtered = scored[:max_cards]
        elif all_cards:
            fallback = [c for c in all_cards if c.get("id", c.get("_id", "")) not in used_ids][:max_cards]
            filtered = [(1.0, c) for c in fallback]
    
    allocated = [card for _, card in filtered[:max_cards]]
    ids, lines = [], []
    for card in allocated:
        cid = card.get("id", card.get("_id", ""))
        ids.append(cid)
        interp = sanitize_for_business((card.get("interpretation") or "")[:200])
        lines.append(f"[{cid}] {card.get('topic', '')} | {interp}")
    
    logger.info(f"[CardAlloc] section={section_id} | scored={len(scored)} | filtered={len(filtered)} | allocated={len(ids)}")
    return SectionRuleCardAllocation(section_id, len(ids), ids, "\n".join(lines), allocated)


def extract_engine_headline(cards: List[Dict]) -> str:
    if not cards:
        return ""
    top_card = cards[0]
    interp = top_card.get("interpretation") or top_card.get("content", {}).get("interpretation", "") or top_card.get("mechanism") or ""
    interp = sanitize_for_business(interp)
    sentences = re.split(r"[.。!?]", interp)
    first = sentences[0].strip() if sentences else interp[:100]
    first = re.sub(r"\{[a-zA-Z_]+\}", "", first)
    return first if first else interp[:100]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 프롬프트 구성 유틸리티
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ROOT_CAUSE_RULE = """## 🧠 Root Cause Rule (절대규칙)
- 사주/룰카드(=원인)가 결론이다. 설문(=증상)은 결론이 아니다.
- 섹션의 첫 문장은 반드시 엔진이 확정한 결론으로 시작한다.
- 금지: "고객님이 설문에서 ~라고 하셨으니" 같은 서술.
"""

TENGOD_ORDER = ["비견","겁재","식신","상관","편재","정재","편관","정관","편인","정인"]


def build_fact_check_context(saju_data: Dict[str, Any]) -> str:
    """🔥 P0: 사실 검증용 컨텍스트 (보이는 글자 중심 및 지장간 추론 금지)"""
    summary = saju_data.get("saju_summary", {})
    yp = saju_data.get("year_pillar","")
    mp = saju_data.get("month_pillar","")
    dp = saju_data.get("day_pillar","")
    hp = saju_data.get("hour_pillar","")
    dm = saju_data.get("day_master","")
    gender = saju_data.get("gender","")
    age = saju_data.get("age",0)
    cur = saju_data.get("current_daeun","")
    direction = saju_data.get("daeun_direction","")
    
    # 십성 정보 (엔진 정답지 우선)
    tg = summary.get("ten_gods_present", []) or saju_data.get("ten_gods_present", [])
    dtg = saju_data.get("daeun_ten_gods") or []
    elems = saju_data.get("elements_present") or []
    has_wealth = bool(saju_data.get("has_wealth_star"))

    def _fmt(xs, order=None):
        if not xs:
            return "(없음)"
        if order:
            s = set(xs)
            xs = [x for x in order if x in s] + [x for x in xs if x not in s]
        return ", ".join(xs)

    # 🔥 P0: '보이는 글자'만 허용 (지장간/숨은천간 추론 금지)
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
        "4) 금지: 지장간/숨은천간을 근거로 '병화/을목이 많다' 같은 문장 작성 금지. (보이는 글자만)\n"
        "5) 금지: '걸록격' 표기. (반드시 '건록격'으로 표기)\n"
        "6) 금지: 월지에 특정 십성이 '위치'한다고 단정(예: 월지 비견 등). 필요시 분포로만 설명.\n"
    )

def build_system_prompt(section_id: str, engine_headline: str, survey_data: Dict = None, saju_data: Dict = None, existing_contents: List[str] = None, cards_summary: str = "") -> str:
    spec = PREMIUM_SECTIONS.get(section_id)
    if not spec:
        return ""
    title = spec.title
    min_chars = spec.min_chars
    master_body = get_master_body_markdown(section_id)
    industry = (survey_data or {}).get("industry", "미입력")
    painPoint = (survey_data or {}).get("painPoint", "미입력")
    businessGoal = (survey_data or {}).get("businessGoal", "미입력")
    
    saju_summary = (saju_data or {}).get("saju_summary", {})
    summary_json = json.dumps(saju_summary, ensure_ascii=False, indent=2) if saju_summary else "{}"
    
    data_compliance_rule = f"""
## 🔴 데이터 준수 철칙 (위반시 실패)
1. 아래 원국 통계(정답지)에 없는 십성/오행을 "있다"고 주장하지 마라.
2. 원국에 재성(정재/편재)이 0개면, "재성이 있다"고 말하지 마라.
3. 원국에 식상(식신/상관)이 0개면, "식상이 있다"고 말하지 마라.
4. 대운에서 들어오는 기운은 반드시 "대운에서 ~가 들어온다"로 명시하라.
5. Allowed_structure_names 외의 격국 이름을 사용하지 마라.
"""
    
    fact_ctx = build_fact_check_context(saju_data or {})
    survey_context = f"\n## 설문 (증상)\n- 업종: {industry}\n- 고민: {painPoint}\n- 목표: {businessGoal}\n"
    
    existing_block = ""
    if existing_contents:
        existing_block = f"\n## 이전 섹션 (반복 금지)\n{chr(10).join(existing_contents[-2:])}\n"
    
    return f"""너는 [{title}] 전문 컨설턴트다.

{ROOT_CAUSE_RULE}
{data_compliance_rule}
{fact_ctx}

## 정답지 (Ground Truth)
{summary_json}

## 첫 문장 (수정 금지)
"{engine_headline}"

## 마스터 샘플
{master_body if master_body else '(자유 작성)'}

## 룰카드 요약
{cards_summary if cards_summary else '(없음)'}
{survey_context}
{existing_block}

## 필수 규칙
1) 첫 문장: 위 엔진 결론으로 시작
2) 리스크 2개, 액션 3개, 체크리스트 7개 포함
3) 최소 {min_chars}자 이상, 전문적인 비즈니스 톤 준수
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
    
    async def build_premium_report(self, saju_data: Dict, rulecards: List[Dict], feature_tags: List[str] = None, target_year: int = 2026, user_question: str = "", name: str = "고객", job_id: str = None, survey_data: Dict = None, mode: str = "premium"):
        self._semaphore = asyncio.Semaphore(2)
        self._client = self._get_client()
        if job_id:
            await job_store.start_job(job_id)
        
        used_card_ids = set()
        results = []
        existing_contents = []
        
        for sid in PREMIUM_SECTIONS.keys():
            spec = PREMIUM_SECTIONS[sid]
            alloc = allocate_rulecards_to_section(rulecards, sid, spec.max_cards, used_card_ids, survey_data)
            used_card_ids.update(alloc.allocated_card_ids)
            engine_headline = extract_engine_headline(alloc.cards)
            
            # 🔥 P0-4: 생성 실패 원인 로그 필수
            headline_len = len(engine_headline) if engine_headline else 0
            logger.info(f"[Builder] 📊 section={sid} | 1.allocated_count={alloc.allocated_count} | 2.headline_len={headline_len}")
            
            try:
                result = await self._generate_section_safe(
                    section_id=sid,
                    saju_data=saju_data,
                    allocation=alloc,
                    target_year=target_year,
                    survey_data=survey_data,
                    engine_headline=engine_headline,
                    existing_contents=existing_contents,
                    job_id=job_id
                )
                
                body = result.get("body_markdown", "")
                body_len = len(body)
                
                # 🔥 P0-4: LLM 응답 및 최종 길이 로그
                logger.info(f"[Builder] 📊 section={sid} | 3.llm_response_len={result.get('llm_response_len', 0)} | 4.final_body_len={body_len}")
                
                if body:
                    existing_contents.append(body[:300])
                results.append(result)
                
                if job_id:
                    await job_store.section_done(job_id, sid, body_len)
                    
            except Exception as e:
                logger.exception(f"[Builder] ❌ 섹션 생성 실패: {sid}")
                fallback_body = generate_fallback_body(sid, engine_headline, survey_data)
                results.append({
                    "section_id": sid, "title": spec.title, "body_markdown": fallback_body,
                    "engine_headline": engine_headline or spec.fallback_headline,
                    "rulecard_ids": [], "char_count": len(fallback_body), "is_fallback": True
                })
        
        if job_id:
            await job_store.complete_job(job_id, {"sections": len(results)})
        return {"status": "success", "sections": results}
    
    async def _generate_section_safe(self, section_id: str, saju_data: Dict, allocation: SectionRuleCardAllocation, target_year: int, survey_data: Dict, engine_headline: str, existing_contents: List[str], job_id: str = None) -> Dict[str, Any]:
        """🔥 P0-1: 빈 섹션 절대 금지 - 카드 0개면 폴백"""
        spec = PREMIUM_SECTIONS.get(section_id)
        if not spec:
            raise ValueError(f"Invalid section_id: {section_id}")
        
        # 🔥 P0-1(A): 카드 0개면 즉시 폴백
        if allocation.allocated_count == 0:
            logger.warning(f"[Builder] section={section_id} | cards=0 → fallback")
            fallback_body = generate_fallback_body(section_id, engine_headline, survey_data)
            return {
                "section_id": section_id, "title": spec.title, "body_markdown": fallback_body,
                "engine_headline": engine_headline or spec.fallback_headline, "rulecard_ids": [],
                "char_count": len(fallback_body), "llm_response_len": 0, "is_fallback": True
            }
        
        cards_summary = self._build_cards_summary(allocation.cards[:5])
        system_prompt = build_system_prompt(
            section_id=section_id, engine_headline=engine_headline or spec.fallback_headline,
            survey_data=survey_data, saju_data=saju_data, existing_contents=existing_contents,
            cards_summary=cards_summary
        )
        user_prompt = self._build_user_prompt(saju_data, allocation, target_year)
        
        body_markdown = ""
        llm_response_len = 0
        
        async with self._semaphore:
            try:
                # 🔥 P0: temperature 0.3 및 max_tokens 1800 최적화
                response = await self._client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=1800
                )
                body_markdown = response.choices[0].message.content or ""
                llm_response_len = len(body_markdown)
            except Exception as e:
                logger.error(f"[Builder] GPT 호출 실패: {section_id} | {e}")
                body_markdown = generate_fallback_body(section_id, engine_headline, survey_data)
        
        if len(body_markdown) < 200:
            body_markdown = generate_fallback_body(section_id, engine_headline, survey_data)
        
        body_markdown = self._enforce_engine_headline(body_markdown, engine_headline or spec.fallback_headline)
        leaked = check_template_leaks(body_markdown, f"section={section_id}")
        body_markdown = replace_template_tokens(body_markdown)
        
        return {
            "section_id": section_id, "title": spec.title, "body_markdown": body_markdown,
            "engine_headline": engine_headline or spec.fallback_headline,
            "rulecard_ids": allocation.allocated_card_ids, "char_count": len(body_markdown),
            "llm_response_len": llm_response_len, "leaked_tokens": leaked
        }
    
    def _build_cards_summary(self, cards: List[Dict]) -> str:
        lines = []
        for i, c in enumerate(cards[:5], 1):
            interp = (c.get("interpretation") or "")[:80]
            lines.append(f"{i}. [{c.get('topic', '')}] {interp}")
        return "\n".join(lines) if lines else "(없음)"
    
    def _build_user_prompt(self, saju_data: Dict, allocation: SectionRuleCardAllocation, target_year: int) -> str:
        year_pillar = saju_data.get("year_pillar", "-")
        month_pillar = saju_data.get("month_pillar", "-")
        day_pillar = saju_data.get("day_pillar", "-")
        hour_pillar = saju_data.get("hour_pillar", "-") or "미입력"
        day_master = saju_data.get("day_master", "")
        card_lines = [f"- [{c.get('id', '')}] {c.get('topic', '')} | {(c.get('interpretation') or '')[:100]}" for c in allocation.cards[:10]]
        return f"""## 사주 원국
| 년주 | 월주 | 일주 | 시주 |
|------|------|------|------|
| {year_pillar} | {month_pillar} | {day_pillar} | {hour_pillar} |

- 일간: {day_master}
- 분석년도: {target_year}년

## 배정된 룰카드
{chr(10).join(card_lines) if card_lines else '(없음)'}

위 원국 팩트와 룰카드를 근거로 비즈니스 인사이트를 작성하세요.
"""
    
    def _enforce_engine_headline(self, body_markdown: str, engine_headline: str) -> str:
        if not engine_headline: return body_markdown
        headline = engine_headline.strip()
        body_stripped = body_markdown.lstrip()
        if body_stripped.startswith(headline) or (len(body_stripped) > 50 and headline[:30] in body_stripped[:100]):
            return body_markdown
        return f"{headline}\n\n{body_stripped}"
    
    async def regenerate_single_section(self, section_id: str, saju_data: Dict, rulecards: List[Dict], feature_tags: List[str] = None, target_year: int = 2026, user_question: str = "", survey_data: Dict = None):
        self._client = self._get_client()
        self._semaphore = asyncio.Semaphore(1)
        spec = PREMIUM_SECTIONS.get(section_id)
        if not spec: raise ValueError(f"Invalid section_id: {section_id}")
        alloc = allocate_rulecards_to_section(rulecards, section_id, spec.max_cards, set(), survey_data)
        engine_headline = extract_engine_headline(alloc.cards)
        result = await self._generate_section_safe(section_id=section_id, saju_data=saju_data, allocation=alloc, target_year=target_year, survey_data=survey_data, engine_headline=engine_headline, existing_contents=[])
        return {"success": True, "section": result}

premium_report_builder = PremiumReportBuilder()
report_builder = premium_report_builder