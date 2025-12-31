"""
SajuOS Premium Report Builder v10 - P0/P1 품질 정상화 패치
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 P0: SafeDict로 템플릿 변수 노출 방지 ({industry} 등)
🔥 P1: 섹션별 카드 격리 (topic 필터)
🔥 P1: engine_headline 서버 강제 보정 + 토큰 제거
🔥 P1: 마스터샘플 Hard Few-shot (복제 강제 모드)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import asyncio
import logging
import re
from typing import Dict, Any, List
from dataclasses import dataclass, field
from collections import UserDict

from openai import AsyncOpenAI
import httpx

from app.config import get_settings
from app.services.openai_key import get_openai_api_key
from app.services.terminology_mapper import sanitize_for_business
from app.services.job_store import job_store
from app.templates.master_samples import load_master_samples, get_master_body_markdown

logger = logging.getLogger(__name__)

MASTER_SAMPLES = load_master_samples("v1")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# P0: SafeDict - 템플릿 변수 노출 방지
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SafeDict(UserDict):
    def __missing__(self, key):
        return ""


def strip_template_tokens(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\{[a-zA-Z_]+\}", "", text)
    text = re.sub(r"\[/?ENGINE_HEADLINE\]", "", text)
    text = re.sub(r"\[/?MASTER_SAMPLE\]", "", text)
    return text.strip()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 섹션 정의 + Topic 필터
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class SectionSpec:
    id: str
    title: str
    pages: int
    max_cards: int
    min_cards: int
    min_chars: int
    validation_type: str = "standard"
    topic_filter: List[str] = field(default_factory=list)


PREMIUM_SECTIONS = {
    "biz_weather": SectionSpec(
        "biz_weather", "2026 비즈니스 전략 기상도", 2, 20, 8, 1500,
        topic_filter=["전체운", "종합", "일간", "성향", "기운", "운세"]
    ),
    "cashflow": SectionSpec(
        "cashflow", "자본 유동성 및 현금흐름 최적화", 5, 20, 10, 2500,
        topic_filter=["재물", "재성", "정재", "편재", "현금", "매출", "투자", "수입", "손재"]
    ),
    "positioning": SectionSpec(
        "positioning", "시장 포지셔닝 및 상품 확장 전략", 5, 20, 10, 2500,
        topic_filter=["사업", "창업", "경영", "관성", "정관", "편관", "시장", "상품"]
    ),
    "partnership": SectionSpec(
        "partnership", "조직 확장 및 파트너십 가이드", 4, 20, 8, 2000,
        topic_filter=["비겁", "비견", "겁재", "동업", "파트너", "협력", "인맥", "귀인", "팀"]
    ),
    "risks": SectionSpec(
        "risks", "주요 장애물 및 리스크 (2026)", 3, 15, 6, 1500,
        topic_filter=["리스크", "위험", "충", "형", "파", "손해", "장애", "번아웃"]
    ),
    "calendar_12m": SectionSpec(
        "calendar_12m", "12개월 비즈니스 스프린트 캘린더", 6, 15, 8, 2500, "calendar",
        topic_filter=["월운", "시기", "계절", "타이밍", "길일", "흉일", "대운", "세운"]
    ),
    "action_90d": SectionSpec(
        "action_90d", "향후 90일 매출 극대화 액션플랜", 5, 15, 6, 2000, "sprint",
        topic_filter=["실행", "액션", "계획", "목표", "식신", "상관", "식상", "성과"]
    ),
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 데이터 구조
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
        return 0.0
    
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
        pain_tags = {
            "lead": ["인맥", "귀인", "관성"],
            "retention": ["비겁", "비견", "겁재"],
            "conversion": ["재성", "정재", "식신생재"],
            "operations": ["인성", "정인", "관성"],
            "funding": ["재성", "재고", "투자"],
            "marketing": ["식상", "상관", "인맥"],
        }
        for tag in pain_tags.get(pain, []):
            if tag.lower() in card_text:
                score += 2.0
    
    return score


def allocate_rulecards_to_section(
    all_cards: List[Dict], 
    section_id: str, 
    max_cards: int, 
    used_ids: set,
    survey_data: Dict = None
) -> SectionRuleCardAllocation:
    
    scored = []
    for card in all_cards:
        cid = card.get("id", card.get("_id", ""))
        if cid in used_ids:
            continue
        score = score_card_for_section(card, section_id, survey_data)
        scored.append((score, card))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    allocated = [card for _, card in scored[:max_cards]]
    
    ids, lines = [], []
    for card in allocated:
        cid = card.get("id", card.get("_id", ""))
        ids.append(cid)
        interp = sanitize_for_business((card.get("interpretation") or "")[:200])
        lines.append(f"[{cid}] {card.get('topic', '')} | {interp}")
    
    logger.info(f"[CardAlloc] section={section_id} | scored={len(scored)} | allocated={len(ids)}")
    
    return SectionRuleCardAllocation(section_id, len(ids), ids, "\n".join(lines), allocated)


def extract_engine_headline(cards: List[Dict]) -> str:
    if not cards:
        return ""
    
    top_card = cards[0]
    interp = top_card.get("interpretation") or top_card.get("content", {}).get("interpretation", "")
    if not interp:
        interp = top_card.get("mechanism") or ""
    
    interp = sanitize_for_business(interp)
    sentences = re.split(r"[.。!?]", interp)
    first = sentences[0].strip() if sentences else interp[:100]
    first = strip_template_tokens(first)
    
    return first if first else interp[:100]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Root Cause Rule 프롬프트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ROOT_CAUSE_RULE = """## 🧠 Root Cause Rule (절대규칙)
