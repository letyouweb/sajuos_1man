"""
SajuOS Premium Report Builder v9 - P0 Root Cause Rule
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 P0 핵심:
1) Root Cause Rule 프롬프트 최상단 삽입
2) ENGINE_HEADLINE 고정 (Top1 룰카드 interpretation)
3) 마스터 샘플 few-shot 삽입
4) 서버 강제 보정 (engine_headline으로 시작하지 않으면 prepend)
5) 섹션 중복 방지 (existing_contents 전달)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import asyncio
import logging
import time
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from openai import AsyncOpenAI
import httpx

from app.config import get_settings
from app.services.openai_key import get_openai_api_key
from app.services.terminology_mapper import sanitize_for_business
from app.services.job_store import job_store
from app.services.quality_gate import quality_gate
from app.templates.master_samples import load_master_samples, get_master_body_markdown, SECTION_ID_MAP

logger = logging.getLogger(__name__)

# 마스터 샘플 로드 (캐시)
MASTER_SAMPLES = load_master_samples("v1")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 섹션 정의
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


PREMIUM_SECTIONS = {
    "biz_weather": SectionSpec("biz_weather", "2026 비즈니스 전략 기상도", 2, 15, 8, 1500),
    "cashflow": SectionSpec("cashflow", "자본 유동성 및 현금흐름 최적화", 5, 18, 10, 2500),
    "positioning": SectionSpec("positioning", "시장 포지셔닝 및 상품 확장 전략", 5, 18, 10, 2500),
    "partnership": SectionSpec("partnership", "조직 확장 및 파트너십 가이드", 4, 15, 8, 2000),
    "risks": SectionSpec("risks", "주요 장애물 및 리스크 (2026)", 3, 12, 6, 1500),
    "calendar_12m": SectionSpec("calendar_12m", "12개월 비즈니스 스프린트 캘린더", 6, 12, 8, 2500, "calendar"),
    "action_90d": SectionSpec("action_90d", "향후 90일 매출 극대화 액션플랜", 5, 10, 6, 2000, "sprint"),
}

SECTION_WEIGHT_TAGS = {
    "biz_weather": ["전체운", "종합", "핵심", "요약", "일간", "성향"],
    "cashflow": ["정재", "편재", "재성", "재물", "현금", "매출", "투자", "손실"],
    "positioning": ["정관", "편관", "사업", "창업", "경영", "리더십", "계약", "거래"],
    "partnership": ["비겁", "비견", "겁재", "동업", "파트너", "직원", "관계", "협력"],
    "risks": ["관성", "충", "형", "파", "리스크", "장애", "손해", "위험"],
    "calendar_12m": ["월운", "시기", "계절", "타이밍", "길일", "흉일", "절기"],
    "action_90d": ["실행", "액션", "계획", "목표", "KPI", "마일스톤", "주간"],
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 데이터 구조
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class SectionRuleCardAllocation:
    section_id: str
    allocated_count: int
    allocated_card_ids: List[str]
    context_text: str
    cards: List[Dict[str, Any]] = field(default_factory=list)


def allocate_rulecards_to_section(all_cards: List[Dict], section_id: str, max_cards: int, used_ids: set) -> SectionRuleCardAllocation:
    section_tags = SECTION_WEIGHT_TAGS.get(section_id, [])
    scored = []
    for card in all_cards:
        cid = card.get("id", card.get("_id", ""))
        if cid in used_ids:
            continue
        card_text = f"{card.get('topic', '')} {card.get('mechanism', '')} {card.get('tags', [])}".lower()
        score = sum(2.0 for st in section_tags if st.lower() in card_text)
        scored.append((score, card))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    allocated = [card for _, card in scored[:max_cards]]
    
    ids, lines = [], []
    for card in allocated:
        cid = card.get("id", card.get("_id", ""))
        ids.append(cid)
        interp = sanitize_for_business((card.get("interpretation") or "")[:200])
        lines.append(f"[{cid}] {card.get('topic', '')} | {interp}")
    
    return SectionRuleCardAllocation(section_id, len(ids), ids, "\n".join(lines), allocated)


def extract_engine_headline(cards: List[Dict]) -> str:
    """Top1 룰카드의 interpretation에서 첫 문장 추출"""
    if not cards:
        return ""
    top_card = cards[0]
    interp = top_card.get("interpretation") or top_card.get("content", {}).get("interpretation", "")
    if not interp:
        interp = top_card.get("mechanism") or ""
    
    # 첫 문장 추출
    interp = sanitize_for_business(interp)
    sentences = re.split(r"[.。!?]", interp)
    first = sentences[0].strip() if sentences else interp[:100]
    return first if first else interp[:100]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. P0 핵심: Root Cause Rule 프롬프트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ROOT_CAUSE_RULE = """## 🧠 Root Cause Rule (P0, 절대규칙)
