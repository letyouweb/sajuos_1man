"""
SajuOS V1.0 하이브리드 엔진 - Main App
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 V1.1 수정 사항:
1. 404 에러 방지를 위한 라우터 프리픽스(Prefix) 정규화
2. 안전한 동적 임포트 구조 유지
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import os
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from importlib import import_module

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_git_sha() -> str:
    sha = os.environ.get("GIT_SHA") or os.environ.get("RAILWAY_GIT_COMMIT_SHA") or os.environ.get("RENDER_GIT_COMMIT")
    if sha: return sha[:8]
    try:
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0: return result.stdout.strip()[:8]
    except: pass
    return "unknown"

GIT_SHA = get_git_sha()
BUILD_TIME = os.environ.get("BUILD_TIME") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

app = FastAPI(title="SajuOS V1.0", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "git_sha": GIT_SHA,
        "build_time": BUILD_TIME,
        "version": "1.0.0",
    }

@app.get("/")
async def root():
    return {"service": "SajuOS V1.0", "status": "running", "engine": "hybrid"}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 P0: 안전한 라우터 등록 로직 (Prefix 수정 완료)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _safe_include_router(module_path: str, prefix: str, tags: list, label: str) -> None:
    try:
        m = import_module(module_path)
        router = getattr(m, "router")
        # 🔥 이중 경로 방지를 위해 프리픽스를 /api/v1으로 통일
        app.include_router(router, prefix=prefix, tags=tags)
        logger.info(f"✅ {label} 라우터 등록 완료 (prefix: {prefix})")
    except Exception as e:
        logger.error(f"❌ {label} 라우터 등록 실패: {e}")

# 모든 라우터를 /api/v1 하위로 등록. 
# 각 라우터 파일(calculate.py, reports.py 등)이 자신의 상세 경로를 가짐.
_safe_include_router("app.routers.calculate", "/api/v1", ["Calculate"], "calculate")
_safe_include_router("app.routers.interpret", "/api/v1", ["Interpret"], "interpret")
_safe_include_router("app.routers.reports", "/api/v1", ["Reports"], "reports") # ✅ 수정됨
_safe_include_router("app.routers.debug", "/api/v1", ["Debug"], "debug")       # ✅ 수정됨
_safe_include_router("app.routers.debug_engine", "/api/v1", ["Debug Engine"], "debug_engine")

@app.on_event("startup")
async def startup():
    logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info(f"🚀 SajuOS V1.0 하이브리드 엔진 가동 시작")
    logger.info(f"   GIT_SHA: {GIT_SHA}")
    logger.info(f"   BUILD_TIME: {BUILD_TIME}")
    logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    app.state.rulestore = None
    try:
        from app.services.rulecards_store import RuleCardStore
        base_dir = Path(__file__).parent.parent
        db_path = base_dir / "data" / "sajuos_master.db"
        
        if db_path.exists():
            store = RuleCardStore.load_from_sqlite_master(str(db_path))
            app.state.rulestore = store
            logger.info(f"✅ RuleCards master_db 로드 완료: 총 {len(store.cards)}장")
            
            from app.services.match_module import match_module
            match_module.store = store
            match_module.loaded = True
            logger.info(f"✅ Match 모듈에 RuleCards 주입 완료")
    except Exception as e:
        logger.warning(f"⚠️ RuleCards 로드 실패: {e}")

@app.get("/ready")
async def ready():
    checks = {
        "rulecards": app.state.rulestore is not None,
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "supabase": bool(os.getenv("SUPABASE_URL")),
    }
    return {"status": "ready" if checks["rulecards"] else "partial", "checks": checks}

@app.exception_handler(Exception)
async def error_handler(request: Request, exc: Exception):
    logger.error(f"Error: {exc}")
    return JSONResponse(status_code=500, content={"error": str(exc)[:100]})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))