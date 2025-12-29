"""
Supabase Store - 프리미엄 리포트 영구 저장
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- reports 테이블: 리포트 메타데이터 + 상태
- report_sections 테이블: 섹션별 콘텐츠 (재시도 시 스킵용)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from supabase import create_client, Client

from app.config import get_settings

logger = logging.getLogger(__name__)

# 섹션 정의 (순서 중요)
SECTION_SPECS = [
    {"id": "exec", "title": "Executive Summary", "order": 1},
    {"id": "money", "title": "Money & Cashflow", "order": 2},
    {"id": "business", "title": "Business Strategy", "order": 3},
    {"id": "team", "title": "Team & Partner", "order": 4},
    {"id": "health", "title": "Health & Performance", "order": 5},
    {"id": "calendar", "title": "12-Month Calendar", "order": 6},
    {"id": "sprint", "title": "90-Day Sprint", "order": 7},
]


class SupabaseStore:
    """Supabase 기반 리포트 저장소"""
    
    _instance: Optional["SupabaseStore"] = None
    _client: Optional[Client] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def _get_client(self) -> Client:
        """Supabase 클라이언트 (lazy init)"""
        if self._client is None:
            settings = get_settings()
            if not settings.supabase_url or not settings.supabase_service_role_key:
                raise RuntimeError("Supabase 설정이 없습니다. SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY 확인")
            self._client = create_client(
                settings.supabase_url,
                settings.supabase_service_role_key
            )
        return self._client
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Reports CRUD
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def create_report(
        self,
        email: str,
        name: str,
        input_data: Dict[str, Any],
        target_year: int = 2026
    ) -> Dict[str, Any]:
        """새 리포트 생성 + 섹션 초기화"""
        client = self._get_client()
        
        # 1. reports 테이블에 삽입
        report_data = {
            "email": email,
            "name": name,
            "input_data": input_data,
            "status": "pending",
            "progress": 0,
            "current_step": "대기 중",
            "target_year": target_year,
        }
        
        result = client.table("reports").insert(report_data).execute()
        
        if not result.data:
            raise Exception("리포트 생성 실패")
        
        report = result.data[0]
        report_id = report["id"]
        
        logger.info(f"[SupabaseStore] 리포트 생성: {report_id}")
        
        # 2. report_sections 초기화
        sections_data = [
            {
                "report_id": report_id,
                "section_id": spec["id"],
                "section_title": spec["title"],
                "section_order": spec["order"],
                "status": "pending",
            }
            for spec in SECTION_SPECS
        ]
        
        client.table("report_sections").insert(sections_data).execute()
        
        logger.info(f"[SupabaseStore] 섹션 {len(sections_data)}개 초기화 완료")
        
        return report
    
    async def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """리포트 조회"""
        client = self._get_client()
        result = client.table("reports").select("*").eq("id", report_id).execute()
        return result.data[0] if result.data else None
    
    async def get_report_by_token(self, access_token: str) -> Optional[Dict[str, Any]]:
        """토큰으로 리포트 조회 (이메일 링크용)"""
        client = self._get_client()
        result = client.table("reports").select("*").eq("access_token", access_token).execute()
        return result.data[0] if result.data else None
    
    async def get_report_with_sections(self, report_id: str) -> Optional[Dict[str, Any]]:
        """리포트 + 섹션 전체 조회"""
        client = self._get_client()
        
        # 리포트 조회
        report_result = client.table("reports").select("*").eq("id", report_id).execute()
        if not report_result.data:
            return None
        
        report = report_result.data[0]
        
        # 섹션 조회
        sections_result = (
            client.table("report_sections")
            .select("*")
            .eq("report_id", report_id)
            .order("section_order")
            .execute()
        )
        
        report["sections"] = sections_result.data or []
        return report
    
    async def update_report_status(
        self,
        report_id: str,
        status: str,
        progress: int = None,
        current_step: str = None,
        error: str = None
    ) -> None:
        """리포트 상태 업데이트"""
        client = self._get_client()
        
        update_data = {"status": status}
        if progress is not None:
            update_data["progress"] = progress
        if current_step is not None:
            update_data["current_step"] = current_step
        if error is not None:
            update_data["error"] = error
        
        client.table("reports").update(update_data).eq("id", report_id).execute()
        
        logger.info(f"[SupabaseStore] 상태 업데이트: {report_id} → {status} ({progress}%)")
    
    async def complete_report(
        self,
        report_id: str,
        result_json: Dict[str, Any],
        pdf_url: Optional[str] = None,
        generation_time_ms: int = 0,
        total_tokens_used: int = 0
    ) -> None:
        """리포트 완료 처리"""
        client = self._get_client()
        
        update_data = {
            "status": "completed",
            "progress": 100,
            "current_step": "완료",
            "result_json": result_json,
            "completed_at": datetime.utcnow().isoformat(),
            "generation_time_ms": generation_time_ms,
            "total_tokens_used": total_tokens_used,
        }
        
        if pdf_url:
            update_data["pdf_url"] = pdf_url
        
        client.table("reports").update(update_data).eq("id", report_id).execute()
        
        logger.info(f"[SupabaseStore] ✅ 리포트 완료: {report_id}")
    
    async def fail_report(self, report_id: str, error: str) -> None:
        """리포트 실패 처리"""
        client = self._get_client()
        
        # retry_count 증가
        report = await self.get_report(report_id)
        retry_count = (report.get("retry_count", 0) if report else 0) + 1
        
        client.table("reports").update({
            "status": "failed",
            "error": error[:1000],
            "retry_count": retry_count,
        }).eq("id", report_id).execute()
        
        logger.error(f"[SupabaseStore] ❌ 리포트 실패: {report_id} | {error[:100]}")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Sections CRUD
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def get_sections(self, report_id: str) -> List[Dict[str, Any]]:
        """리포트의 모든 섹션 조회"""
        client = self._get_client()
        result = (
            client.table("report_sections")
            .select("*")
            .eq("report_id", report_id)
            .order("section_order")
            .execute()
        )
        return result.data or []
    
    async def get_pending_sections(self, report_id: str) -> List[Dict[str, Any]]:
        """미완료 섹션만 조회 (재시도용)"""
        client = self._get_client()
        result = (
            client.table("report_sections")
            .select("*")
            .eq("report_id", report_id)
            .neq("status", "completed")
            .order("section_order")
            .execute()
        )
        return result.data or []
    
    async def update_section_start(self, report_id: str, section_id: str) -> None:
        """섹션 시작"""
        client = self._get_client()
        
        # 섹션 상태 업데이트
        client.table("report_sections").update({
            "status": "generating",
            "started_at": datetime.utcnow().isoformat(),
        }).eq("report_id", report_id).eq("section_id", section_id).execute()
        
        # 리포트 current_step 업데이트
        section_title = next(
            (s["title"] for s in SECTION_SPECS if s["id"] == section_id),
            section_id
        )
        
        # progress 계산 (섹션 순서 기반)
        section_order = next(
            (s["order"] for s in SECTION_SPECS if s["id"] == section_id),
            1
        )
        progress = int((section_order - 1) / len(SECTION_SPECS) * 100)
        
        await self.update_report_status(
            report_id,
            status="generating",
            progress=progress,
            current_step=f"{section_title} 생성 중..."
        )
    
    async def update_section_complete(
        self,
        report_id: str,
        section_id: str,
        content_json: Dict[str, Any],
        char_count: int = 0,
        rulecard_count: int = 0,
        elapsed_ms: int = 0
    ) -> None:
        """섹션 완료"""
        client = self._get_client()
        
        client.table("report_sections").update({
            "status": "completed",
            "content_json": content_json,
            "char_count": char_count,
            "rulecard_count": rulecard_count,
            "completed_at": datetime.utcnow().isoformat(),
            "elapsed_ms": elapsed_ms,
        }).eq("report_id", report_id).eq("section_id", section_id).execute()
        
        # 리포트 progress 업데이트
        sections = await self.get_sections(report_id)
        completed = sum(1 for s in sections if s["status"] == "completed")
        progress = int(completed / len(SECTION_SPECS) * 100)
        
        section_title = next(
            (s["title"] for s in SECTION_SPECS if s["id"] == section_id),
            section_id
        )
        
        await self.update_report_status(
            report_id,
            status="generating",
            progress=progress,
            current_step=f"{section_title} 완료"
        )
        
        logger.info(f"[SupabaseStore] ✅ 섹션 완료: {section_id} ({progress}%)")
    
    async def update_section_fail(
        self,
        report_id: str,
        section_id: str,
        error: str
    ) -> None:
        """섹션 실패"""
        client = self._get_client()
        
        # attempt_count 증가
        section_result = (
            client.table("report_sections")
            .select("attempt_count")
            .eq("report_id", report_id)
            .eq("section_id", section_id)
            .execute()
        )
        
        attempt_count = 1
        if section_result.data:
            attempt_count = (section_result.data[0].get("attempt_count", 0) or 0) + 1
        
        client.table("report_sections").update({
            "status": "failed",
            "error": error[:500],
            "attempt_count": attempt_count,
        }).eq("report_id", report_id).eq("section_id", section_id).execute()
        
        logger.warning(f"[SupabaseStore] ⚠️ 섹션 실패: {section_id} (시도 {attempt_count}회)")
    
    async def reset_section_for_retry(self, report_id: str, section_id: str) -> None:
        """섹션 재시도를 위해 리셋"""
        client = self._get_client()
        
        client.table("report_sections").update({
            "status": "pending",
            "error": None,
        }).eq("report_id", report_id).eq("section_id", section_id).execute()
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🔥 Job Recovery용 메서드
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def get_reports_by_status(self, status: str) -> list:
        """특정 상태의 리포트 목록 조회 (복구용)"""
        try:
            client = self._get_client()
            result = (
                client.table("reports")
                .select("id, email, status, created_at, updated_at")
                .eq("status", status)
                .order("created_at", desc=True)
                .limit(50)  # 최대 50개만
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"[SupabaseStore] get_reports_by_status 실패: {e}")
            return []


# 싱글톤 인스턴스
supabase_store = SupabaseStore()
