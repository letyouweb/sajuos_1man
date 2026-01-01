"""
Reports API Router v13 - P0: section_id 매핑 + 탭 강제
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 P0 핵심: 백엔드 ID → 프론트 ID 매핑
- exec → business_climate
- money → cashflow
- business → market_product
- team → team_partnership
- health → owner_risk
- calendar → sprint_12m
- sprint → action_90d
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, Query
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any, List
import logging
import uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])


# ─────────────────────────────────────────────
# Request Model
# ─────────────────────────────────────────────

class ReportStartRequest(BaseModel):
    email: Optional[EmailStr] = None
    name: str = "고객"

    saju_result: Optional[Dict[str, Any]] = None
    year_pillar: Optional[str] = None
    month_pillar: Optional[str] = None
    day_pillar: Optional[str] = None
    hour_pillar: Optional[str] = None

    target_year: int = 2026
    question: str = ""
    concern_type: str = "career"
    survey_data: Optional[Dict[str, Any]] = None

    # 🔥 P0
    gender: Optional[str] = None          # female / male / 여 / 남
    birth_info: Optional[Dict[str, Any]] = None  # {year, month, day, hour, minute ...}


def get_supabase():
    try:
        from app.services.supabase_service import supabase_service
        return supabase_service
    except Exception as e:
        logger.error(f"Supabase import 실패: {e}")
        return None


# ─────────────────────────────────────────────
# Section ID Mapping
# ─────────────────────────────────────────────

BACKEND_TO_FRONTEND_ID = {
    "exec": "business_climate",
    "money": "cashflow",
    "business": "market_product",
    "team": "team_partnership",
    "health": "owner_risk",
    "calendar": "sprint_12m",
    "sprint": "action_90d",
}

FRONTEND_TO_BACKEND_ID = {v: k for k, v in BACKEND_TO_FRONTEND_ID.items()}

SECTION_SPECS = [
    {"id": "business_climate", "backend_id": "exec", "title": "2026 비즈니스 전략 기상도", "order": 1, "icon": "🌦️"},
    {"id": "cashflow", "backend_id": "money", "title": "자본 유동성 및 현금흐름 최적화", "order": 2, "icon": "💰"},
    {"id": "market_product", "backend_id": "business", "title": "시장 포지셔닝 및 상품 확장 전략", "order": 3, "icon": "📍"},
    {"id": "team_partnership", "backend_id": "team", "title": "조직 확장 및 파트너십 가이드", "order": 4, "icon": "🤝"},
    {"id": "owner_risk", "backend_id": "health", "title": "오너 리스크 관리 및 번아웃 방어", "order": 5, "icon": "🧯"},
    {"id": "sprint_12m", "backend_id": "calendar", "title": "12개월 비즈니스 스프린트 캘린더", "order": 6, "icon": "🗓️"},
    {"id": "action_90d", "backend_id": "sprint", "title": "향후 90일 매출 극대화 액션플랜", "order": 7, "icon": "🚀"},
]


def map_to_frontend_id(backend_id: str) -> str:
    return BACKEND_TO_FRONTEND_ID.get(backend_id, backend_id)


# ─────────────────────────────────────────────
# Normalize / Placeholder
# ─────────────────────────────────────────────

def normalize_section(section: Dict) -> Dict:
    backend_id = section.get("section_id") or section.get("id", "")
    frontend_id = map_to_frontend_id(backend_id)
    raw_json = section.get("raw_json") or {}
    markdown = section.get("markdown") or raw_json.get("body_markdown", "")

    spec = next((s for s in SECTION_SPECS if s["backend_id"] == backend_id), None)

    return {
        "section_id": frontend_id,
        "id": frontend_id,
        "backend_id": backend_id,
        "title": spec["title"] if spec else backend_id,
        "icon": spec.get("icon") if spec else "📄",
        "order": spec.get("order", 99) if spec else 99,
        "status": "completed" if markdown else "empty",
        "markdown": markdown,
        "body_markdown": markdown,
        "raw_json": raw_json,
        "char_count": len(markdown or ""),
    }


def ensure_all_sections(sections_raw: List[Dict], job_id: str, job_status: str = "running") -> List[Dict]:
    by_backend = {s.get("section_id"): s for s in sections_raw}
    results = []

    for spec in SECTION_SPECS:
        backend_id = spec["backend_id"]
        frontend_id = spec["id"]
        s = by_backend.get(backend_id)

        is_completed = job_status == "completed"
        placeholder_status = "empty" if is_completed else "generating"

        if s:
            results.append(normalize_section(s))
        else:
            results.append({
                "section_id": frontend_id,
                "id": frontend_id,
                "backend_id": backend_id,
                "title": spec["title"],
                "icon": spec["icon"],
                "order": spec["order"],
                "status": placeholder_status,
                "markdown": "⏳ 이 섹션은 현재 생성 중입니다.\n\n잠시 후 다시 확인해주세요.",
                "body_markdown": "",
                "raw_json": {},
                "char_count": 0,
                "error": "SECTION_MISSING",
            })
            if is_completed:
                logger.warning(f"[Reports] 섹션 누락(완료 상태): {frontend_id} | job={job_id}")
            else:
                logger.info(f"[Reports] 섹션 생성중 placeholder: {frontend_id} | job={job_id}")

    return sorted(results, key=lambda x: x["order"])


# ─────────────────────────────────────────────
# Start Report
# ─────────────────────────────────────────────

@router.post("/start")
async def start_report(payload: ReportStartRequest, background_tasks: BackgroundTasks, request: Request):
    input_data = {
        "name": payload.name,
        "question": payload.question,
        "concern_type": payload.concern_type,
        "target_year": payload.target_year,
        "survey_data": payload.survey_data,
        "saju_result": payload.saju_result,
        "year_pillar": payload.year_pillar,
        "month_pillar": payload.month_pillar,
        "day_pillar": payload.day_pillar,
        "hour_pillar": payload.hour_pillar,

        # 🔥 P0 전달
        "gender": payload.gender,
        "birth_info": payload.birth_info,
    }

    supabase = get_supabase()
    if not supabase or not supabase.is_available():
        raise HTTPException(status_code=503, detail="Supabase 미연결")

    try:
        job = await supabase.create_job(
            email=payload.email,
            name=payload.name,
            input_data=input_data,
            target_year=payload.target_year,
        )
        job_id = job["id"]
        public_token = job.get("public_token")

        rulestore = getattr(request.app.state, "rulestore", None)
        background_tasks.add_task(run_report_job, job_id, rulestore)

        logger.info(f"[Reports] Job 생성: {job_id}")
        return {
            "success": True,
            "job_id": job_id,
            "token": public_token,
            "status": "queued",
        }
    except Exception as e:
        logger.error(f"Job 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e)[:300])


# ─────────────────────────────────────────────
# View Report
# ─────────────────────────────────────────────

@router.get("/view/{job_id}")
async def view_report(job_id: str, token: str = Query(...)):
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id")

    supabase = get_supabase()
    is_valid, job = await supabase.verify_job_token(job_id, token)
    if not is_valid:
        raise HTTPException(status_code=403, detail="Invalid token")

    sections_raw = await supabase.get_sections_ordered(job_id)
    job_status = job.get("status") or "running"

    sections = ensure_all_sections(sections_raw, job_id, job_status)

    return {
        "job_id": job_id,
        "status": job_status,
        "progress": job.get("progress", 0),
        "sections": sections,
    }


# ─────────────────────────────────────────────
# Worker Runner
# ─────────────────────────────────────────────

async def run_report_job(job_id: str, rulestore):
    try:
        from app.services.report_worker import report_worker
        await report_worker.run_job(job_id, rulestore)
    except Exception as e:
        logger.error(f"[Reports] Job 실패: {job_id} | {e}")
        supabase = get_supabase()
        if supabase:
            await supabase.fail_job(job_id, str(e))
