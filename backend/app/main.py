"""
SajuOS V1.0 하이브리드 엔진 - Main App
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 V1.0 핵심 개선:
1. sajuos_master.db 우선 로드 (SQLite)
2. RuleCards 콘텐츠 주입 보장
3. Match 모듈 자동 주입
4. P0: 라우터 로딩 구조 분리 (import_module 적용)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import os
import logging
import subprocess
from pathlib import Path
from importlib import import_module

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🔥 P0: GIT_SHA 추출 (배포 증명용)
def get_git_sha() -> str:
    """Git commit SHA 추출"""
    sha = os.environ.get("GIT_SHA") or os.environ.get("RAILWAY_GIT_COMMIT_SHA") or os.environ.get("RENDER_GIT_COMMIT")
    if sha:
        return sha[:8]
    try:
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()[:8]
    except:
        pass
    return "unknown"

GIT_SHA = get_git_sha()

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
    return {"status": "ok", "git_sha": GIT_SHA}

@app.get("/")
async def root():
    return {"service": "SajuOS V1.0", "status": "running", "engine": "hybrid"}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 P0: 안전한 라우터 등록 로직
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _safe_include_router(module_path: str, prefix: str, tags: list, label: str) -> None:
    """모듈 임포트 에러가 다른 라우터에 영향을 주지 않도록 안전하게 등록"""
    try:
        m = import_module(module_path)
        router = getattr(m, "router")
        app.include_router(router, prefix=prefix, tags=tags)
        logger.info(f"✅ {label} 라우터 등록 완료 (prefix: {prefix})")
    except Exception as e:
        logger.error(f"❌ {label} 라우터 등록 실패: {e}")

# 라우터 등록 실행
_safe_include_router("app.routers.calculate", "/api/v1", ["Calculate"], "calculate")
_safe_include_router("app.routers.interpret", "/api/v1", ["Interpret"], "interpret")
_safe_include_router("app.routers.reports", "/api/v1/reports", ["Reports"], "reports")
_safe_include_router("app.routers.debug", "/api/v1/debug", ["Debug"], "debug")
_safe_include_router("app.routers.debug_engine", "/api/v1/debug_engine", ["Debug Engine"], "debug_engine")


@app.on_event("startup")
async def startup():
    logger.info(f"")
    logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info(f"🚀 SajuOS V1.0 하이브리드 엔진 가동 시작")
    logger.info(f"🔥 GIT_SHA: {GIT_SHA}")
    logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    app.state.rulestore = None
    try:
        from app.services.rulecards_store import RuleCardStore
        
        base_dir = Path(__file__).parent.parent
        master_db_paths = [
            base_dir / "data" / "sajuos_master.db",
            Path("/app/data/sajuos_master.db"),
            Path("data/sajuos_master.db"),
        ]
        jsonl_paths = [
            base_dir / "data" / "sajuos_master_db.jsonl",
            base_dir / "data" / "rulecards.jsonl",
            Path("/app/data/rulecards.jsonl"),
            Path("data/rulecards.jsonl"),
        ]
        
        store = None
        source = None
        
        for db_path in master_db_paths:
            if db_path.exists():
                logger.info(f"[RuleCards] master_db 발견: {db_path}")
                store = RuleCardStore.load_from_sqlite_master(str(db_path))
                source = "master_db"
                break
        
        if not store:
            for jsonl_path in jsonl_paths:
                if jsonl_path.exists():
                    logger.info(f"[RuleCards] JSONL 발견: {jsonl_path}")
                    store = RuleCardStore(str(jsonl_path))
                    store.load()
                    source = "jsonl"
                    break
        
        if store:
            app.state.rulestore = store
            total = len(store.cards)
            logger.info(f"✅ RuleCards source={source} | 로드 완료: 총 {total}장")
            
            try:
                from app.services.match_module import match_module
                match_module.store = store
                match_module.loaded = True
                logger.info(f"✅ Match 모듈에 RuleCards 주입 완료")
            except Exception as me:
                logger.warning(f"⚠️ Match 모듈 주입 실패: {me}")
        else:
            logger.warning(f"⚠️ RuleCards 파일을 찾을 수 없습니다")
            
    except Exception as e:
        logger.warning(f"⚠️ RuleCards 로드 실패: {e}")
    
    # 🔥 P0: DB 걸록 잔존 체크 + 자동 패치
    try:
        import sqlite3
        db_path = None
        for p in [Path(__file__).parent.parent / "data" / "sajuos_master.db", Path("/app/data/sajuos_master.db")]:
            if p.exists():
                db_path = str(p)
                break
        
        if db_path:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cols = ["trigger_json", "mechanism", "interpretation", "action", "tags_json", "cautions_json"]
            total_typo = 0
            for c in cols:
                try:
                    n = cur.execute(f"SELECT COUNT(*) FROM rule_cards WHERE {c} LIKE '%걸록%'").fetchone()[0]
                    total_typo += n
                except: pass
            
            if total_typo > 0:
                logger.warning(f"⚠️ '걸록' 오타 {total_typo}개 발견! 자동 패치 실행...")
                for c in cols:
                    try:
                        cur.execute(f"UPDATE rule_cards SET {c} = REPLACE({c}, '걸록', '건록') WHERE {c} LIKE '%걸록%'")
                    except: pass
                conn.commit()
                logger.info(f"✅ '걸록' → '건록' 자동 패치 완료")
            conn.close()
    except Exception as typo_err:
        logger.debug(f"[RuleCards] 오타 체크 스킵: {typo_err}")
    
    logger.info(f"✅ Startup 완료")


@app.get("/ready")
async def ready():
    checks = {
        "rulecards": app.state.rulestore is not None,
        "rulecards_count": len(app.state.rulestore.cards) if app.state.rulestore else 0,
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "supabase": bool(os.getenv("SUPABASE_URL")),
    }
    return {"status": "ready" if checks["rulecards"] and checks["openai"] else "partial", "checks": checks, "git_sha": GIT_SHA}


@app.exception_handler(Exception)
async def error_handler(request: Request, exc: Exception):
    logger.error(f"Error: {exc}")
    return JSONResponse(status_code=500, content={"error": str(exc)[:100]})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))