- 사주/룰카드(=원인)가 결론이다. 설문(=증상)은 결론이 아니다.
- 섹션의 첫 문장은 반드시 엔진이 확정한 결론(ENGINE_HEADLINE)로 시작한다.
- 설문(painPoint/goal/industry/time)은 "현장에서 어떻게 드러났는지"만 설명한다.
- 금지: "고객님이 설문에서 ~라고 하셔서(=원인)" 같은 서술.
- 허용: "원국의 구조(원인) 때문에, {industry} 현장에서 {painPoint}로 드러난다(증상)."
"""


def build_system_prompt(section_id: str, engine_headline: str, survey_data: Dict = None, existing_contents: List[str] = None) -> str:
    """P0 시스템 프롬프트 생성"""
    spec = PREMIUM_SECTIONS.get(section_id)
    title = spec.title if spec else section_id
    min_chars = spec.min_chars if spec else 2000
    
    # 마스터 샘플 body_markdown
    master_body = get_master_body_markdown(section_id)
    
    # 설문 컨텍스트
    survey_context = ""
    if survey_data:
        survey_context = f"""
## 📋 설문 데이터 (증상, 원인 아님)
- industry: {survey_data.get('industry', '미입력')}
- painPoint: {survey_data.get('painPoint', '미입력')}
- businessGoal: {survey_data.get('businessGoal', '미입력')}
- decisionStyle: {survey_data.get('decisionStyle', '미입력')}
"""
    
    # 이전 섹션 중복 방지
    existing_block = ""
    if existing_contents:
        existing_block = f"""
## ⚠️ 섹션 중복 금지
아래는 이전 섹션에서 이미 다룬 내용입니다. 절대 반복하지 마세요:
{chr(10).join(existing_contents[-3:])}
"""
    
    return f"""{ROOT_CAUSE_RULE}

## 🚨 ENGINE_HEADLINE (수정/희석/부정 금지)
아래 문장은 엔진이 확정한 결론이다. 너는 이 문장을 수정/부정/희석할 수 없다.
body_markdown은 반드시 이 문장으로 시작해야 한다.

[ENGINE_HEADLINE]
{engine_headline}
[/ENGINE_HEADLINE]

## 📌 섹션 마스터 샘플 (구성/톤 참고)
아래는 이 섹션의 모범 답안이다. 구조와 톤을 따르되 내용은 클라이언트 사주에 맞게 작성하라.

```markdown
{master_body if master_body else '(마스터 샘플 없음)'}
```
{survey_context}
{existing_block}

## 출력 포맷 강제
1) 결정 문장 (3줄) - 반드시 ENGINE_HEADLINE으로 시작
2) 원인(사주/룰카드) → 증상(설문) 연결
3) 리스크 2개 (각각: 트리거/피해/조기경보)
4) 액션 3개 (D+14 / D+30 / D+60, 수치 포함)
5) 체크리스트 7개

