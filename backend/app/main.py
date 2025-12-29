"""
SajuOS V1.0 하이브리드 엔진 - Main App
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 V1.0 핵심 개선:
1. RuleCards 로드 상태 상세 로그 (토픽별 분포)
2. Match 모듈 자동 주입
3. 디버그 엔드포인트 활성화
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import os
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 App 선언 (최상단)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
app = FastAPI(title="SajuOS V1.0", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 /health - 무조건 즉시 OK (최우선)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"service": "SajuOS V1.0", "status": "running", "engine": "hybrid"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 라우터 등록 (try-except로 보호)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
try:
    from app.routers import calculate, interpret
    app.include_router(calculate.router, prefix="/api/v1", tags=["Calculate"])
    app.include_router(interpret.router, prefix="/api/v1", tags=["Interpret"])
    logger.info("✅ calculate, interpret 라우터 등록")
except Exception as e:
    logger.error(f"❌ 기본 라우터 등록 실패: {e}")

try:
    from app.routers import reports
    app.include_router(reports.router, prefix="/api/v1", tags=["Reports"])
    app.include_router(reports.router, prefix="/api", include_in_schema=False)
    logger.info("✅ reports 라우터 등록 (/api/v1/reports + /api/reports)")
except Exception as e:
    logger.error(f"❌ reports 라우터 등록 실패: {e}")

# 🔥 Debug 라우터 추가
try:
    from app.routers import debug
    app.include_router(debug.router, prefix="/api/v1", tags=["Debug"])
    logger.info("✅ debug 라우터 등록 (/api/v1/debug)")
except Exception as e:
    logger.error(f"❌ debug 라우터 등록 실패: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 Startup - RuleCards 로드 + Match 모듈 주입
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.on_event("startup")
async def startup():
    logger.info(f"")
    logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info(f"🚀 SajuOS V1.0 하이브리드 엔진 가동 시작")
    logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info(f"   PORT: {os.getenv('PORT', 'unknown')}")
    logger.info(f"")
    
    # 🔥🔥🔥 RuleCards 로드 (상세 로그)
    app.state.rulestore = None
    try:
        from app.services.rulecards_store import RuleCardStore
        
        # 가능한 경로들
        possible_paths = [
            "/app/data/sajuos_master_db.jsonl",
            "data/sajuos_master_db.jsonl",
            "data/rulecards.jsonl",
            "temp_rulecards.jsonl",
            str(Path(__file__).parent.parent / "data" / "rulecards.jsonl"),
            str(Path(__file__).parent.parent / "temp_rulecards.jsonl")
        ]
        
        loaded = False
        for p in possible_paths:
            if os.path.exists(p):
                logger.info(f"[RuleCards] 파일 발견: {p}")
                store = RuleCardStore(p)
                store.load()
                app.state.rulestore = store
                
                # 🔥 상세 로그 출력
                total_cards = len(store.cards)
                logger.info(f"")
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                logger.info(f"✅ RuleCards 로드 완료: 총 {total_cards}장")
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                
                # 토픽별 분포
                if store.by_topic:
                    logger.info(f"📊 토픽별 분포:")
                    for topic, cards in sorted(store.by_topic.items()):
                        logger.info(f"   - {topic}: {len(cards)}장")
                else:
                    logger.warning(f"⚠️ 토픽별 인덱스가 비어있습니다")
                
                # IDF 토큰 수
                if store.idf:
                    logger.info(f"")
                    logger.info(f"📝 IDF 토큰: {len(store.idf)}개")
                
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                logger.info(f"")
                
                # 🔥🔥🔥 Match 모듈에 RuleCards 주입
                try:
                    from app.services.match_module import match_module
                    match_module.store = store
                    match_module.loaded = True
                    logger.info(f"✅ Match 모듈에 RuleCards 주입 완료")
                    logger.info(f"")
                except Exception as me:
                    logger.warning(f"⚠️ Match 모듈 주입 실패: {me}")
                
                loaded = True
                break
        
        if not loaded:
            logger.warning(f"")
            logger.warning(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.warning(f"⚠️ RuleCards 파일을 찾을 수 없습니다")
            logger.warning(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.warning(f"   시도한 경로:")
            for p in possible_paths:
                logger.warning(f"     - {p}")
            logger.warning(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.warning(f"")
            
    except Exception as e:
        logger.warning(f"⚠️ RuleCards 로드 실패 (계속 진행): {e}")
        import traceback
        logger.warning(traceback.format_exc())
    
    logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info(f"✅ Startup 완료 - SajuOS V1.0 준비 완료")
    logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info(f"")


@app.get("/ready")
async def ready():
    """
    서버 준비 상태 확인
    
    Returns:
        - rulecards: RuleCards 로드 여부
        - openai: OpenAI API 키 설정 여부
        - supabase: Supabase 연결 여부
    """
    checks = {
        "rulecards": app.state.rulestore is not None,
        "rulecards_count": len(app.state.rulestore.cards) if app.state.rulestore else 0,
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "supabase": bool(os.getenv("SUPABASE_URL")),
    }
    return {"status": "ready" if all([checks["rulecards"], checks["openai"], checks["supabase"]]) else "partial", "checks": checks}


@app.exception_handler(Exception)
async def error_handler(request: Request, exc: Exception):
    logger.error(f"Error: {exc}")
    return JSONResponse(status_code=500, content={"error": str(exc)[:100]})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
