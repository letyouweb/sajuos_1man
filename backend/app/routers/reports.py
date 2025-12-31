"""
Reports API Router v11 - P0: 탭 강제 생성 + 섹션 placeholder
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
P0 핵심 수정:
1) 🔥 탭 강제: DB에 섹션 없어도 7개 탭 모두 반환
2) full_markdown = 섹션별 markdown 순서대로 합침
3) completed인데 섹션 비면 → 경고 로그
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


def get_supabase():
    try:
        from app.services.supabase_service import supabase_service
        return supabase_service
    except Exception as e:
        logger.error(f"Supabase import 실패: {e}")
        return None


# 🔥 섹션 순서 고정 (7개)
SECTION_ORDER = ["exec", "money", "business", "team", "health", "calendar", "sprint"]

SECTION_SPECS = [
    {"id": "exec", "title": "Executive Summary", "order": 1, "icon": "📊"},
    {"id": "money", "title": "Money & Cashflow", "order": 2, "icon": "💰"},
    {"id": "business", "title": "Business Strategy", "order": 3, "icon": "🎯"},
    {"id": "team", "title": "Team & Partner", "order": 4, "icon": "🤝"},
    {"id": "health", "title": "Health & Performance", "order": 5, "icon": "❤️"},
    {"id": "calendar", "title": "12-Month Calendar", "order": 6, "icon": "📅"},
    {"id": "sprint", "title": "90-Day Sprint", "order": 7, "icon": "🚀"},
]


def get_section_title(section_id: str) -> str:
    for spec in SECTION_SPECS:
        if spec["id"] == section_id:
            return spec["title"]
    return section_id or "Unknown"


def get_section_order(section_id: str) -> int:
    if section_id in SECTION_ORDER:
        return SECTION_ORDER.index(section_id) + 1
    return 99


def get_section_icon(section_id: str) -> str:
    for spec in SECTION_SPECS:
        if spec["id"] == section_id:
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
    section_id = section.get("section_id") or section.get("id", "")
    raw_json = section.get("raw_json") or {}
    markdown = section.get("markdown") or extract_markdown_from_section(section)
    
    return {
        "section_id": section_id,
        "id": section_id,
        "title": section.get("title") or get_section_title(section_id),
        "icon": get_section_icon(section_id),
        "status": section.get("status", "completed"),
        "order": section.get("order") or get_section_order(section_id),
        "markdown": markdown,
        "content": markdown,
        "body_markdown": markdown,
        "raw_json": raw_json,
        "char_count": section.get("char_count") or len(markdown),
        "error": section.get("error"),
        "updated_at": section.get("updated_at"),
    }


def ensure_all_sections(sections_raw: List[Dict], job_id: str) -> List[Dict]:
    """
    🔥 P0 탭 강제: DB에 섹션이 없어도 7개 탭 모두 반환
    """
    sections_by_id = {s.get("section_id"): s for s in sections_raw}
    sections_normalized = []
    
    for spec in SECTION_SPECS:
        sid = spec["id"]
        s = sections_by_id.get(sid)
        
        if s:
            sections_normalized.append(normalize_section(s))
        else:
            # 🔥 탭 강제: 섹션이 DB에 없어도 탭은 보여준다
            sections_normalized.append({
                "section_id": sid,
                "id": sid,
                "title": spec["title"],
                "icon": spec.get("icon", "📄"),
                "status": "empty",
                "order": spec["order"],
                "markdown": "⏳ 이 섹션은 현재 생성 중이거나 저장에 실패했습니다.\n\n잠시 후 다시 시도해주세요.",
                "content": "",
                "body_markdown": "",
                "raw_json": {},
                "char_count": 0,
                "error": "SECTION_MISSING",
            })
            logger.warning(f"[Reports] 🔥 탭 강제 생성: {sid} | job={job_id}")
    
    sections_normalized.sort(key=lambda x: x.get("order", 99))
    return sections_normalized


def build_full_markdown(sections: List[Dict], name: str = "고객", target_year: int = 2026) -> str:
    lines = [f"# {name}님의 {target_year}년 비즈니스 운세 리포트\n"]
    
    for section in sections:
        section_id = section.get("section_id") or section.get("id", "")
        title = section.get("title") or get_section_title(section_id)
        markdown = section.get("markdown") or ""
        
        if markdown and section.get("status") != "empty":
            lines.append(f"## {title}\n")
            lines.append(markdown)
            lines.append("\n---\n")
    
    return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 디버그 엔드포인트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
        "sections": [{
            "section_id": s.get("section_id"),
            "status": s.get("status"),
            "markdown_length": len(s.get("markdown") or ""),
        } for s in sections_raw],
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 고정 경로
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
    }
    
    supabase = get_supabase()
    
    if supabase and supabase.is_available():
        try:
            job = await supabase.create_job(
                email=payload.email,
                name=payload.name,
                input_data=input_data,
                target_year=payload.target_year
            )
            job_id = job["id"]
            public_token = job.get("public_token")
            
            logger.info(f"[Reports] Job 생성: {job_id}")
            
            try:
                await supabase.init_sections(job_id, SECTION_SPECS)
            except Exception as e:
                logger.warning(f"섹션 초기화 스킵: {e}")
            
            rulestore = getattr(request.app.state, "rulestore", None)
            background_tasks.add_task(run_report_job, job_id, rulestore)
            
            return {
                "success": True,
                "job_id": job_id,
                "token": public_token,
                "status": "queued",
                "message": "리포트 생성이 시작되었습니다.",
            }
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
    return {"sections": SECTION_SPECS}


@router.get("/view/{job_id}")
async def view_report(job_id: str, token: str = Query(..., description="Access token")):
    """
    🔥🔥🔥 P0: 탭 강제 - 7개 섹션 무조건 반환
    """
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
    
    # DB에서 섹션 조회
    sections_raw = await supabase.get_sections_ordered(job_id)
    sections_raw = [s for s in sections_raw if s.get("job_id") == job_id]
    
    # 🔥 P0 탭 강제: 7개 섹션 무조건 반환
    sections_normalized = ensure_all_sections(sections_raw, job_id)
    
    # 상태 체크
    job_status = job.get("status")
    db_section_count = len([s for s in sections_raw if s.get("section_id")])
    
    if job_status == "completed" and db_section_count == 0:
        logger.error(f"[Reports] ❌ COMPLETED인데 DB 섹션 0개: {job_id}")
    
    # full_markdown 생성
    input_json = job.get("input_json") or {}
    name = input_json.get("name", "고객")
    target_year = input_json.get("target_year", 2026)
    full_markdown = build_full_markdown(sections_normalized, name, target_year)
    
    logger.info(f"[Reports] view_report: {job_id} | db_sections={db_section_count} | total_tabs=7 | markdown_len={len(full_markdown)}")
    
    return {
        "job": {
            "id": job["id"],
            "status": job.get("status"),
            "progress": job.get("progress", 0),
            "completed_at": job.get("completed_at"),
            "error": job.get("error"),
        },
        "input": input_json,
        "sections": sections_normalized,
        "full_markdown": full_markdown,
        "section_count": 7,  # 🔥 항상 7
    }


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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 동적 경로
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
        
        return {
            "job_id": job_id,
            "status": job.get("status", "unknown"),
            "progress": progress,
            "sections": [{"id": s.get("section_id"), "status": s.get("status")} for s in sections_data],
        }
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
        
        return {
            "job_id": job_id,
            "status": job.get("status", "unknown"),
            "progress": job.get("progress", 0),
            "sections": [{"id": s.get("section_id"), "status": s.get("status")} for s in sections_data],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.get("/{job_id}/result")
async def get_report_result(job_id: str, token: Optional[str] = Query(None)):
    """
    🔥🔥🔥 P0: 탭 강제 - 7개 섹션 무조건 반환
    """
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
    
    # DB에서 섹션 조회
    sections_raw = await supabase.get_sections_ordered(job_id)
    sections_raw = [s for s in sections_raw if s.get("job_id") == job_id]
    
    # 🔥 P0 탭 강제: 7개 섹션 무조건 반환
    sections_normalized = ensure_all_sections(sections_raw, job_id)
    
    db_section_count = len([s for s in sections_raw if s.get("section_id")])
    if db_section_count == 0:
        logger.error(f"[Reports] ❌ result 요청인데 DB 섹션 0개: {job_id}")
    
    input_json = job.get("input_json") or {}
    name = input_json.get("name", "고객")
    target_year = input_json.get("target_year", 2026)
    full_markdown = build_full_markdown(sections_normalized, name, target_year)
    
    logger.info(f"[Reports] get_report_result: {job_id} | db_sections={db_section_count} | total_tabs=7")
    
    return {
        "completed": True,
        "job": {"id": job["id"], "status": job.get("status"), "completed_at": job.get("completed_at")},
        "input": input_json,
        "sections": sections_normalized,
        "full_markdown": full_markdown,
        "section_count": 7,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 백그라운드 작업
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
