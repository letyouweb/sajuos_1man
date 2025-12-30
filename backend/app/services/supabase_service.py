"""
Supabase Service v14 - P0 Fix
- calendar_cache 지원
- report_jobs / report_sections 지원
- body_markdown CANONICAL COLUMN 보장
- RC-xxxx / 근거 제거 sanitize
"""

import os
import re
import time
import secrets
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime

from supabase import create_client, Client

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 P0: sanitize 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def sanitize_report_content(text: str) -> str:
    """
    리포트 본문에서 내부 토큰 제거
    - RC-xxxx 토큰 제거
    - "### 근거:" 류 제거
    - 과한 줄바꿈 정리
    """
    if not text:
        return ""
    text = re.sub(r"\[?RC-[A-Za-z0-9_-]+\]?", "", text)
    text = re.sub(r"#+\s*근거:.*", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 섹션 정의
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SECTION_SPECS = [
    {"id": "business_climate", "title": "🌦️ 2026 비즈니스 전략 기상도", "order": 1},
    {"id": "cashflow", "title": "💰 자본 유동성 및 현금흐름 최적화", "order": 2},
    {"id": "market_product", "title": "📍 시장 포지셔닝 및 상품 확장 전략", "order": 3},
    {"id": "team_partnership", "title": "🤝 조직 확장 및 파트너십 가이드", "order": 4},
    {"id": "owner_risk", "title": "🧯 오너 리스크 관리 및 번아웃 방어", "order": 5},
    {"id": "sprint_12m", "title": "🗓️ 12개월 비즈니스 스프린트 캘린더", "order": 6},
    {"id": "action_90d", "title": "🚀 향후 90일 매출 극대화 액션플랜", "order": 7},
]

SECTION_ORDER = [s["id"] for s in SECTION_SPECS]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Supabase Service
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SupabaseService:
    """
    - Lazy init
    - service_role 키는 백엔드 전용
    """
    _client: Optional[Client] = None
    _last_init_ts: float = 0.0

    # -----------------------------
    # Client
    # -----------------------------
    def _get_client(self) -> Client:
        if self._client is None:
            url = os.getenv("SUPABASE_URL", "").strip()
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            if not url or not key:
                raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY is not set")
            self._client = create_client(url, key)
            self._last_init_ts = time.time()
            logger.info("✅ Supabase 연결 완료")
        return self._client

    def is_available(self) -> bool:
        return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

    # -----------------------------
    # calendar_cache
    # -----------------------------
    def get_calendar_cache(self, sol_year: int, sol_month: int, sol_day: int) -> Optional[Dict[str, Any]]:
        try:
            res = (
                self._get_client()
                .table("calendar_cache")
                .select("payload, fetched_at, source")
                .eq("sol_year", sol_year)
                .eq("sol_month", sol_month)
                .eq("sol_day", sol_day)
                .limit(1)
                .execute()
            )
            return res.data[0] if res.data else None
        except Exception:
            return None

    def upsert_calendar_cache(
        self,
        sol_year: int,
        sol_month: int,
        sol_day: int,
        payload: Dict[str, Any],
        source: str = "kasi",
    ) -> None:
        try:
            (
                self._get_client()
                .table("calendar_cache")
                .upsert(
                    {
                        "sol_year": sol_year,
                        "sol_month": sol_month,
                        "sol_day": sol_day,
                        "payload": payload,
                        "source": source,
                    },
                    on_conflict="sol_year,sol_month,sol_day",
                )
                .execute()
            )
        except Exception:
            pass

    # -----------------------------
    # report_jobs
    # -----------------------------
    def create_job(self, input_json: Dict[str, Any]) -> str:
        res = (
            self._get_client()
            .table("report_jobs")
            .insert({
                "status": "queued",
                "progress": 0,
                "current_step": "queued",
                "input_json": input_json,
                "public_token": secrets.token_hex(16),
            })
            .execute()
        )
        return res.data[0]["id"]

    def update_job_progress(self, job_id: str, progress: int, step: str) -> None:
        self._get_client().table("report_jobs").update(
            {"status": "running", "progress": progress, "current_step": step}
        ).eq("id", job_id).execute()

    def complete_job(
        self,
        job_id: str,
        result_json: Dict[str, Any],
        result_markdown: str = "",
        saju_json: Dict[str, Any] = None,
    ) -> None:
        data = {
            "status": "completed",
            "progress": 100,
            "current_step": "done",
            "completed_at": datetime.utcnow().isoformat(),
            "result_json": result_json,
        }
        if result_markdown:
            data["markdown"] = sanitize_report_content(result_markdown)
        if saju_json:
            data["saju_json"] = saju_json

        self._get_client().table("report_jobs").update(data).eq("id", job_id).execute()

    def fail_job(self, job_id: str, error_message: str) -> None:
        self._get_client().table("report_jobs").update(
            {"status": "failed", "error_message": error_message[:500]}
        ).eq("id", job_id).execute()

    # -----------------------------
    # report_sections
    # -----------------------------
    def save_section(
        self,
        job_id: str,
        section_id: str,
        section_json: Dict[str, Any],
    ) -> None:
        client = self._get_client()

        md_raw = (
            section_json.get("body_markdown")
            or section_json.get("markdown")
            or section_json.get("content")
            or ""
        )
        md = sanitize_report_content(md_raw)

        data = {
            "job_id": job_id,
            "section_id": section_id,
            "status": "completed",
            "progress": 100,
            "raw_json": section_json,
            "body_markdown": md,   # 🔥 CANONICAL
            "markdown": md,        # 하위호환
            "content": md,         # 하위호환
            "char_count": len(md),
        }

        if section_id in SECTION_ORDER:
            data["section_order"] = SECTION_ORDER.index(section_id) + 1

        client.table("report_sections").upsert(
            data,
            on_conflict="job_id,section_id",
        ).execute()


# 싱글톤
supabase_service = SupabaseService()
