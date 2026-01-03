"""
Reports API Router v10 - P0 Fix: markdown 컬럼 기준 조회 + full_markdown 생성
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
P0 핵심 수정:
1) /view, /result에서 섹션을 order대로 정렬
2) full_markdown = 섹션별 markdown을 순서대로 합침
3) completed인데 섹션 비면 → 경고 로그 + 500
4) sanitize_markdown() 적용
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any, List
import logging
import uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])


class ReportStartRequest(BaseModel):
    email: EmailStr
    gender: Optional[str] = None  # pass-through for daeun direction
    birth_info: Optional[Dict[str, Any]] = None  # pass-through for age/daeun
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


# 🔥 섹션 순서 (order)
SECTION_ORDER = ["exec", "money", "business", "team", "health", "calendar", "sprint"]

SECTION_SPECS = [
    {"id": "exec", "title": "Executive Summary", "order": 1},
    {"id": "money", "title": "Money & Cashflow", "order": 2},
    {"id": "business", "title": "Business Strategy", "order": 3},
    {"id": "team", "title": "Team & Partner", "order": 4},
    {"id": "health", "title": "Health & Performance", "order": 5},
    {"id": "calendar", "title": "12-Month Calendar", "order": 6},
    {"id": "sprint", "title": "90-Day Sprint", "order": 7},
]


def get_section_title(section_id: str) -> str:
    """section_id로 title 조회"""
    for spec in SECTION_SPECS:
        if spec["id"] == section_id:
            return spec["title"]
    return section_id or "Unknown"


def get_section_order(section_id: str) -> int:
    """section_id로 order 조회"""
    if section_id in SECTION_ORDER:
        return SECTION_ORDER.index(section_id) + 1
    return 99


def extract_markdown_from_section(section: Dict) -> str:
    """
    🔥 P0: 섹션에서 markdown 추출 (우선순위)
    1) section.markdown (DB 컬럼)
    2) raw_json.body_markdown
    3) raw_json → 마크다운 변환
    """
    # 1) 직접 markdown 필드 (DB 컬럼)
    if section.get("markdown"):
        return section["markdown"]
    
    # 2) raw_json에서 추출
    raw_json = section.get("raw_json") or {}
    
    if raw_json.get("body_markdown"):
        return raw_json["body_markdown"]
    
    if raw_json.get("content"):
        return raw_json["content"]
    
    # 3) raw_json 구조화 데이터 → 마크다운 변환
    if raw_json:
        return build_markdown_from_raw_json(section.get("section_id", ""), raw_json)
    
    return ""


def build_markdown_from_raw_json(section_id: str, raw_json: Dict) -> str:
    """raw_json을 마크다운으로 변환 (fallback)"""
    lines = []
    title = raw_json.get("title") or get_section_title(section_id)
    
    # body_markdown이 있으면 우선 사용
    if raw_json.get("body_markdown"):
        return raw_json["body_markdown"]
    
    # diagnosis
    diagnosis = raw_json.get("diagnosis")
    if diagnosis:
        lines.append("### 진단")
        if diagnosis.get("current_state"):
            lines.append(f"**현재 상태**: {diagnosis['current_state']}")
        if diagnosis.get("key_issues"):
            lines.append("**핵심 이슈**:")
            for issue in diagnosis["key_issues"]:
                lines.append(f"- {issue}")
        lines.append("")
    
    # hypotheses
    hypotheses = raw_json.get("hypotheses") or []
    if hypotheses:
        lines.append("### 가설")
        for h in hypotheses:
            lines.append(f"- **{h.get('id', '')}**: {h.get('statement', '')} (신뢰도: {h.get('confidence', '')})")
        lines.append("")
    
    # strategy_options
    options = raw_json.get("strategy_options") or []
    if options:
        lines.append("### 전략 옵션")
        for opt in options:
            lines.append(f"**{opt.get('name', '')}**: {opt.get('description', '')}")
        lines.append("")
    
    # recommended_strategy
    rec = raw_json.get("recommended_strategy")
    if rec:
        lines.append("### 추천 전략")
        lines.append(f"**선택**: {rec.get('selected_option', '')}")
        lines.append(f"**근거**: {rec.get('rationale', '')}")
        lines.append("")
    
    # kpis
    kpis = raw_json.get("kpis") or []
    if kpis:
        lines.append("### KPI")
        for kpi in kpis:
            lines.append(f"- **{kpi.get('metric', '')}**: 목표 {kpi.get('target', '')}")
        lines.append("")
    
    # risks
    risks = raw_json.get("risks") or []
    if risks:
        lines.append("### 리스크")
        for risk in risks:
            lines.append(f"- **{risk.get('risk', '')}**: {risk.get('mitigation', '')}")
        lines.append("")
    
    return "\n".join(lines)


def build_full_markdown(sections: List[Dict], name: str = "고객", target_year: int = 2026) -> str:
    """
    🔥 P0: 섹션들을 order대로 합쳐서 full_markdown 생성
    """
    lines = []
    lines.append(f"# {name}님의 {target_year}년 비즈니스 운세 리포트\n")
    
    for section in sections:
        section_id = section.get("section_id") or section.get("id", "")
        title = section.get("title") or get_section_title(section_id)
        markdown = section.get("markdown") or extract_markdown_from_section(section)
        
        if markdown:
            lines.append(f"## {title}\n")
            lines.append(markdown)
            lines.append("\n---\n")
    
    return "\n".join(lines)


def normalize_section(section: Dict) -> Dict:
    """
    🔥 P0: 섹션 정규화 (프론트엔드 호환)
    """
    section_id = section.get("section_id") or section.get("id", "")
    raw_json = section.get("raw_json") or {}
    markdown = section.get("markdown") or extract_markdown_from_section(section)
    
    return {
        "section_id": section_id,
        "id": section_id,  # 호환성
        "title": section.get("title") or get_section_title(section_id),
        "status": section.get("status", "completed"),
        "order": section.get("order") or get_section_order(section_id),
        # 🔥 핵심: markdown 필드
        "markdown": markdown,
        "content": markdown,  # 호환성
        "body_markdown": markdown,  # 호환성
        # raw_json (상세 데이터)
        "raw_json": raw_json,
        # 주요 필드 직접 노출
        "confidence": raw_json.get("confidence", "MEDIUM"),
        "diagnosis": raw_json.get("diagnosis"),
        "hypotheses": raw_json.get("hypotheses"),
        "strategy_options": raw_json.get("strategy_options"),
        "recommended_strategy": raw_json.get("recommended_strategy"),
        "kpis": raw_json.get("kpis"),
        "risks": raw_json.get("risks"),
        # Calendar
        "annual_theme": raw_json.get("annual_theme"),
        "monthly_plans": raw_json.get("monthly_plans"),
        "quarterly_milestones": raw_json.get("quarterly_milestones"),
        "peak_months": raw_json.get("peak_months"),
        "risk_months": raw_json.get("risk_months"),
        # Sprint
        "mission_statement": raw_json.get("mission_statement"),
        "phase_1_offer": raw_json.get("phase_1_offer"),
        "phase_2_funnel": raw_json.get("phase_2_funnel"),
        "phase_3_content": raw_json.get("phase_3_content"),
        "phase_4_automation": raw_json.get("phase_4_automation"),
        "milestones": raw_json.get("milestones"),
        "risk_scenarios": raw_json.get("risk_scenarios"),
        # 메타
        "char_count": section.get("char_count") or len(markdown),
        "error": section.get("error"),
        "updated_at": section.get("updated_at"),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 디버그 엔드포인트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/debug/{job_id}")
async def debug_job(job_id: str):
    """디버그용: DB에서 직접 job + sections 조회"""
    supabase = get_supabase()
    
    if not supabase or not supabase.is_available():
        return {"error": "Supabase 미연결"}
    
    job = await supabase.get_job(job_id)
    if not job:
        return {"error": f"Job not found: {job_id}"}
    
    sections_raw = await supabase.get_sections_ordered(job_id)
    
    sections_debug = []
    for s in sections_raw:
        markdown = s.get("markdown") or ""
        raw_json = s.get("raw_json") or {}
        sections_debug.append({
            "section_id": s.get("section_id"),
            "status": s.get("status"),
            "order": s.get("order"),
            "markdown_length": len(markdown),
            "has_raw_json": bool(raw_json),
            "raw_json_body_length": len(raw_json.get("body_markdown", "")),
            "markdown_preview": markdown[:200] + "..." if len(markdown) > 200 else markdown,
        })
    
    return {
        "job_id": job_id,
        "job_status": job.get("status"),
        "job_progress": job.get("progress"),
        "completed_at": job.get("completed_at"),
        "sections_count": len(sections_raw),
        "sections_debug": sections_debug,
        "has_result_json": bool(job.get("result_json")),
        "has_markdown": bool(job.get("markdown")),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 고정 경로 먼저
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/start")
async def start_report(
    payload: ReportStartRequest,
    background_tasks: BackgroundTasks,
    request: Request
):
    """리포트 생성 시작"""
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
        "gender": payload.gender,
        "birth_info": payload.birth_info,
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
            
            # 섹션 초기화
            try:
                await supabase.init_sections(job_id, SECTION_SPECS)
            except Exception as e:
                logger.warning(f"섹션 초기화 스킵: {e}")
            
            # 백그라운드 작업
            rulestore = getattr(request.app.state, "rulestore", None)
            background_tasks.add_task(run_report_job, job_id, rulestore)
            
            # 🔥 P0: 표준화된 응답
            return {
                "success": True,
                "job_id": job_id,
                "token": public_token,
                "status": "queued",
                "message": "리포트 생성이 시작되었습니다.",
                "view_url": f"https://sajuos.com/report/{job_id}?token={public_token}",
                "full_view_url": f"https://sajuos.com/report/{job_id}?token={public_token}&view=full",
            }
        except Exception as e:
            logger.error(f"Job 생성 실패: {e}")
            raise HTTPException(status_code=500, detail=str(e)[:300])
    else:
        temp_id = str(uuid.uuid4())
        return {
            "success": True,
            "job_id": temp_id,
            "status": "queued",
            "message": "리포트 생성 시작 (Supabase 미연결)",
        }


@router.get("/start")
async def start_report_get():
    """GET /start는 지원하지 않음"""
    return {"error": "Use POST method", "method": "POST /api/reports/start"}


@router.get("/sections-info")
async def get_sections_info():
    """섹션 정보"""
    return {"sections": SECTION_SPECS}


@router.get("/view/{job_id}")
async def view_report(job_id: str, token: str = Query(..., description="Access token")):
    """
    🔥🔥🔥 P0 핵심: job + sections(order 정렬) + full_markdown 반환
    중복 방지: job_id로 필터링된 섹션만 반환
    """
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid job_id format: {job_id}")
    
    supabase = get_supabase()
    
    if not supabase or not supabase.is_available():
        raise HTTPException(status_code=503, detail="Supabase 미연결")
    
    # 1) token 검증
    is_valid, job = await supabase.verify_job_token(job_id, token)
    
    if not is_valid or not job:
        raise HTTPException(status_code=404, detail="Invalid token or job not found")
    
    # 2) 🔥 P0: sections 조회 (order 정렬) - job_id로 필터링 확실히
    sections_raw = await supabase.get_sections_ordered(job_id)
    
    # 🔥 P0: 중복 방지 - job_id가 일치하는지 재확인
    sections_raw = [s for s in sections_raw if s.get("job_id") == job_id]
    
    # 3) 섹션 정규화
    sections_normalized = [normalize_section(s) for s in sections_raw]
    
    # 4) 🔥 P0: completed인데 섹션 비면 경고
    if job.get("status") == "completed":
        empty_sections = [s["section_id"] for s in sections_normalized if len(s.get("markdown", "")) < 100]
        if empty_sections:
            logger.error(f"[Reports] ⚠️ COMPLETED인데 빈 섹션: {job_id} | {empty_sections}")
            logger.error(f"[Reports] 섹션 개수: {len(sections_normalized)} | Job: {job_id}")
    
    # 5) full_markdown 생성
    input_json = job.get("input_json") or {}
    name = input_json.get("name", "고객")
    target_year = input_json.get("target_year", 2026)
    full_markdown = build_full_markdown(sections_normalized, name, target_year)
    
    # 6) saju_result.quality 기본값
    saju_result = input_json.get("saju_result") or {}
    if "quality" not in saju_result:
        saju_result["quality"] = {}
    
    quality_defaults = {
        "solar_term_boundary": None,
        "has_birth_time": bool(saju_result.get("saju", {}).get("hour_pillar")),
        "accuracy": "MEDIUM",
        "notes": [],
    }
    for key, default_val in quality_defaults.items():
        if key not in saju_result["quality"]:
            saju_result["quality"][key] = default_val
    
    input_json["saju_result"] = saju_result
    
    # 🔥 P0 FIX: ready 플래그 계산 (빈 본문 노출 방지)
    completed_sections = len([s for s in sections_normalized if len(s.get("markdown", "")) >= 200])
    total_markdown_length = sum(len(s.get("markdown", "")) for s in sections_normalized)
    is_ready = completed_sections >= 1 and total_markdown_length >= 500
    
    # 7) 응답 반환
    logger.info(f"[Reports] view_report: {job_id} | sections={len(sections_normalized)} | markdown_length={len(full_markdown)} | ready={is_ready}")
    
    return {
        "job": {
            "id": job["id"],
            "status": job.get("status"),
            "progress": job.get("progress", 0),
            "result_json": job.get("result_json"),
            "completed_at": job.get("completed_at"),
            "error": job.get("error"),
            "target_year": input_json.get("target_year"),  # 🔥 P0: target_year 추가
        },
        "input": input_json,
        "sections": sections_normalized,
        "full_markdown": full_markdown,
        "section_count": len(sections_normalized),
        "ready": is_ready,  # 🔥 P0: 콘텐츠 준비 완료 여부
        "completed_section_count": completed_sections,  # 🔥 P0: 실제 완료된 섹션 수
    }


@router.get("/verify/{job_id}")
async def verify_token(job_id: str, token: str = Query(..., description="Access token")):
    """job_id + token 검증"""
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid job_id format: {job_id}")
    
    supabase = get_supabase()
    
    if not supabase or not supabase.is_available():
        raise HTTPException(status_code=503, detail="Supabase 미연결")
    
    is_valid, job = await supabase.verify_job_token(job_id, token)
    
    if not is_valid:
        raise HTTPException(status_code=403, detail="Invalid token")
    
    return {
        "valid": True,
        "job_id": job["id"],
        "status": job.get("status"),
        "progress": job.get("progress", 0),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 동적 경로는 마지막에
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/{job_id}/status")
async def get_job_status(job_id: str):
    """폴링용 상태 조회"""
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid job_id format: {job_id}")
    
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
            "error": job.get("error"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.get("/{job_id}")
async def get_report_status(job_id: str, token: Optional[str] = Query(None)):
    """폴링용 상태 조회"""
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid job_id format: {job_id}")
    
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
            "error": job.get("error"),
            "result": job.get("result_json") if job.get("status") == "completed" else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.get("/{job_id}/result")
async def get_report_result(job_id: str, token: Optional[str] = Query(None)):
    """
    🔥🔥🔥 P0 핵심: /result - 섹션 order대로 정렬 + full_markdown 생성
    중복 방지: job_id로 필터링된 섹션만 반환
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
    
    # 🔥 P0: sections 조회 (order 정렬) - job_id로 필터링 확실히
    sections_raw = await supabase.get_sections_ordered(job_id)
    
    # 🔥 P0: 중복 방지 - job_id가 일치하는지 재확인
    sections_raw = [s for s in sections_raw if s.get("job_id") == job_id]
    
    # 섹션 정규화
    sections_normalized = [normalize_section(s) for s in sections_raw]
    
    # 🔥 P0: completed인데 섹션 비면 경고 (500은 너무 과함)
    empty_sections = [s["section_id"] for s in sections_normalized if len(s.get("markdown", "")) < 100]
    if empty_sections:
        logger.error(f"[Reports] ⚠️ COMPLETED인데 빈 섹션: {job_id} | {empty_sections}")
        logger.error(f"[Reports] 섹션 개수: {len(sections_normalized)} | Job: {job_id}")
        # 경고만 남기고 진행
    
    # full_markdown 생성
    input_json = job.get("input_json") or {}
    name = input_json.get("name", "고객")
    target_year = input_json.get("target_year", 2026)
    full_markdown = build_full_markdown(sections_normalized, name, target_year)
    
    logger.info(f"[Reports] get_report_result: {job_id} | sections={len(sections_normalized)} | markdown_length={len(full_markdown)}")
    
    return {
        "completed": True,
        "job": {
            "id": job["id"],
            "status": job.get("status"),
            "completed_at": job.get("completed_at"),
            "result_json": job.get("result_json"),
        },
        "input": input_json,
        "sections": sections_normalized,
        "full_markdown": full_markdown,
        "section_count": len(sections_normalized),
        "result": job.get("result_json"),
        "markdown": full_markdown,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 백그라운드 작업
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def run_report_job(job_id: str, rulestore):
    """백그라운드 리포트 생성"""
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