## 섹션 정보
- 섹션: {title}
- 최소 글자 수: {min_chars}자
- 반드시 한국어로만 작성
- 비즈니스 용어(매출, 수익, ROI) 중심으로 작성 (취업 용어 금지)
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 빌더 클래스
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PremiumReportBuilder:
    def __init__(self):
        self._client = None
        self._semaphore = None
    
    def _get_client(self) -> AsyncOpenAI:
        settings = get_settings()
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
        existing_contents = []  # 🔥 P0: 중복 방지용
        
        for sid in PREMIUM_SECTIONS.keys():
            spec = PREMIUM_SECTIONS[sid]
            alloc = allocate_rulecards_to_section(rulecards, sid, spec.max_cards, used_card_ids)
            used_card_ids.update(alloc.allocated_card_ids)
            
            # 🔥 P0: Top1 카드에서 engine_headline 추출
            engine_headline = extract_engine_headline(alloc.cards)
            
            logger.info(f"[Builder] section={sid} | cards={alloc.allocated_count} | headline_len={len(engine_headline)}")
            
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
                
                # 🔥 P0: 다음 섹션 중복 방지용 저장
                body = result.get("body_markdown", "")
                if body:
                    existing_contents.append(body[:500])
                
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
        """섹션 생성 + engine_headline 강제 보정"""
        
        system_prompt = build_system_prompt(
            section_id=section_id,
            engine_headline=engine_headline,
            survey_data=survey_data,
            existing_contents=existing_contents
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
        
        # 🔥 P0: 서버 강제 보정 - engine_headline으로 시작하지 않으면 prepend
        body_markdown = self._enforce_engine_headline(body_markdown, engine_headline)
        
        return {
            "section_id": section_id,
            "title": PREMIUM_SECTIONS[section_id].title,
            "body_markdown": body_markdown,
            "engine_headline": engine_headline,
            "rulecard_ids": allocation.allocated_card_ids,
            "char_count": len(body_markdown)
        }
    
    def _build_user_prompt(self, saju_data: Dict, allocation: SectionRuleCardAllocation, target_year: int) -> str:
        year_pillar = saju_data.get("year_pillar", "-")
        month_pillar = saju_data.get("month_pillar", "-")
        day_pillar = saju_data.get("day_pillar", "-")
        hour_pillar = saju_data.get("hour_pillar", "-") or "미입력"
        day_master = saju_data.get("day_master", "")
        
        card_lines = []
        for c in allocation.cards[:20]:
            cid = c.get("id", "")
            interp = (c.get("interpretation") or "")[:100]
            card_lines.append(f"- [{cid}] {c.get('topic', '')} | {interp}")
        
        return f"""## 클라이언트 사주 원국
| 구분 | 간지 |
|------|------|
| 년주 | {year_pillar} |
| 월주 | {month_pillar} |
| 일주 | {day_pillar} |
| 시주 | {hour_pillar} |

- 일간(日干): {day_master}
- 분석 기준년도: {target_year}년

## 주입된 룰카드
{chr(10).join(card_lines) if card_lines else '(없음)'}

위 정보를 바탕으로 섹션 내용을 작성하세요.
"""
    
    def _enforce_engine_headline(self, body_markdown: str, engine_headline: str) -> str:
        """🔥 P0: engine_headline으로 시작하지 않으면 강제 prepend"""
        if not engine_headline:
            return body_markdown
        
        headline = engine_headline.strip()
        body_stripped = body_markdown.lstrip()
        
        # 이미 시작하면 그대로
        if body_stripped.startswith(headline):
            return body_markdown
        
        # headline 앞 50자 비교 (유사하면 통과)
        if len(body_stripped) > 50 and headline[:30] in body_stripped[:100]:
            return body_markdown
        
        # 강제 prepend
        logger.warning(f"[Builder] ⚠️ engine_headline 강제 삽입")
        return f"{headline}\n\n{body_stripped}"
    
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
            raise ValueError(f"Invalid section_id: {section_id}")
        
        alloc = allocate_rulecards_to_section(rulecards, section_id, spec.max_cards, set())
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