- 사주/룰카드(=원인)가 결론이다. 설문(=증상)은 결론이 아니다.
- 섹션의 첫 문장은 반드시 엔진이 확정한 결론으로 시작한다.
- 설문(painPoint/goal/industry)은 "현장에서 어떻게 드러났는지"만 설명한다.
- 금지: "고객님이 설문에서 ~라고 하셔서" 같은 서술.
"""


def build_system_prompt(
    section_id: str, 
    engine_headline: str, 
    survey_data: Dict = None, 
    existing_contents: List[str] = None,
    cards_summary: str = ""
) -> str:
    
    spec = PREMIUM_SECTIONS.get(section_id)
    if not spec:
        logger.error(f"[Builder] Invalid section_id: {section_id}")
        return ""
    
    title = spec.title
    min_chars = spec.min_chars
    master_body = get_master_body_markdown(section_id)
    
    industry = (survey_data or {}).get("industry", "") or "미입력"
    painPoint = (survey_data or {}).get("painPoint", "") or "미입력"
    businessGoal = (survey_data or {}).get("businessGoal", "") or "미입력"
    
    survey_context = f"""
## 📋 설문 데이터 (증상으로만 활용)
- 업종: {industry}
- 고민: {painPoint}
- 목표: {businessGoal}
"""
    
    existing_block = ""
    if existing_contents and len(existing_contents) > 0:
        existing_block = f"""
## ⚠️ 이전 섹션 내용 (반복 금지)
{chr(10).join(existing_contents[-2:])}
"""
    
    return f"""너는 [{title}] 전문 컨설턴트다.

{ROOT_CAUSE_RULE}

## 🚨 첫 문장 (수정 금지)
아래 문장으로 반드시 시작해야 한다:

"{engine_headline}"

## 📌 마스터 샘플 (구조 복제)
아래 샘플의 구조/헤더/순서를 따라라:

{master_body if master_body else '(자유 작성)'}

## 🧩 주입된 룰카드
{cards_summary if cards_summary else '(없음)'}
{survey_context}
{existing_block}

