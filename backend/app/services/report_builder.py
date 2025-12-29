"""
SajuOS Premium Report Builder v7
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 v7 핵심 개선:
1) 품질 게이트 3중 필터 (금지어/구체성/중복)
2) 7문항 설문 기반 개인화 컨텍스트 주입
3) 룰카드 스코어링 엔진 (사업가형 50태그 기반)
4) 검증 실패 시 자동 재생성 + 품질 피드백
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import asyncio
import logging
import time
import json
import random
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from openai import AsyncOpenAI, APIError, RateLimitError, APIConnectionError, APITimeoutError
import httpx

from app.config import get_settings
from app.services.openai_key import get_openai_api_key
from app.services.terminology_mapper import (
    sanitize_for_business,
    get_business_prompt_rules,
)
from app.services.job_store import job_store, JobStore

# 🔥 v7: 품질 게이트 + 설문 + 스코어링 모듈
from app.services.quality_gate import (
    quality_gate, 
    QualityReport, 
    get_quality_improvement_prompt,
    clean_banned_phrases
)
from app.services.survey_intake import (
    SurveyResponse, 
    survey_to_prompt_context
)
from app.services.rulecard_scorer import (
    rulecard_scorer, 
    SectionCards
)

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 가드레일: 한국어 고정 + 비즈니스 금칙어
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 금칙어 (취업/커리어 템플릿)
BANNED_CAREER_TERMS = [
    "자격증", "취업", "이력서", "채용", "면접", "포트폴리오", "합격",
    "job application", "resume", "certification", "interview prep",
    "career change", "job search", "job hunting", "linkedin",
    "취업 준비", "자격 시험", "입사", "퇴사", "구직", "인턴"
]

# 비즈니스 필수 용어 (최소 3개 이상 포함 필요)
REQUIRED_BUSINESS_TERMS = [
    "매출", "수익", "현금", "투자", "ROI", "KPI", "전환", "리드",
    "고객", "시장", "전략", "실행", "목표", "성과", "분기", "월별"
]

# 🔥 P0-3: 영어 Allowlist (비즈니스 약어 - en_ratio 계산에서 제외)
ENGLISH_ALLOWLIST = {
    "ai", "okr", "kpi", "pdf", "sns", "url", "api", "db", "sql",
    "roi", "b2b", "b2c", "saas", "crm", "erp", "hr", "ceo", "cto", "cfo",
    "mvp", "poc", "qa", "ui", "ux", "seo", "sem", "ppc", "cpa", "cpc",
    "ltv", "cac", "mrr", "arr", "gmv", "aov", "dau", "mau", "wau",
    "pm", "pd", "pr", "ir", "ipo", "m&a", "nda", "mou", "rnd",
    "it", "iot", "ml", "gpt", "llm", "devops", "ci", "cd",
}


def english_ratio(text: str) -> float:
    """영문자 비율 계산 (Allowlist 제외)"""
    if not text:
        return 0.0
    
    # 1) 영어 단어 추출
    en_words = re.findall(r"[A-Za-z]+", text)
    
    # 2) Allowlist 제외한 영어 글자 수 계산
    en_chars = 0
    for word in en_words:
        if word.lower() not in ENGLISH_ALLOWLIST:
            en_chars += len(word)
    
    # 3) 공백 제외한 전체 길이
    total_chars = len(re.sub(r"\s", "", text))
    
    return en_chars / max(total_chars, 1)


def validate_language_and_topic(text: str, section_id: str) -> Tuple[bool, List[str]]:
    """
    가드레일 검증: 한국어 고정 + 비즈니스 금칙어
    Returns: (is_valid, error_codes)
    """
    errors = []
    
    if not text or len(text) < 100:
        errors.append("CONTENT_TOO_SHORT")
        return False, errors
    
    # 1) 한국어 고정 (영문 비율 5% 초과 시 실패)
    en_ratio = english_ratio(text)
    if en_ratio > 0.05:
        errors.append(f"LANGUAGE_NOT_KOREAN (en_ratio={en_ratio:.1%})")
        logger.warning(f"[Guardrail] {section_id}: 영어 비율 {en_ratio:.1%} > 5%")
    
    # 2) 비즈니스 보고서에서 커리어 템플릿 금지
    text_lower = text.lower()
    for banned in BANNED_CAREER_TERMS:
        if banned.lower() in text_lower:
            errors.append(f"BANNED_CAREER_TEMPLATE ({banned})")
            logger.warning(f"[Guardrail] {section_id}: 금칙어 발견 '{banned}'")
            break  # 하나만 찾으면 충분
    
    # 3) 비즈니스 필수 용어 최소 3개 포함 확인
    found_business_terms = sum(1 for term in REQUIRED_BUSINESS_TERMS if term in text)
    if found_business_terms < 3:
        errors.append(f"MISSING_BUSINESS_CONTEXT (found={found_business_terms})")
        logger.warning(f"[Guardrail] {section_id}: 비즈니스 용어 부족 ({found_business_terms}/3)")
    
    is_valid = len(errors) == 0
    return is_valid, errors


def validate_rulecard_usage(rulecard_ids: List[str], section_id: str, min_required: int = 8) -> Tuple[bool, str]:
    """RuleCard 최소 사용량 검증"""
    count = len(rulecard_ids) if rulecard_ids else 0
    if count < min_required:
        return False, f"RULECARD_INSUFFICIENT ({count}/{min_required})"
    return True, ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 사업가형 핵심 태그 50개
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BUSINESS_OWNER_CORE_TAGS = [
    "정재", "편재", "재성", "재물", "부", "현금", "매출", "수익", "투자", 
    "자산", "유동성", "손실", "파산", "횡재", "도둑",
    "정관", "편관", "관성", "직장", "사업", "창업", "경영", "리더십", 
    "승진", "이직", "독립", "프리랜서", "계약", "거래", "파트너",
    "식신", "상관", "식상", "실행", "생산", "창작", "마케팅", "혁신", 
    "출력", "성과",
    "비겁", "비견", "겁재", "동업", "경쟁",
    "인성", "정인", "편인", "학습", "브랜드"
]

SECTION_WEIGHT_TAGS: Dict[str, List[str]] = {
    "exec": ["전체운", "종합", "핵심", "요약", "일간", "성향"],
    "money": ["정재", "편재", "재성", "재물", "현금", "매출", "투자", "손실"],
    "business": ["정관", "편관", "사업", "창업", "경영", "리더십", "계약", "거래"],
    "team": ["비겁", "비견", "겁재", "동업", "파트너", "직원", "관계", "협력"],
    "health": ["건강", "에너지", "스트레스", "번아웃", "체력", "질병", "휴식"],
    "calendar": ["월운", "시기", "계절", "타이밍", "길일", "흉일", "절기"],
    "sprint": ["실행", "액션", "계획", "목표", "KPI", "마일스톤", "주간"]
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 섹션 정의
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class SectionSpec:
    id: str
    title: str
    pages: int
    max_cards: int
    min_cards: int  # 최소 RuleCard 수
    min_chars: int
    validation_type: str = "standard"


PREMIUM_SECTIONS: Dict[str, SectionSpec] = {
    "exec": SectionSpec(id="exec", title="2026년, 내 장사 설계도", pages=2, max_cards=15, min_cards=8, min_chars=1500, validation_type="standard"),
    "money": SectionSpec(id="money", title="현금흐름 & 수익구조", pages=5, max_cards=18, min_cards=10, min_chars=2500, validation_type="standard"),
    "business": SectionSpec(id="business", title="사업 전략 & 확장 타이밍", pages=5, max_cards=18, min_cards=10, min_chars=2500, validation_type="standard"),
    "team": SectionSpec(id="team", title="협력자 & 파트너 리스크", pages=4, max_cards=15, min_cards=8, min_chars=2000, validation_type="standard"),
    "health": SectionSpec(id="health", title="체력 & 번아웃 관리", pages=3, max_cards=12, min_cards=6, min_chars=1500, validation_type="standard"),
    "calendar": SectionSpec(id="calendar", title="12개월 캘린더", pages=6, max_cards=12, min_cards=8, min_chars=2500, validation_type="calendar"),
    "sprint": SectionSpec(id="sprint", title="90일 스프린트 플랜", pages=5, max_cards=10, min_cards=6, min_chars=2000, validation_type="sprint")
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. JSON Schema (Structured Outputs)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STANDARD_SECTION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "standard_section",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "diagnosis": {
                    "type": "object",
                    "properties": {
                        "current_state": {"type": "string"},
                        "key_issues": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["current_state", "key_issues"],
                    "additionalProperties": False
                },
                "hypotheses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "statement": {"type": "string"},
                            "confidence": {"type": "string"},
                            "evidence": {"type": "string"}
                        },
                        "required": ["id", "statement", "confidence", "evidence"],
                        "additionalProperties": False
                    }
                },
                "strategy_options": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "pros": {"type": "array", "items": {"type": "string"}},
                            "cons": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["id", "name", "description", "pros", "cons"],
                        "additionalProperties": False
                    }
                },
                "recommended_strategy": {
                    "type": "object",
                    "properties": {
                        "selected_option": {"type": "string"},
                        "rationale": {"type": "string"},
                        "execution_plan": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "week": {"type": "integer"},
                                    "focus": {"type": "string"},
                                    "actions": {"type": "array", "items": {"type": "string"}}
                                },
                                "required": ["week", "focus", "actions"],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required": ["selected_option", "rationale", "execution_plan"],
                    "additionalProperties": False
                },
                "kpis": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "metric": {"type": "string"},
                            "target": {"type": "string"},
                            "current": {"type": "string"},
                            "measurement": {"type": "string"}
                        },
                        "required": ["metric", "target", "current", "measurement"],
                        "additionalProperties": False
                    }
                },
                "risks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "risk": {"type": "string"},
                            "probability": {"type": "string"},
                            "impact": {"type": "string"},
                            "mitigation": {"type": "string"}
                        },
                        "required": ["risk", "probability", "impact", "mitigation"],
                        "additionalProperties": False
                    }
                },
                "body_markdown": {"type": "string"},
                "confidence": {"type": "string"}
            },
            "required": ["title", "diagnosis", "hypotheses", "strategy_options", 
                        "recommended_strategy", "kpis", "risks", "body_markdown", "confidence"],
            "additionalProperties": False
        }
    }
}

# 🔥 Sprint 섹션: 비즈니스 전용 (리드→전환→LTV→자동화)
SPRINT_SECTION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "sprint_section",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "mission_statement": {"type": "string"},
                "phase_1_offer": {
                    "type": "object",
                    "properties": {
                        "weeks": {"type": "string"},
                        "theme": {"type": "string"},
                        "goals": {"type": "array", "items": {"type": "string"}},
                        "deliverables": {"type": "array", "items": {"type": "string"}},
                        "kpis": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["weeks", "theme", "goals", "deliverables", "kpis"],
                    "additionalProperties": False
                },
                "phase_2_funnel": {
                    "type": "object",
                    "properties": {
                        "weeks": {"type": "string"},
                        "theme": {"type": "string"},
                        "goals": {"type": "array", "items": {"type": "string"}},
                        "deliverables": {"type": "array", "items": {"type": "string"}},
                        "kpis": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["weeks", "theme", "goals", "deliverables", "kpis"],
                    "additionalProperties": False
                },
                "phase_3_content": {
                    "type": "object",
                    "properties": {
                        "weeks": {"type": "string"},
                        "theme": {"type": "string"},
                        "goals": {"type": "array", "items": {"type": "string"}},
                        "deliverables": {"type": "array", "items": {"type": "string"}},
                        "kpis": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["weeks", "theme", "goals", "deliverables", "kpis"],
                    "additionalProperties": False
                },
                "phase_4_automation": {
                    "type": "object",
                    "properties": {
                        "weeks": {"type": "string"},
                        "theme": {"type": "string"},
                        "goals": {"type": "array", "items": {"type": "string"}},
                        "deliverables": {"type": "array", "items": {"type": "string"}},
                        "kpis": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["weeks", "theme", "goals", "deliverables", "kpis"],
                    "additionalProperties": False
                },
                "milestones": {
                    "type": "object",
                    "properties": {
                        "day_30": {
                            "type": "object",
                            "properties": {
                                "goal": {"type": "string"},
                                "success_criteria": {"type": "string"},
                                "revenue_target": {"type": "string"}
                            },
                            "required": ["goal", "success_criteria", "revenue_target"],
                            "additionalProperties": False
                        },
                        "day_60": {
                            "type": "object",
                            "properties": {
                                "goal": {"type": "string"},
                                "success_criteria": {"type": "string"},
                                "revenue_target": {"type": "string"}
                            },
                            "required": ["goal", "success_criteria", "revenue_target"],
                            "additionalProperties": False
                        },
                        "day_90": {
                            "type": "object",
                            "properties": {
                                "goal": {"type": "string"},
                                "success_criteria": {"type": "string"},
                                "revenue_target": {"type": "string"}
                            },
                            "required": ["goal", "success_criteria", "revenue_target"],
                            "additionalProperties": False
                        }
                    },
                    "required": ["day_30", "day_60", "day_90"],
                    "additionalProperties": False
                },
                "risk_scenarios": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "scenario": {"type": "string"},
                            "trigger": {"type": "string"},
                            "pivot_plan": {"type": "string"}
                        },
                        "required": ["scenario", "trigger", "pivot_plan"],
                        "additionalProperties": False
                    }
                },
                "body_markdown": {"type": "string"},
                "confidence": {"type": "string"}
            },
            "required": ["title", "mission_statement", "phase_1_offer", "phase_2_funnel",
                        "phase_3_content", "phase_4_automation", "milestones", 
                        "risk_scenarios", "body_markdown", "confidence"],
            "additionalProperties": False
        }
    }
}

# 🔥🔥🔥 P0: 장애물/리스크 섹션 전용 스키마 (team, health, business용)
RISK_SECTION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "risk_section",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "diagnosis": {
                    "type": "object",
                    "properties": {
                        "core_problem": {"type": "string"},
                        "root_cause": {"type": "string"},
                        "why_now": {"type": "string"}
                    },
                    "required": ["core_problem", "root_cause", "why_now"],
                    "additionalProperties": False
                },
                "hypotheses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "hypothesis": {"type": "string"},
                            "evidence": {"type": "string"},
                            "test": {"type": "string"}
                        },
                        "required": ["hypothesis", "evidence", "test"],
                        "additionalProperties": False
                    }
                },
                "strategy_options": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "pros": {"type": "string"},
                            "cons": {"type": "string"},
                            "when_to_choose": {"type": "string"}
                        },
                        "required": ["name", "pros", "cons", "when_to_choose"],
                        "additionalProperties": False
                    }
                },
                "recommended_strategy": {
                    "type": "object",
                    "properties": {
                        "strategy": {"type": "string"},
                        "reason": {"type": "string"},
                        "execution_steps": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["strategy", "reason", "execution_steps"],
                    "additionalProperties": False
                },
                "kpis": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "metric": {"type": "string"},
                            "target": {"type": "string"},
                            "current": {"type": "string"},
                            "measurement": {"type": "string"}
                        },
                        "required": ["metric", "target", "current", "measurement"],
                        "additionalProperties": False
                    }
                },
                "risks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "risk": {"type": "string"},
                            "probability": {"type": "string"},
                            "impact": {"type": "string"},
                            "mitigation": {"type": "string"}
                        },
                        "required": ["risk", "probability", "impact", "mitigation"],
                        "additionalProperties": False
                    }
                },
                "body_markdown": {"type": "string"},
                "confidence": {"type": "string"}
            },
            "required": ["title", "diagnosis", "hypotheses", "strategy_options", 
                        "recommended_strategy", "kpis", "risks", "body_markdown", "confidence"],
            "additionalProperties": False
        }
    }
}

# Calendar 섹션: 월별 현금흐름 포함
CALENDAR_SECTION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "calendar_section",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "annual_theme": {"type": "string"},
                "annual_revenue_projection": {"type": "string"},
                "monthly_plans": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "month": {"type": "integer"},
                            "month_name": {"type": "string"},
                            "theme": {"type": "string"},
                            "energy_level": {"type": "string"},
                            "revenue_index": {"type": "integer"},
                            "key_focus": {"type": "string"},
                            "recommended_actions": {"type": "array", "items": {"type": "string"}},
                            "cautions": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["month", "month_name", "theme", "energy_level", 
                                    "revenue_index", "key_focus", "recommended_actions", "cautions"],
                        "additionalProperties": False
                    }
                },
                "quarterly_milestones": {
                    "type": "object",
                    "properties": {
                        "Q1": {"type": "object", "properties": {"theme": {"type": "string"}, "milestone": {"type": "string"}, "revenue_target": {"type": "string"}}, "required": ["theme", "milestone", "revenue_target"], "additionalProperties": False},
                        "Q2": {"type": "object", "properties": {"theme": {"type": "string"}, "milestone": {"type": "string"}, "revenue_target": {"type": "string"}}, "required": ["theme", "milestone", "revenue_target"], "additionalProperties": False},
                        "Q3": {"type": "object", "properties": {"theme": {"type": "string"}, "milestone": {"type": "string"}, "revenue_target": {"type": "string"}}, "required": ["theme", "milestone", "revenue_target"], "additionalProperties": False},
                        "Q4": {"type": "object", "properties": {"theme": {"type": "string"}, "milestone": {"type": "string"}, "revenue_target": {"type": "string"}}, "required": ["theme", "milestone", "revenue_target"], "additionalProperties": False}
                    },
                    "required": ["Q1", "Q2", "Q3", "Q4"],
                    "additionalProperties": False
                },
                "peak_months": {"type": "array", "items": {"type": "string"}},
                "risk_months": {"type": "array", "items": {"type": "string"}},
                "body_markdown": {"type": "string"},
                "confidence": {"type": "string"}
            },
            "required": ["title", "annual_theme", "annual_revenue_projection", "monthly_plans", 
                        "quarterly_milestones", "peak_months", "risk_months", "body_markdown", "confidence"],
            "additionalProperties": False
        }
    }
}


def get_section_schema(section_id: str) -> dict:
    spec = PREMIUM_SECTIONS.get(section_id)
    if not spec:
        return STANDARD_SECTION_SCHEMA
    if spec.validation_type == "sprint":
        return SPRINT_SECTION_SCHEMA
    elif spec.validation_type == "calendar":
        return CALENDAR_SECTION_SCHEMA
    # 🔥 P0: 장애물/리스크 섹션용 스키마 (team, health, business)
    elif section_id in ["team", "health", "business"]:
        return RISK_SECTION_SCHEMA
    return STANDARD_SECTION_SCHEMA


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. 전역 Top-100 RuleCard 선별
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class GlobalRuleCardSelection:
    original_pool_count: int
    top100_count: int
    top100_cards: List[Dict[str, Any]]
    top100_card_ids: List[str]


def score_rulecard_global(card: Dict[str, Any], feature_tags: List[str]) -> float:
    score = 0.0
    card_text = f"{card.get('topic', '')} {' '.join(card.get('tags', []))} {card.get('mechanism', '')} {card.get('action', '')}"
    card_text_lower = card_text.lower()
    
    for ft in feature_tags:
        if ft.lower() in card_text_lower:
            score += 3.0
    
    for core_tag in BUSINESS_OWNER_CORE_TAGS:
        if core_tag.lower() in card_text_lower:
            score += 1.0
    
    return score


def select_global_top100(all_cards: List[Dict[str, Any]], feature_tags: List[str], top_limit: int = 100) -> GlobalRuleCardSelection:
    original_pool = len(all_cards)
    if original_pool == 0:
        return GlobalRuleCardSelection(0, 0, [], [])
    
    scored = [(score_rulecard_global(card, feature_tags), card) for card in all_cards]
    scored.sort(key=lambda x: x[0], reverse=True)
    top100 = [card for _, card in scored[:top_limit]]
    top100_ids = [card.get("id", card.get("_id", f"card_{i}")) for i, card in enumerate(top100)]
    
    logger.info(f"[GlobalTop100] Pool={original_pool} → Top100={len(top100)}")
    return GlobalRuleCardSelection(original_pool, len(top100), top100, top100_ids)


@dataclass
class SectionRuleCardAllocation:
    section_id: str
    allocated_count: int
    allocated_card_ids: List[str]
    context_text: str


def allocate_rulecards_to_section(
    top100_cards: List[Dict[str, Any]],
    section_id: str,
    max_cards: int,
    already_used_ids: set
) -> SectionRuleCardAllocation:
    section_tags = SECTION_WEIGHT_TAGS.get(section_id, [])
    
    scored = []
    for card in top100_cards:
        cid = card.get("id", card.get("_id", ""))
        if cid in already_used_ids:
            continue
        
        card_text = f"{card.get('topic', '')} {card.get('mechanism', '')} {card.get('action', '')}".lower()
        section_score = sum(2.0 for st in section_tags if st.lower() in card_text)
        scored.append((section_score, card))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    allocated = [card for _, card in scored[:max_cards]]
    
    lines = []
    ids = []
    for card in allocated:
        cid = card.get("id", card.get("_id", f"card_{len(ids)}"))
        ids.append(cid)
        topic = card.get("topic", "")
        mechanism = sanitize_for_business((card.get("mechanism") or "")[:100])
        action = sanitize_for_business((card.get("action") or "")[:100])
        line = f"[{cid}] {topic}"
        if mechanism:
            line += f" → {mechanism}"
        if action:
            line += f" | 액션: {action}"
        lines.append(line)
    
    context = "\n".join(lines) if lines else "분석 데이터 없음"
    return SectionRuleCardAllocation(section_id, len(ids), ids, context)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. 프롬프트 생성 (비즈니스 가드레일 강화)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_section_system_prompt(section_id: str, target_year: int, survey_context: str = "") -> str:
    """🔥 P0 Pivot: ONE-MAN BUSINESS 공통 프롬프트 (RC-#### 내부 메모 금지)"""
    spec = PREMIUM_SECTIONS.get(section_id)
    if not spec:
        spec = PREMIUM_SECTIONS["exec"]
    
    # 🔥🔥🔥 P0 최상위 규칙: 인과관계 분석 원칙 (1순위)
    cause_effect_principle = """
## 🧠 인과관계 분석 원칙 (Cause-Effect Principle v2) - 최상위 규칙!

### 1. 설문(Survey) = 직접 원인(Direct Cause)
- 업종/매출구간/병목/목표/가용시간은 "현재 발생 중인 비즈니스 현상의 1차 원인"이다.
- 섹션의 결론·액션·수치는 반드시 survey_data에서 시작하라.
- ⚠️ 설문 문장을 그대로 반복하지 말고, KPI/매츠릭/수치/기간으로 변환하라.

### 2. 사주(Pillars) = 증폭기/반복 패턴(Amplifier & Pattern)
- 사주는 원인을 대체하지 않는다.
- "왜 이 문제가 반복되는지", "어떤 리스크가 커지는지", "어떤 실행 리듬/우선순위가 필요한지"를 설명하는 **2차 원인(구조적 배경)**으로만 사용한다.
- 사주 용어는 최소화하고(전체 단어 10% 이하) 비즈니스 언어로 치환한다.

### 3. 해결책(Solution) = 처방(Prescription)
- 해결책은 '설문 문장 반복'이 아니라, KPI(수치) + 기간(언제까지) + 행동(무엇을) + 리스크 대비(무엇을 막나)로 작성한다.

**❗ 금지 예시:**
- "리드 확보가 필요합니다" → ❌ (설문 반복)
- "매출 성장을 위해 노력해야 합니다" → ❌ (추상어)

**✅ 올바른 예시:**
- "D+14까지 인스타그램 리스 광고 3개 테스트 → CPL 3000원 이하 채널 1개 선정 → D+30 리드 50건 확보" → ✅
- "2월 매출 800만원 → 3월 1200만원 목표, 신규 고객 15명 확보, 객단가 20% 인상" → ✅
"""
    
    # 🔥🔥🔥 P0 핵심: 섹션 서술 구조 강제 (3단계)
    section_structure_rule = """
## 📋 섹션 서술 구조 (3단계 강제)

모든 섹션은 아래 구조를 반드시 따라야 한다:

### 1단계. 【사업 DNA 진단】 (사주→비즈니스 치환, 10% 이하)
- 사주 4주를 비즈니스 언어로 번역하여 2~3문장으로 진단.
- 예: "일간 입수(壬水)는 유연한 적응력과 네트워킹 강점을 의미합니다. 다만 2026년에는..."

### 2단계. 【현실 병목 진단】 (survey_data 기반 KPI/기간/상황)
- survey_data의 업종/병목/매출/목표/시간을 KPI 관점으로 분해.
- painPoint를 그대로 반복하지 말고, 발생 메커니즘을 설명.
- 예: "lead 병목 → 유입수/전환율/단가/재방문/리드 품질로 분해"

### 3단계. 【돌파 전략】 (수치/기간/행동 + 리스크 2개 + 체크리스트)
- KPI 목표: 예) "월매출 1500만원"
- 기간: 예) "D+30까지", "1분기 내"
- 행동: 예) "인스타 리스 광고 3개 테스트"
- 리스크 2개: 예) "광고비 과다 지출 시 현금흐름 악화"
- 체크리스트: D+1, D+7, D+30 시점별 할 일
"""
    
    # 🔥🔥🔥 P0 핵심: 리스크/장애물 섹션 전용 규칙
    risk_analysis_rule = ""
    if section_id in ["team", "health", "business"]:
        risk_analysis_rule = """
## ⚠️ 리스크 및 장애물 분석 규칙 (Survey-first)

**반드시 준수:**

1. painPoint를 "그대로 반복"하지 말고, 발생 메커니즘을 KPI 관점으로 분해하라.
   - lead → 유입수/전환율/단가/재방문/리드 품질로 분해
   - retention → 재구매율/칠드레이트/LTV/고객불만으로 분해
   - operations → 처리시간/실수율/자동화율/병목프로세스로 분해

2. **첫 문장은 반드시 아래 템플릿:**
   "현재 장애물은 {painPoint} 자체가 아니라, {industry}에서 {time} 제약 하에 {revenue} 상태에서 흔히 터지는 (KPI/프로세스/계약/번아웃 중 1개) 구조 문제다."

3. 사주는 2~3문장 이내로 "악화 조건/실행 리듬"만 보정:
   "이 문제는 2026년에 (사주적 리듬)과 겹치면 지연 비용이 커진다" 수준으로만.

4. **사주로만 우기는 방향 절대 금지:**
   - "형충파해로 인해 주의해야 합니다" → ❌
   - "재성이 약하므로 돈을 조심해야 합니다" → ❌
   - "현재 월매출 800만원에서 재구매율 15%는 업계 평균 25% 대비 낮음 → D+30까지 25%로 끌어올리면 월 120만원 추가 수익" → ✅

## 📋 JSON 출력 필수 필드 (RISK_SECTION_SCHEMA)

장애물/리스크 섹션은 아래 JSON 구조를 **정확히** 따라야 한다:

- `title`: "⚠️ 주요 장애물 및 리스크 (2026)"
- `diagnosis`: {core_problem, root_cause, why_now} — 단일 원인 진단
- `hypotheses`: [{hypothesis, evidence, test}] — 가설 2개
- `strategy_options`: [{name, pros, cons, when_to_choose}] — 옵션 3개
- `recommended_strategy`: {strategy, reason, execution_steps[]} — Action 1/2/3
- `kpis`: [{metric, target, current, measurement}] — KPI 3개
- `risks`: [{risk, probability, impact, mitigation}] — 리스크 2개
- `body_markdown`: 결정 문장 3줄 → 단일 원인 → 리스크 2개 → 액션 3개 → 체크리스트
- `confidence`: "중~상 (설문 입력값 기반)"

**body_markdown 필수 구조:**
```markdown
## 결정 문장 (3줄)
- 핵심 인사이트 1줄
- 핵심 인사이트 2줄
- 핵심 인사이트 3줄

## 장애물의 정체 (단일 원인)
[diagnosis.core_problem 요약]

## 리스크 (2개)
1) [risk 1]
2) [risk 2]

## 액션플랜 (3개, 순서 강제)
### Action 1 (D+14): [제목]
- 목표: ...
- 기준: ...

### Action 2 (D+30): [제목]
...

### Action 3 (D+60): [제목]
...

## 체크리스트
- [ ] 이번 주 중단한 행동 3가지?
- [ ] 가장 큰 매출 행동 1개?
- [ ] 30일 뒤 KPI 1개 개선됐는가?
```
"""
    
    # 🔥🔥🔥 P0 핵심: 사주 용어 강제 포함 프롬프트
    saju_interpretation_rule = """
## 🔮 사주 기반 비즈니스 해석 규칙 (필수)

⚠️ **리포트 시작 시 반드시 아래 형식으로 시작하라:**

```
【당신의 사업 DNA 분석】

📌 일간(Day Master): [ex: 입수(壬水)] = 비즈니스 스타일 핵심
   → 비즈니스 해석: [ex: "유연한 적응력, 네트워킹 강점, 현금흐름 관리 능력"]

📌 4주 구조 비즈니스 해석:
   - 년주(Year): [비즈니스 기반/배경]
   - 월주(Month): [사업 실행 스타일]
   - 일주(Day): [본질적 경영 성향]
   - 시주(Hour): [미래 성장 방향]

🎯 2026년 핵심 전략 포인트:
   [ex: "재성(財星)이 강한 해 → 매출 확장에 집중", "인성(印星) 활성화 → 브랜드/콘텐츠 강화"]
```

**사주 용어 → 비즈니스 언어 변환 규칙:**
- 재성(財星) → 매출/수익/현금흐름
- 관성(官星) → 조직력/시스템/규모 확장
- 인성(印星) → 브랜드/콘텐츠/학습 능력
- 식상(食傷) → 창의력/마케팅/상품 개발
- 비겁(比劫)/비견·겁재 → 파트너/협업/경쟁/인적 네트워크

### 표현 규칙 (절대 위반 금지)
- **사주 용어 비중은 전체 단어의 10% 이하**로 제한하고, 나머지 90%는 비즈니스 언어(매출/현금흐름/리드/전환/단가/재구매/계약/리스크/번아웃)로 치환하라.
- “운이 좋다/노력해라/성장/균형/마음가짐/기회” 같은 추상 문구는 금지한다. 대신 **수치·기간·행동**으로 쓴다.
- 내부 코드(RC-####)나 룰카드 ID는 절대 노출하지 말고, 저장 직전 sanitize를 가정하더라도 **출력에서 먼저 금지**한다.
- 비겱(比劫) → 팀 운영/파트너십/경쟁
- 신강(身強) → 실행력/주도성/리더십
- 신약(身弱) → 협업 필요/외부 자원 활용/시스템화
- 길신(吉神) → 기회/호재/확장 타이밍
- 흡신(凶神) → 리스크/주의 시기/보수적 접근

**⚠️ 주의:** 사주 용어를 그대로 노출하지 말고, 반드시 비즈니스 언어로 변환하되 "근거: 사주 분석"을 명시하라.
"""
    
    # 🔥 P0: ONE-MAN BUSINESS 공통 프롬프트 (추상어 금지, 액션 중심)
    base_prompt = f"""당신은 1인 자영업자를 위한 비즈니스 리포트를 작성하는 전략 컨설턴트입니다.

{cause_effect_principle}

{section_structure_rule}

{risk_analysis_rule}

{saju_interpretation_rule}

## 📅 분석 기준: {target_year}년

{survey_context if survey_context else ""}

## ⚠️ 필수 준수사항 (위반 시 재생성)

1. **RC-#### 절대 노출 금지**: RC-1234 같은 내부 메모는 raw_json에만. 최종 마크다운/프론트 표시에 절대 포함 금지.

2. **추상어 금지**: "노력하세요", "성장의 시기", "균형을 유지", "좋은 운" 같은 일반론 금지.
   - 대신 구체적 수치/기간/액션만 작성.
   - 예: "3월까지 월매출 500만원 달성" (O), "성장의 시기" (X)

3. **출력 포맷 강제**:
   ```markdown
   ## 결론 (3줄)
   - 핵심 인사이트 1줄
   - 핵심 인사이트 2줄
   - 핵심 인사이트 3줄

   ## 액션플랜 (3개, 기간/수치/효과 명시)
   ### 액션 1: [제목]
   - 기간: D+7 ~ D+30
   - 목표 수치: 월매출 300만원
   - 예상 효과: 고객 확보 20명

   ### 액션 2: [제목]
   - 기간: ...

   ### 액션 3: [제목]
   - 기간: ...

   ## 리스크 (2개)
   1. [리스크 1]
   2. [리스크 2]

   ## 체크리스트
   - [ ] D+1: ...
   - [ ] D+7: ...
   - [ ] D+30: ...
   ```

4. **한국어 전용**: 영어 사용 금지 (KPI, ROI, MVP 같은 약어는 OK).

5. **취업/커리어 용어 금지**: 이력서, 면접, 자격증, 채용, 포트폴리오 등 절대 사용 금지.

6. **비즈니스 필수 용어**: 매출, 수익, 현금, 투자, 고객, 전환, 리드 중 최소 5개 포함.
"""

    # Sprint 섹션 특화
    if section_id == "sprint":
        return base_prompt + f"""

## 🎯 90일 스프린트 필수 구조

**Phase 1 (Week 1-3): 오퍼 확정**
- 핵심 상품 1개 확정
- 가격 결정
- 타겟 고객 정의

**Phase 2 (Week 4-6): 유입 채널**
- 채널 1개 선택 (SNS/블로그/광고)
- 랜딩페이지 제작
- 첫 리드 10명 확보

**Phase 3 (Week 7-9): 콘텐츠 시스템**
- 주 3회 콘텐츠 발행
- 이메일 시퀀스 구축
- 리타겟팅 세팅

**Phase 4 (Week 10-12): 자동화**
- CRM 세팅
- 결제 자동화
- KPI 대시보드

JSON 스키마에 맞춰 정확히 응답하세요.
"""

    # 일반 섹션
    return base_prompt + f"""

## 이 섹션: {spec.title}

최소 {spec.min_chars}자 이상 작성하되, 위 출력 포맷을 준수하세요.

JSON 스키마에 맞춰 정확히 응답하세요.
"""


def get_section_user_prompt(
    section_id: str,
    saju_data: Dict[str, Any],
    allocation: SectionRuleCardAllocation,
    target_year: int,
    user_question: str = ""
) -> str:
    """
    🔥🔥🔥 P0 핵심: 사주 4주를 프롬프트에 명시적으로 포함!
    이렇게 해야 서로 다른 생년월일이 서로 다른 리포트를 생성함.
    """
    spec = PREMIUM_SECTIONS.get(section_id)
    
    # 🔥 사주 4주 추출 (이게 핵심!)
    year_pillar = saju_data.get("year_pillar", "-")
    month_pillar = saju_data.get("month_pillar", "-")
    day_pillar = saju_data.get("day_pillar", "-")
    hour_pillar = saju_data.get("hour_pillar", "-") or "미입력"
    day_master = saju_data.get("day_master", "")
    day_master_element = saju_data.get("day_master_element", "")
    day_master_description = saju_data.get("day_master_description", "")
    birth_info = saju_data.get("birth_info", "")
    
    # 🔥 사주 4주가 비어있으면 경고 로그
    if not year_pillar or year_pillar == "-":
        logger.warning(f"[Prompt:{section_id}] ⚠️ 사주 데이터 누락! year_pillar={year_pillar}")
    
    return f"""## 🔮 클라이언트 사주 원국 (필수 참조)

**이 분석은 아래 사주를 기반으로 합니다. 반드시 이 4주를 해석에 반영하세요.**

| 구분 | 간지 |
|------|------|
| 년주(年柱) | {year_pillar} |
| 월주(月柱) | {month_pillar} |
| 일주(日柱) | {day_pillar} |
| 시주(時柱) | {hour_pillar} |

- **일간(日干)**: {day_master} ({day_master_element}) - {day_master_description}
- **생년월일시**: {birth_info if birth_info else '미입력'}
- **분석 기준년도**: {target_year}년

## 💼 클라이언트 질문
{user_question or "종합적인 비즈니스 전략 수립"}

## 📊 분석 근거 RuleCards ({allocation.allocated_count}장)
{allocation.context_text}

---
위 사주 원국과 RuleCards를 기반으로 **{spec.title if spec else section_id}** 섹션을 작성하세요.

⚠️ 핵심 규칙:
1. 위 사주 4주(년/월/일/시)를 반드시 해석에 반영
2. 일간 {day_master}({day_master_element})의 특성을 모든 전략에 연결
3. 반드시 한국어로만 작성
4. 취업/자격증/이력서/면접 관련 내용 절대 금지
5. 매출, 수익, 현금흐름, ROI, KPI 중심으로 작성
6. 최소 {spec.min_chars if spec else 2000}자 이상
7. JSON 스키마에 정확히 맞춰 응답"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. 메인 빌더 (가드레일 + 자동 재생성)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PremiumReportBuilder:
    """99,000원 프리미엄 리포트 빌더 v6"""
    
    def __init__(self):
        self._client = None
        self._semaphore = None
    
    def _get_client(self) -> AsyncOpenAI:
        settings = get_settings()
        api_key = get_openai_api_key()
        return AsyncOpenAI(
            api_key=api_key,
            timeout=httpx.Timeout(90.0, connect=15.0),
            max_retries=0
        )
    
    async def _call_with_retry(
        self,
        messages: List[Dict[str, str]],
        section_id: str,
        response_format: dict,
        max_retries: int = 3,
        base_delay: float = 2.0,
        job_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """JSON Schema + Retry + Exponential Backoff"""
        settings = get_settings()
        last_error = None
        
        for attempt in range(max_retries):
            try:
                logger.info(f"[Section:{section_id}] OpenAI 호출 {attempt + 1}/{max_retries}")
                
                # 🔥 Progress: OpenAI 요청 시작
                if job_id:
                    await job_store.section_stage(job_id, section_id, "openai_request")
                
                response = await self._client.chat.completions.create(
                    model=settings.openai_model,
                    messages=messages,
                    max_tokens=4000,
                    temperature=0.3,
                    response_format=response_format
                )
                
                # 🔥 Progress: 응답 수신 완료
                if job_id:
                    await job_store.section_stage(job_id, section_id, "validating")
                
                content_str = response.choices[0].message.content
                if not content_str:
                    raise ValueError("빈 응답")
                
                content = json.loads(content_str)
                logger.info(f"[Section:{section_id}] 성공 | 응답: {len(content_str)}자")
                return content
                
            except RateLimitError as e:
                last_error = e
                delay = base_delay * (2 ** attempt) + random.uniform(0.5, 1.5)
                logger.warning(f"[Section:{section_id}] 429 Rate Limit | Wait {delay:.1f}s")
                # 🔥 Progress: 429 재시도
                if job_id:
                    await job_store.section_retry(job_id, section_id, "rate_limit_429", delay)
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                    
            except (APIError, APIConnectionError, APITimeoutError) as e:
                last_error = e
                delay = base_delay * (2 ** attempt) + random.uniform(0.5, 1.5)
                logger.warning(f"[Section:{section_id}] API Error | Wait {delay:.1f}s")
                # 🔥 Progress: API 에러 재시도
                if job_id:
                    await job_store.section_retry(job_id, section_id, "api_error", delay)
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                    
            except json.JSONDecodeError as e:
                last_error = e
                delay = base_delay * (2 ** attempt) + random.uniform(0.5, 1.5)
                logger.warning(f"[Section:{section_id}] JSON Parse Error | Wait {delay:.1f}s")
                # 🔥 Progress: JSON 파싱 에러 재시도
                if job_id:
                    await job_store.section_retry(job_id, section_id, "json_parse_error", delay)
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                last_error = e
                logger.error(f"[Section:{section_id}] 에러: {type(e).__name__}: {str(e)[:200]}")
                raise
        
        raise last_error or Exception("Unknown error")
    
    async def _generate_section_with_guardrail(
        self,
        section_id: str,
        saju_data: Dict[str, Any],
        allocation: SectionRuleCardAllocation,
        target_year: int,
        user_question: str,
        max_regeneration: int = 2,
        job_id: Optional[str] = None,
        survey_context: str = ""  # 🔥 v7: 설문 컨텍스트
    ) -> Dict[str, Any]:
        """섹션 생성 + 가드레일 검증 + 품질 게이트 + 자동 재생성"""
        
        async with self._semaphore:
            start_time = time.time()
            spec = PREMIUM_SECTIONS.get(section_id)
            
            # 🔥 Progress: 섹션 시작
            if job_id:
                await job_store.section_start(job_id, section_id)
            
            system_prompt = get_section_system_prompt(section_id, target_year, survey_context)
            user_prompt = get_section_user_prompt(section_id, saju_data, allocation, target_year, user_question)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            response_format = get_section_schema(section_id)
            
            logger.info(f"[Section:{section_id}] 시작 | RuleCards={allocation.allocated_count}장")
            
            for regen_attempt in range(max_regeneration + 1):
                content = await self._call_with_retry(
                    messages=messages,
                    section_id=section_id,
                    response_format=response_format,
                    max_retries=3,
                    base_delay=2.0,
                    job_id=job_id
                )
                
                # 🔥 Progress: 가드레일 검증
                if job_id:
                    await job_store.section_stage(job_id, section_id, "guardrail_check")
                
                # 🔥 가드레일 검증
                body_text = content.get("body_markdown", "")
                is_valid, errors = validate_language_and_topic(body_text, section_id)
                
                # 🔥 v7: 품질 게이트 검증 (금지어/구체성/중복)
                quality_report = quality_gate.check_section(
                    section_id=section_id,
                    content=body_text,
                    existing_contents=[]  # TODO: 이전 섹션 내용 전달
                )
                
                if not quality_report.passed:
                    is_valid = False
                    # 🔥 P0-4: banned_phrase에 상세 정보 추가
                    for issue in quality_report.issues[:3]:
                        if issue.type == "banned_phrase":
                            errors.append(f"QUALITY_GATE:banned_phrase({issue.content})")
                        else:
                            errors.append(f"QUALITY_GATE:{issue.type}")
                    logger.warning(f"[Section:{section_id}] 품질 게이트 점수: {quality_report.score}/100")
                
                if is_valid:
                    logger.info(f"[Section:{section_id}] ✅ 가드레일 통과")
                    break
                else:
                    if regen_attempt < max_regeneration:
                        logger.warning(
                            f"[Section:{section_id}] ⚠️ 가드레일 실패 ({regen_attempt + 1}/{max_regeneration}) | "
                            f"Errors: {errors} → 재생성 중..."
                        )
                        # 재생성 시 더 강한 경고 추가
                        messages[1]["content"] += f"\n\n⚠️ 이전 응답이 가드레일을 위반했습니다: {errors}. 반드시 한국어로, 비즈니스 용어만 사용하세요."
                    else:
                        logger.error(f"[Section:{section_id}] ❌ 가드레일 최종 실패 | Errors: {errors}")
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            # 🔥 P0-2: ok 필드 명확히 반환 (is_valid 기반)
            return {
                "ok": is_valid,  # 🔥 핵심: 가드레일 통과 여부
                "content": content, 
                "latency_ms": latency_ms, 
                "guardrail_errors": errors if not is_valid else []
            }
    
    async def build_premium_report(
        self,
        saju_data: Dict[str, Any],
        rulecards: List[Dict[str, Any]],
        feature_tags: List[str] = None,
        target_year: int = 2026,
        user_question: str = "",
        name: str = "고객",
        mode: str = "premium",
        job_id: Optional[str] = None,
        survey_data: Optional[Dict[str, Any]] = None  # 🔥 v7: 7문항 설문 데이터
    ) -> Dict[str, Any]:
        """7개 섹션 순차 생성 (Progress 지원 + 품질 게이트)"""
        settings = get_settings()
        start_time = time.time()
        
        self._semaphore = asyncio.Semaphore(1)
        self._client = self._get_client()
        
        if not feature_tags:
            feature_tags = []
        
        # 🔥 v7: 설문 데이터 → 프롬프트 컨텍스트 변환
        survey_context = ""
        if survey_data:
            try:
                survey = SurveyResponse.from_dict(survey_data)
                survey_context = survey_to_prompt_context(survey)
                logger.info(f"[PremiumReport] 설문 컨텍스트 생성: {len(survey_context)}자")
            except Exception as e:
                logger.warning(f"[PremiumReport] 설문 데이터 변환 실패: {e}")
        
        # 🔥 Progress: Job 시작
        if job_id:
            await job_store.start_job(job_id)
        
        # 전역 Top-100 선별
        global_selection = select_global_top100(rulecards, feature_tags, top_limit=100)
        
        logger.info(
            f"[PremiumReport] ========== 시작 ==========\n"
            f"  Year={target_year} | Pool={global_selection.original_pool_count} | "
            f"Top100={global_selection.top100_count}"
        )
        
        # 섹션별 RuleCard 분배
        section_ids = list(PREMIUM_SECTIONS.keys())
        allocations: Dict[str, SectionRuleCardAllocation] = {}
        used_card_ids = set()
        
        for sid in section_ids:
            spec = PREMIUM_SECTIONS[sid]
            alloc = allocate_rulecards_to_section(
                top100_cards=global_selection.top100_cards,
                section_id=sid,
                max_cards=spec.max_cards,
                already_used_ids=used_card_ids
            )
            allocations[sid] = alloc
            used_card_ids.update(alloc.allocated_card_ids)
        
        # 섹션 생성 (가드레일 + 품질 게이트 포함) - 🔥 순차 처리로 변경 (Progress 지원)
        results = []
        for sid in section_ids:
            try:
                result = await self._generate_section_with_guardrail(
                    section_id=sid,
                    saju_data=saju_data,
                    allocation=allocations[sid],
                    target_year=target_year,
                    user_question=user_question,
                    max_regeneration=2,
                    job_id=job_id,
                    survey_context=survey_context  # 🔥 v7: 설문 컨텍스트 전달
                )
                results.append(result)
                
                # 🔥 Progress: 섹션 완료
                if job_id:
                    char_count = len(result.get("content", {}).get("body_markdown", ""))
                    await job_store.section_done(job_id, sid, char_count)
                    
            except Exception as e:
                results.append(e)
                # 🔥 Progress: 섹션 에러
                if job_id:
                    await job_store.section_error(job_id, sid, str(e)[:200])
        
        # 결과 수집
        sections = []
        errors = []
        rulecard_meta = {}
        all_used_card_ids = set()
        
        for sid, result in zip(section_ids, results):
            alloc = allocations[sid]
            
            if isinstance(result, Exception):
                errors.append({"section": sid, "error_type": type(result).__name__, "error_message": str(result)[:500]})
                logger.error(f"[PremiumReport] ❌ 섹션 실패: {sid}")
                sections.append(self._create_error_section(sid, target_year, str(result)[:200]))
            else:
                content = result["content"]
                polished = self._polish_section(content, sid)
                spec = PREMIUM_SECTIONS.get(sid)
                
                section_data = {
                    "id": sid,
                    "title": spec.title if spec else sid,
                    "confidence": polished.get("confidence", "MEDIUM"),
                    "rulecard_ids": alloc.allocated_card_ids,
                    "rulecard_selected": alloc.allocated_count,
                    "body_markdown": polished.get("body_markdown", ""),
                    "char_count": len(polished.get("body_markdown", "")),
                    "latency_ms": result.get("latency_ms", 0),
                    "guardrail_passed": len(result.get("guardrail_errors", [])) == 0
                }
                
                # 타입별 필드
                if spec.validation_type == "sprint":
                    section_data.update({
                        "mission_statement": polished.get("mission_statement", ""),
                        "phase_1_offer": polished.get("phase_1_offer", {}),
                        "phase_2_funnel": polished.get("phase_2_funnel", {}),
                        "phase_3_content": polished.get("phase_3_content", {}),
                        "phase_4_automation": polished.get("phase_4_automation", {}),
                        "milestones": polished.get("milestones", {}),
                        "risk_scenarios": polished.get("risk_scenarios", []),
                    })
                elif spec.validation_type == "calendar":
                    section_data.update({
                        "annual_theme": polished.get("annual_theme", ""),
                        "annual_revenue_projection": polished.get("annual_revenue_projection", ""),
                        "monthly_plans": polished.get("monthly_plans", []),
                        "quarterly_milestones": polished.get("quarterly_milestones", {}),
                        "peak_months": polished.get("peak_months", []),
                        "risk_months": polished.get("risk_months", []),
                    })
                else:
                    section_data.update({
                        "diagnosis": polished.get("diagnosis", {}),
                        "hypotheses": polished.get("hypotheses", []),
                        "strategy_options": polished.get("strategy_options", []),
                        "recommended_strategy": polished.get("recommended_strategy", {}),
                        "kpis": polished.get("kpis", []),
                        "risks": polished.get("risks", []),
                    })
                
                sections.append(section_data)
                all_used_card_ids.update(alloc.allocated_card_ids)
                logger.info(f"[PremiumReport] ✅ 섹션 성공: {sid} | Chars={section_data['char_count']}")
            
            rulecard_meta[sid] = {
                "selected_count": alloc.allocated_count,
                "selected_card_ids": alloc.allocated_card_ids
            }
        
        total_latency = int((time.time() - start_time) * 1000)
        total_chars = sum(s.get("char_count", 0) for s in sections)
        unique_cards_used = len(all_used_card_ids)
        
        report = {
            "target_year": target_year,
            "sections": sections,
            "meta": {
                "total_chars": total_chars,
                "mode": "premium_business_30p",
                "generated_at": datetime.now().isoformat(),
                "llm_model": settings.openai_model,
                "section_count": len(sections),
                "success_count": len(sections) - len(errors),
                "error_count": len(errors),
                "latency_ms": total_latency,
                # 🔥 핵심: 유니크 RuleCard 합산
                "rulecards_pool_total": global_selection.original_pool_count,
                "rulecards_top100_selected": global_selection.top100_count,
                "rulecards_unique_used": unique_cards_used,
                "rulecards_by_section": rulecard_meta,
                "feature_tags_count": len(feature_tags),
                "errors": errors if errors else None
            },
            "legacy": self._create_legacy_compat(sections, target_year, name)
        }
        
        logger.info(
            f"[PremiumReport] ========== 완료 ==========\n"
            f"  Sections={len(sections)} | Success={len(sections) - len(errors)}\n"
            f"  🔥 RuleCards={unique_cards_used}/{global_selection.original_pool_count}\n"
            f"  Chars={total_chars} | Latency={total_latency}ms"
        )
        
        # 🔥 Progress: Job 완료
        if job_id:
            await job_store.complete_job(job_id, report)
        
        # 🔥 v7: Supabase에 최종 리포트 영구 저장
        try:
            from app.services.supabase_service import supabase_service
            
            # 1) 각 섹션을 report_sections 테이블에 저장
            for section in sections:
                await supabase_service.save_section(
                    job_id=job_id,
                    section_id=section["id"],
                    content_json=section
                )
            
            # 2) Job 완료 상태 업데이트 (result_json, saju_json 포함)
            await supabase_service.complete_job(
                job_id=job_id,
                result_json=report,
                saju_json=saju_data  # 🔥 사주 계산 결과 저장
            )
            
            logger.info(f"✅ [Supabase] 리포트 영구 저장 완료 (Job: {job_id}, 섹션: {len(sections)}개)")
        except Exception as e:
            logger.error(f"❌ [Supabase] 저장 중 오류 발생: {str(e)}", exc_info=True)
        
        return report
    
    async def regenerate_single_section(
        self,
        section_id: str,
        saju_data: Dict[str, Any],
        rulecards: List[Dict[str, Any]],
        feature_tags: List[str] = None,
        target_year: int = 2026,
        user_question: str = "",
        survey_data: Optional[Dict[str, Any]] = None  # 🔥 v7: 설문 데이터
    ) -> Dict[str, Any]:
        """단일 섹션 재생성"""
        
        # 🔥 P0-2: RuleCards 진단 로그
        logger.info(f"[Section:{section_id}] 시작 | RuleCards={len(rulecards)}장, feature_tags={len(feature_tags or [])}개")
        
        if section_id not in PREMIUM_SECTIONS:
            raise ValueError(f"Invalid section_id: {section_id}")
        
        self._semaphore = asyncio.Semaphore(1)
        self._client = self._get_client()
        
        if not feature_tags:
            feature_tags = []
        
        # 🔥 v7: 설문 데이터 → 프롬프트 컨텍스트 변환
        survey_context = ""
        if survey_data:
            try:
                survey = SurveyResponse.from_dict(survey_data)
                survey_context = survey_to_prompt_context(survey)
            except Exception as e:
                logger.warning(f"[SingleSection] 설문 데이터 변환 실패: {e}")
        
        global_selection = select_global_top100(rulecards, feature_tags, top_limit=100)
        spec = PREMIUM_SECTIONS[section_id]
        allocation = allocate_rulecards_to_section(global_selection.top100_cards, section_id, spec.max_cards, set())
        
        try:
            result = await self._generate_section_with_guardrail(
                section_id=section_id,
                saju_data=saju_data,
                allocation=allocation,
                target_year=target_year,
                user_question=user_question,
                max_regeneration=2,
                survey_context=survey_context  # 🔥 v7: 설문 컨텍스트 전달
            )
            
            content = result["content"]
            polished = self._polish_section(content, section_id)
            
            section_data = {
                "id": section_id,
                "title": spec.title,
                "confidence": polished.get("confidence", "MEDIUM"),
                "rulecard_ids": allocation.allocated_card_ids,
                "rulecard_selected": allocation.allocated_count,
                "body_markdown": polished.get("body_markdown", ""),
                "char_count": len(polished.get("body_markdown", "")),
                "latency_ms": result.get("latency_ms", 0),
                "regenerated": True
            }
            
            return {"success": True, "section": section_data}
            
        except Exception as e:
            logger.error(f"[SingleSection] 실패: {section_id} | {str(e)[:200]}")
            return {"success": False, "section_id": section_id, "error": str(e)[:500]}
    
    def _polish_section(self, content: Dict[str, Any], section_id: str) -> Dict[str, Any]:
        if "body_markdown" in content:
            content["body_markdown"] = sanitize_for_business(content["body_markdown"])
        if "diagnosis" in content and isinstance(content["diagnosis"], dict):
            if "current_state" in content["diagnosis"]:
                content["diagnosis"]["current_state"] = sanitize_for_business(content["diagnosis"]["current_state"])
        if "mission_statement" in content:
            content["mission_statement"] = sanitize_for_business(content["mission_statement"])
        if "annual_theme" in content:
            content["annual_theme"] = sanitize_for_business(content["annual_theme"])
        return content
    
    def _create_error_section(self, section_id: str, target_year: int, error_msg: str = "") -> Dict[str, Any]:
        spec = PREMIUM_SECTIONS.get(section_id)
        return {
            "id": section_id,
            "title": spec.title if spec else section_id,
            "confidence": "LOW",
            "rulecard_ids": [],
            "rulecard_selected": 0,
            "body_markdown": f"## {spec.title if spec else section_id}\n\n분석 중 오류가 발생했습니다.\n_Error: {error_msg[:100]}_",
            "char_count": 0,
            "latency_ms": 0,
            "error": True,
            "error_message": error_msg[:200]
        }
    
    def _create_legacy_compat(self, sections: List[Dict[str, Any]], target_year: int, name: str) -> Dict[str, Any]:
        exec_section = next((s for s in sections if s["id"] == "exec"), {})
        strengths = [h.get("statement", "") for h in exec_section.get("hypotheses", []) if h.get("confidence") == "HIGH"][:5]
        risks = [r.get("risk", "") for r in exec_section.get("risks", [])[:3]]
        return {
            "success": True,
            "summary": f"{target_year}년 프리미엄 비즈니스 컨설팅 보고서",
            "strengths": strengths,
            "risks": risks,
            "blessing": f"{name}님의 {target_year}년 성공을 응원합니다!",
            "disclaimer": "본 보고서는 데이터 기반 분석 참고 자료입니다."
        }


premium_report_builder = PremiumReportBuilder()
report_builder = premium_report_builder
