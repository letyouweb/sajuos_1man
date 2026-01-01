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


class ReportStartRequest(BaseModel):
    email: EmailStr
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
    gender: Optional[str] = None  # 🔥 P0: 성별 (female/male/여/남)
    birth_info: Optional[Dict[str, Any]] = None  # 🔥 P0: 생년월일 정보


def get_supabase():
    try:
        from app.services.supabase_service import supabase_service
        return supabase_service
    except Exception as e:
        logger.error(f"Supabase import 실패: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 P0: section_id 매핑 (백엔드 → 프론트)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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


def map_to_frontend_id(backend_id: str) -> str:
    return BACKEND_TO_FRONTEND_ID.get(backend_id, backend_id)


def map_to_backend_id(frontend_id: str) -> str:
    return FRONTEND_TO_BACKEND_ID.get(frontend_id, frontend_id)


SECTION_ORDER = ["business_climate", "cashflow", "market_product", "team_partnership", "owner_risk", "sprint_12m", "action_90d"]

SECTION_SPECS = [
    {"id": "business_climate", "backend_id": "exec", "title": "2026 비즈니스 전략 기상도", "order": 1, "icon": "🌦️"},
    {"id": "cashflow", "backend_id": "money", "title": "자본 유동성 및 현금흐름 최적화", "order": 2, "icon": "💰"},
    {"id": "market_product", "backend_id": "business", "title": "시장 포지셔닝 및 상품 확장 전략", "order": 3, "icon": "📍"},
    {"id": "team_partnership", "backend_id": "team", "title": "조직 확장 및 파트너십 가이드", "order": 4, "icon": "🤝"},
    {"id": "owner_risk", "backend_id": "health", "title": "오너 리스크 관리 및 번아웃 방어", "order": 5, "icon": "🧯"},
    {"id": "sprint_12m", "backend_id": "calendar", "title": "12개월 비즈니스 스프린트 캘린더", "order": 6, "icon": "🗓️"},
    {"id": "action_90d", "backend_id": "sprint", "title": "향후 90일 매출 극대화 액션플랜", "order": 7, "icon": "🚀"},
]


def get_section_title(section_id: str) -> str:
    for spec in SECTION_SPECS:
        if spec["id"] == section_id or spec.get("backend_id") == section_id:
            return spec["title"]
    return section_id or "Unknown"


def get_section_order(section_id: str) -> int:
    frontend_id = map_to_frontend_id(section_id)
    if frontend_id in SECTION_ORDER:
        return SECTION_ORDER.index(frontend_id) + 1
    return 99


def get_section_icon(section_id: str) -> str:
    frontend_id = map_to_frontend_id(section_id)
    for spec in SECTION_SPECS:
        if spec["id"] == frontend_id:
            return spec.get("icon", "📄")
    return "📄"


def extract_markdown_from_section(section: Dict) -> str:
    if section.get("markdown"):
        return section["markdown"]
    raw_json = section.get("raw_json") or {}
    if raw_json.get("body_markdown"):
        return raw_json["body_markdown"]
    if raw_json.get("content"):
        return raw_json["content"]
    return ""


def normalize_section(section: Dict) -> Dict:
    backend_id = section.get("section_id") or section.get("id", "")
    frontend_id = map_to_frontend_id(backend_id)
    raw_json = section.get("raw_json") or {}
    markdown = section.get("markdown") or extract_markdown_from_section(section)
    
    return {
        "section_id": frontend_id,
        "id": frontend_id,
        "backend_id": backend_id,
        "title": section.get("title") or get_section_title(backend_id),
        "icon": get_section_icon(backend_id),
        "status": section.get("status", "completed"),
        "order": section.get("order") or get_section_order(backend_id),
        "markdown": markdown,
        "content": markdown,
        "body_markdown": markdown,
        "raw_json": raw_json,
        "char_count": section.get("char_count") or len(markdown),
        "error": section.get("error"),
        "updated_at": section.get("updated_at"),
    }


def ensure_all_sections(sections_raw: List[Dict], job_id: str, job_status: str = "running") -> List[Dict]:
    sections_by_backend_id = {}
    for s in sections_raw:
        bid = s.get("section_id") or s.get("id", "")
        sections_by_backend_id[bid] = s
    
    sections_normalized = []
    
    for spec in SECTION_SPECS:
        frontend_id = spec["id"]
        backend_id = spec["backend_id"]
        s = sections_by_backend_id.get(backend_id)
        
        is_completed = (job_status == "completed")
        placeholder_status = "empty" if is_completed else "generating"

        if s:
            normalized = normalize_section(s)
            sections_normalized.append(normalized)
        else:
            sections_normalized.append({
                "section_id": frontend_id,
                "id": frontend_id,
                "backend_id": backend_id,
                "title": spec["title"],
                "icon": spec.get("icon", "📄"),
                "status": placeholder_status,
                "order": spec["order"],
                "markdown": "⏳ 이 섹션은 현재 생성 중이거나 저장에 실패했습니다.\n\n잠시 후 다시 시도해주세요.",
                "content": "",
                "body_markdown": "",
                "raw_json": {},
                "char_count": 0,
                "error": "SECTION_MISSING",
            })
            if is_completed:
                logger.warning(f"[Reports] 섹션 누락(완료 상태): {frontend_id} | job={job_id}")
            else:
                logger.info(f"[Reports] 섹션 생성중 placeholder: {frontend_id} | job={job_id}")
    
    sections_normalized.sort(key=lambda x: x.get("order", 99))
    return sections_normalized


def build_full_markdown(sections: List[Dict], name: str = "고객", target_year: int = 2026) -> str:
    lines = [f"# {name}님의 {target_year}년 비즈니스 운세 리포트\n"]
    for section in sections:
        title = section.get("title") or ""
        markdown = section.get("markdown") or ""
        if markdown and section.get("status") != "empty":
            lines.append(f"## {title}\n")
            lines.append(markdown)
            lines.append("\n---\n")
    return "\n".join(lines)


@router.get("/debug/{job_id}")
async def debug_job(job_id: str):
    supabase = get_supabase()
    if not supabase or not supabase.is_available():
        return {"error": "Supabase 미연결"}
    job = await supabase.get_job(job_id)
    if not job:
        return {"error": f"Job not found: {job_id}"}
    sections_raw = await supabase.get_sections_ordered(job_id)
    return {
        "job_id": job_id,
        "job_status": job.get("status"),
        "sections_count": len(sections_raw),
        "sections": [{"backend_id": s.get("section_id"), "frontend_id": map_to_frontend_id(s.get("section_id", "")), "status": s.get("status"), "markdown_length": len(s.get("markdown") or "")} for s in sections_raw],
        "id_mapping": BACKEND_TO_FRONTEND_ID,
    }


@router.post("/start")
async def start_report(payload: ReportStartRequest, background_tasks: BackgroundTasks, request: Request):
    input_data = {"name": payload.name, "question": payload.question, "concern_type": payload.concern_type, "target_year": payload.target_year, "survey_data": payload.survey_data, "saju_result": payload.saju_result, "year_pillar": payload.year_pillar, "month_pillar": payload.month_pillar, "day_pillar": payload.day_pillar, "hour_pillar": payload.hour_pillar, "gender": payload.gender, "birth_info": payload.birth_info}
    supabase = get_supabase()
    if supabase and supabase.is_available():
        try:
            job = await supabase.create_job(email=payload.email, name=payload.name, input_data=input_data, target_year=payload.target_year)
            job_id = job["id"]
            public_token = job.get("public_token")
            logger.info(f"[Reports] Job 생성: {job_id}")
            try:
                await supabase.init_sections(job_id, SECTION_SPECS)
            except Exception as e:
                logger.warning(f"섹션 초기화 스킵: {e}")
            rulestore = getattr(request.app.state, "rulestore", None)
            background_tasks.add_task(run_report_job, job_id, rulestore)
            return {"success": True, "job_id": job_id, "token": public_token, "status": "queued", "message": "리포트 생성이 시작되었습니다."}
        except Exception as e:
            logger.error(f"Job 생성 실패: {e}")
            raise HTTPException(status_code=500, detail=str(e)[:300])
    else:
        temp_id = str(uuid.uuid4())
        return {"success": True, "job_id": temp_id, "status": "queued"}


@router.get("/start")
async def start_report_get():
    return {"error": "Use POST method"}


@router.get("/sections-info")
async def get_sections_info():
    return {"sections": SECTION_SPECS, "id_mapping": BACKEND_TO_FRONTEND_ID}


@router.get("/view/{job_id}")
async def view_report(job_id: str, token: str = Query(..., description="Access token")):
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid job_id: {job_id}")
    supabase = get_supabase()
    if not supabase or not supabase.is_available():
        raise HTTPException(status_code=503, detail="Supabase 미연결")
    is_valid, job = await supabase.verify_job_token(job_id, token)
    if not is_valid or not job:
        raise HTTPException(status_code=404, detail="Invalid token or job not found")
    sections_raw = await supabase.get_sections_ordered(job_id)
    sections_raw = [s for s in sections_raw if s.get("job_id") == job_id]
    job_status = job.get("status") or "running"
    sections_normalized = ensure_all_sections(sections_raw, job_id, job_status)
    db_section_count = len([s for s in sections_raw if s.get("section_id")])
    if job_status == "completed" and db_section_count == 0:
        logger.error(f"[Reports] COMPLETED인데 DB 섹션 0개: {job_id}")
    input_json = job.get("input_json") or {}
    name = input_json.get("name", "고객")
    target_year = input_json.get("target_year", 2026)
    full_markdown = build_full_markdown(sections_normalized, name, target_year)
    logger.info(f"[Reports] view_report: {job_id} | db_sections={db_section_count} | total_tabs=7")
    return {"job": {"id": job["id"], "status": job.get("status"), "progress": job.get("progress", 0), "completed_at": job.get("completed_at"), "error": job.get("error")}, "input": input_json, "sections": sections_normalized, "full_markdown": full_markdown, "section_count": 7}


@router.get("/verify/{job_id}")
async def verify_token(job_id: str, token: str = Query(...)):
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid job_id: {job_id}")
    supabase = get_supabase()
    if not supabase or not supabase.is_available():
        raise HTTPException(status_code=503, detail="Supabase 미연결")
    is_valid, job = await supabase.verify_job_token(job_id, token)
    if not is_valid:
        raise HTTPException(status_code=403, detail="Invalid token")
    return {"valid": True, "job_id": job["id"], "status": job.get("status")}


@router.get("/{job_id}/status")
async def get_job_status(job_id: str):
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid job_id: {job_id}")
    supabase = get_supabase()
    if not supabase or not supabase.is_available():
        return {"job_id": job_id, "status": "unknown", "progress": 0}
    try:
        job = await supabase.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        sections_data = await supabase.get_sections(job_id)
        completed = len([s for s in sections_data if s.get("status") in ("completed", "done", "success")])
        progress = max(job.get("progress", 0), int((completed / 7) * 100))
        return {"job_id": job_id, "status": job.get("status", "unknown"), "progress": progress, "sections": [{"id": map_to_frontend_id(s.get("section_id", "")), "status": s.get("status")} for s in sections_data]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.get("/{job_id}")
async def get_report_status(job_id: str, token: Optional[str] = Query(None)):
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid job_id: {job_id}")
    supabase = get_supabase()
    if not supabase or not supabase.is_available():
        return {"job_id": job_id, "status": "unknown", "progress": 0}
    try:
        if token:
            is_valid, job = await supabase.verify_job_token(job_id, token)
            if not is_valid:
                raise HTTPException(status_code=403, detail="Invalid token")
        else:
            job = await supabase.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        sections_data = await supabase.get_sections(job_id)
        return {"job_id": job_id, "status": job.get("status", "unknown"), "progress": job.get("progress", 0), "sections": [{"id": map_to_frontend_id(s.get("section_id", "")), "status": s.get("status")} for s in sections_data]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.get("/{job_id}/result")
async def get_report_result(job_id: str, token: Optional[str] = Query(None)):
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid job_id: {job_id}")
    supabase = get_supabase()
    if not supabase or not supabase.is_available():
        raise HTTPException(status_code=503, detail="Supabase 미연결")
    if token:
        is_valid, job = await supabase.verify_job_token(job_id, token)
        if not is_valid:
            raise HTTPException(status_code=403, detail="Invalid token")
    else:
        job = await supabase.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "completed":
        return {"completed": False, "status": job.get("status"), "progress": job.get("progress", 0)}
    sections_raw = await supabase.get_sections_ordered(job_id)
    sections_raw = [s for s in sections_raw if s.get("job_id") == job_id]
    sections_normalized = ensure_all_sections(sections_raw, job_id)
    db_section_count = len([s for s in sections_raw if s.get("section_id")])
    if db_section_count == 0:
        logger.error(f"[Reports] result 요청인데 DB 섹션 0개: {job_id}")
    input_json = job.get("input_json") or {}
    name = input_json.get("name", "고객")
    target_year = input_json.get("target_year", 2026)
    full_markdown = build_full_markdown(sections_normalized, name, target_year)
    logger.info(f"[Reports] get_report_result: {job_id} | db_sections={db_section_count} | total_tabs=7")
    return {"completed": True, "job": {"id": job["id"], "status": job.get("status"), "completed_at": job.get("completed_at")}, "input": input_json, "sections": sections_normalized, "full_markdown": full_markdown, "section_count": 7}


async def run_report_job(job_id: str, rulestore):
    try:
        from app.services.report_worker import report_worker
        await report_worker.run_job(job_id, rulestore)
    except Exception as e:
        logger.error(f"Report job 실패: {job_id} | {e}")
        supabase = get_supabase()
        if supabase:
            try:
                await supabase.fail_job(job_id, str(e))
            except:
                pass