## 출력 규칙
1) 첫 문장: 위 엔진 결론으로 시작
2) 원인(사주) → 증상(설문) 연결
3) 리스크 2개
4) 액션 3개 (D+14/D+30/D+60)
5) 체크리스트 7개
6) 최소 {min_chars}자
7) 한국어로만 작성
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
    
    async def build_premium_report(
        self,
        saju_data: Dict,
        rulecards: List[Dict],
        feature_tags: List[str] = None,
        target_year: int = 2026,
        user_question: str = "",
        name: str = "고객",
        job_id: str = None,
        survey_data: Dict = None,
        mode: str = "premium"
    ):
        self._semaphore = asyncio.Semaphore(2)
        self._client = self._get_client()
        
        if job_id:
            await job_store.start_job(job_id)
        
        used_card_ids = set()
        results = []
        existing_contents = []
        
        for sid in PREMIUM_SECTIONS.keys():
            spec = PREMIUM_SECTIONS[sid]
            alloc = allocate_rulecards_to_section(
                rulecards, sid, spec.max_cards, used_card_ids, survey_data
            )
            used_card_ids.update(alloc.allocated_card_ids)
            
            engine_headline = extract_engine_headline(alloc.cards)
            
            logger.info(f"[Builder] section={sid} | cards={alloc.allocated_count} | headline={engine_headline[:50] if engine_headline else 'NONE'}")
            
            try:
                result = await self._generate_section(
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
                if body:
                    existing_contents.append(body[:300])
                
                results.append(result)
                
                if job_id:
                    await job_store.section_done(job_id, sid, len(body))
                    
            except Exception as e:
                logger.exception(f"[Builder] 섹션 생성 실패: {sid} | {e}")
                if job_id:
                    await job_store.fail_job(job_id, str(e)[:500])
                raise
        
        if job_id:
            await job_store.complete_job(job_id, {"sections": len(results)})
        
        return {"status": "success", "sections": results}
    
    async def _generate_section(
        self,
        section_id: str,
        saju_data: Dict,
        allocation: SectionRuleCardAllocation,
        target_year: int,
        survey_data: Dict,
        engine_headline: str,
        existing_contents: List[str],
        job_id: str = None
    ) -> Dict[str, Any]:
        
        cards_summary = self._build_cards_summary(allocation.cards[:5])
        
        system_prompt = build_system_prompt(
            section_id=section_id,
            engine_headline=engine_headline,
            survey_data=survey_data,
            existing_contents=existing_contents,
            cards_summary=cards_summary
        )
        
        user_prompt = self._build_user_prompt(saju_data, allocation, target_year)
        
        async with self._semaphore:
            try:
                response = await self._client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=4000
                )
                body_markdown = response.choices[0].message.content or ""
            except Exception as e:
                logger.error(f"[Builder] GPT 호출 실패: {e}")
                raise
        
        body_markdown = self._enforce_engine_headline(body_markdown, engine_headline)
        body_markdown = strip_template_tokens(body_markdown)
        
        leaked = self._check_template_leaks(body_markdown)
        if leaked:
            logger.error(f"[Builder] ⚠️ 템플릿 토큰 누출: {leaked}")
        
        return {
            "section_id": section_id,
            "title": PREMIUM_SECTIONS[section_id].title,
            "body_markdown": body_markdown,
            "engine_headline": engine_headline,
            "rulecard_ids": allocation.allocated_card_ids,
            "char_count": len(body_markdown)
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
        
        card_lines = []
        for c in allocation.cards[:10]:
            interp = (c.get("interpretation") or "")[:100]
            card_lines.append(f"- [{c.get('id', '')}] {c.get('topic', '')} | {interp}")
        
        return f"""## 클라이언트 사주 원국
| 구분 | 간지 |
|------|------|
| 년주 | {year_pillar} |
| 월주 | {month_pillar} |
| 일주 | {day_pillar} |
| 시주 | {hour_pillar} |

- 일간: {day_master}
- 분석 기준년도: {target_year}년

## 룰카드
{chr(10).join(card_lines) if card_lines else '(없음)'}

위 정보를 바탕으로 작성하세요.
"""
    
    def _enforce_engine_headline(self, body_markdown: str, engine_headline: str) -> str:
        if not engine_headline:
            return body_markdown
        
        headline = engine_headline.strip()
        body_stripped = body_markdown.lstrip()
        
        if body_stripped.startswith(headline):
            return body_markdown
        
        if len(body_stripped) > 50 and headline[:30] in body_stripped[:100]:
            return body_markdown
        
        logger.warning(f"[Builder] engine_headline 강제 삽입")
        return f"{headline}\n\n{body_stripped}"
    
    def _check_template_leaks(self, text: str) -> List[str]:
        leaked = []
        patterns = [r"\{industry\}", r"\{painPoint\}", r"\{engine_headline\}", 
                    r"\{goal\}", r"\{revenue\}", r"\{time\}"]
        for p in patterns:
            if re.search(p, text):
                leaked.append(p)
        return leaked
    
    async def regenerate_single_section(
        self,
        section_id: str,
        saju_data: Dict,
        rulecards: List[Dict],
        feature_tags: List[str] = None,
        target_year: int = 2026,
        user_question: str = "",
        survey_data: Dict = None
    ):
        self._client = self._get_client()
        self._semaphore = asyncio.Semaphore(1)
        
        spec = PREMIUM_SECTIONS.get(section_id)
        if not spec:
            logger.error(f"[Builder] Invalid section_id: {section_id}")
            raise ValueError(f"Invalid section_id: {section_id}")
        
        alloc = allocate_rulecards_to_section(rulecards, section_id, spec.max_cards, set(), survey_data)
        engine_headline = extract_engine_headline(alloc.cards)
        
        result = await self._generate_section(
            section_id=section_id,
            saju_data=saju_data,
            allocation=alloc,
            target_year=target_year,
            survey_data=survey_data,
            engine_headline=engine_headline,
            existing_contents=[]
        )
        
        return {"success": True, "section": result}


premium_report_builder = PremiumReportBuilder()
report_builder = premium_report_builder
