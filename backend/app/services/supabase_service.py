"""
Supabase Service v14 - P0 Fix: content/markdown/body_markdown 컬럼 반드시 저장
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
P0 핵심:
1) save_section()에서 content, markdown, body_markdown 모두 저장
2) sanitize_report_content()로 RC-xxxx, 근거: 제거
3) char_count, confidence, error도 저장
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import os
import re
import secrets
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 P0: sanitize 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def sanitize_report_content(text: str) -> str:
    """
    🔥 P0: 리포트 본문에서 내부 토큰 제거
    - RC-xxxx 토큰 제거
    - "### 근거:" 류 제거
    - 과한 줄바꿈 정리
    """
    if not text:
        return ""
    text = re.sub(r"\[?RC-[A-Za-z0-9_-]+\]?", "", text)   # RC 토큰 제거
    text = re.sub(r"#+\s*근거:.*", "", text)              # "### 근거:" 류 제거
    text = re.sub(r"\n{3,}", "\n\n", text)                # 과한 줄바꿈 정리
    return text.strip()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 섹션 정의
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 🔥 P0: 1인 자영업자용 섹션 스펙
SECTION_SPECS = [
    {"id": "exec", "title": "2026년, 내 장사 설계도", "order": 1},
    {"id": "money", "title": "현금흐름 & 수익구조", "order": 2},
    {"id": "business", "title": "사업 전략 & 확장 타이밍", "order": 3},
    {"id": "team", "title": "협력자 & 파트너 리스크", "order": 4},
    {"id": "health", "title": "체력 & 번아웃 관리", "order": 5},
    {"id": "calendar", "title": "12개월 캘린더", "order": 6},
    {"id": "sprint", "title": "90일 스프린트 플랜", "order": 7},
]

SECTION_ORDER = ["exec", "money", "business", "team", "health", "calendar", "sprint"]


class SupabaseService:
    _client = None
    
    def _get_client(self):
        if self._client is None:
            from supabase import create_client
            url = os.getenv("SUPABASE_URL", "")
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
            if not url or not key:
                raise RuntimeError("SUPABASE_URL/KEY 없음")
            self._client = create_client(url, key)
            logger.info("✅ Supabase 연결")
        return self._client
    
    def is_available(self) -> bool:
        return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    
    async def create_job(self, email: str, name: str = "", input_data: Dict = None, target_year: int = 2026) -> Dict:
        """Job 생성"""
        client = self._get_client()
        public_token = secrets.token_hex(16)
        
        data = {
            "user_email": email,
            "input_json": input_data or {},
            "status": "queued",
            "progress": 0,
            "current_step": "queued",
            "public_token": public_token
        }
        
        result = client.table("report_jobs").insert(data).execute()
        
        if not result.data:
            raise RuntimeError("Job 생성 실패")
        
        job = result.data[0]
        logger.info(f"[Supabase] Job 생성: {job['id']} | token={public_token[:8]}...")
        return job
    
    async def get_job(self, job_id: str) -> Optional[Dict]:
        """Job 조회"""
        client = self._get_client()
        result = client.table("report_jobs").select("*").eq("id", job_id).execute()
        return result.data[0] if result.data else None
    
    async def get_job_by_token(self, token: str) -> Optional[Dict]:
        """토큰으로 Job 조회"""
        client = self._get_client()
        result = client.table("report_jobs").select("*").eq("public_token", token).execute()
        return result.data[0] if result.data else None
    
    async def verify_job_token(self, job_id: str, token: str) -> tuple[bool, Optional[Dict]]:
        """Job ID + Token 검증"""
        if not token:
            return False, None
        
        client = self._get_client()
        result = client.table("report_jobs").select("*").eq("id", job_id).eq("public_token", token).execute()
        
        if not result.data:
            logger.warning(f"[Supabase] 토큰 검증 실패: job={job_id}")
            return False, None
        
        return True, result.data[0]
    
    async def update_progress(self, job_id: str, progress: int, status: str = "running"):
        """진행률 업데이트"""
        client = self._get_client()
        client.table("report_jobs").update({
            "status": status,
            "progress": progress,
            "current_step": status
        }).eq("id", job_id).execute()
    
    async def complete_job(self, job_id: str, result_json: Dict = None, markdown: str = "", saju_json: Dict = None):
        """
        Job 완료
        
        Args:
            job_id: Job ID
            result_json: 전체 결과 (섹션 + 메타)
            markdown: 전체 마크다운
            saju_json: 🔥 사주 계산 결과 (년/월/일/시주 등)
        """
        client = self._get_client()
        data = {
            "status": "completed",
            "progress": 100,
            "current_step": "completed",
            "completed_at": datetime.utcnow().isoformat(),
        }
        if result_json:
            data["result_json"] = result_json
        if markdown:
            data["markdown"] = sanitize_report_content(markdown)
            logger.info(f"[Supabase] Job markdown 저장: {len(markdown)}자")
        
        # 🔥 P0: saju_json 저장 (계산 결과)
        if saju_json:
            data["saju_json"] = saju_json
            logger.info(f"[Supabase] 🎯 saju_json 저장: {saju_json.get('year_pillar', 'N/A')}/{saju_json.get('month_pillar', 'N/A')}/{saju_json.get('day_pillar', 'N/A')}/{saju_json.get('hour_pillar', 'N/A')}")
        else:
            logger.warning(f"[Supabase] ⚠️ saju_json이 NULL입니다!")
        
        client.table("report_jobs").update(data).eq("id", job_id).execute()
        logger.info(f"[Supabase] ✅ Job 완료: {job_id}")
    
    async def fail_job(self, job_id: str, error: str):
        """Job 실패"""
        client = self._get_client()
        client.table("report_jobs").update({
            "status": "failed",
            "current_step": "failed",
            "error": error[:500]
        }).eq("id", job_id).execute()
        logger.error(f"[Supabase] ❌ Job 실패: {job_id}")
    
    async def save_section(self, job_id: str, section_id: str, content_json: Dict = None):
        """
        🔥🔥🔥 P0 핵심: 섹션 저장 (content 필수 저장)
        - body_markdown, markdown, content 3개 컬럼 모두 저장
        - sanitize_report_content()로 RC-xxxx, 근거: 제거
        - char_count, confidence, error, title, section_order도 저장
        - raw_json은 원본 그대로 보존 (근거 추적용)
        """
        client = self._get_client()

        existing = client.table("report_sections").select("id").eq(
            "job_id", job_id).eq("section_id", section_id).execute()

        data = {
            "job_id": job_id,
            "section_id": section_id,
            "status": "completed",
            "progress": 100,
        }

        if content_json:
            # 🔥 P0: raw_json은 원본 그대로 저장 (근거 추적용)
            data["raw_json"] = content_json

            # 🔥 P0: body_markdown/markdown/content 중 하나 추출
            md = (
                content_json.get("body_markdown")
                or content_json.get("markdown")
                or content_json.get("content")
                or ""
            )
            
            # 🔥 P0: sanitize 적용 (사용자용)
            md_sanitized = sanitize_report_content(md)

            # 🔥 P0 핵심: 3개 컬럼 모두 저장
            data["body_markdown"] = md_sanitized
            data["markdown"] = md_sanitized
            data["content"] = md_sanitized
            data["char_count"] = len(md_sanitized)
            
            # title 저장
            if content_json.get("title"):
                data["title"] = content_json["title"]

            # confidence 저장
            if content_json.get("confidence"):
                data["confidence"] = str(content_json["confidence"])

            # error 저장
            if content_json.get("guardrail_errors"):
                data["error"] = "guardrail_block"
            if content_json.get("error"):
                data["error"] = str(content_json["error"])[:500]
            
            # section_order 저장
            if section_id in SECTION_ORDER:
                data["section_order"] = SECTION_ORDER.index(section_id) + 1
            
            # 🔥 검증: 저장할 내용이 비어있으면 경고
            if len(md_sanitized) < 100:
                logger.warning(f"[Supabase] ⚠️⚠️⚠️ 섹션 내용이 너무 짧음: {section_id} | {len(md_sanitized)}자")
                logger.warning(f"[Supabase] content_json keys: {list(content_json.keys())}")
                logger.warning(f"[Supabase] body_markdown length: {len(content_json.get('body_markdown', ''))}")
            else:
                logger.info(f"[Supabase] ✅ 섹션 저장 준비: {section_id} | char_count={len(md_sanitized)}")

        if existing.data:
            client.table("report_sections").update(data).eq(
                "job_id", job_id).eq("section_id", section_id).execute()
            logger.info(f"[Supabase] ✅ 섹션 UPDATE: {section_id} | {data.get('char_count', 0)}자")
        else:
            client.table("report_sections").insert(data).execute()
            logger.info(f"[Supabase] ✅ 섹션 INSERT: {section_id} | {data.get('char_count', 0)}자")
    
    async def get_sections(self, job_id: str) -> List[Dict]:
        """섹션 조회"""
        client = self._get_client()
        result = client.table("report_sections").select("*").eq("job_id", job_id).execute()
        return result.data or []
    
    async def get_sections_ordered(self, job_id: str) -> List[Dict]:
        """섹션 조회 (SECTION_ORDER 순 정렬)"""
        sections = await self.get_sections(job_id)
        
        def sort_key(s):
            sid = s.get("section_id", "")
            if sid in SECTION_ORDER:
                return SECTION_ORDER.index(sid)
            return 999
        
        return sorted(sections, key=sort_key)
    
    async def get_job_with_sections(self, job_id: str) -> Optional[Dict]:
        """Job + 섹션"""
        job = await self.get_job(job_id)
        if job:
            job["sections"] = await self.get_sections_ordered(job_id)
        return job
    
    async def init_sections(self, job_id: str, specs: List[Dict]):
        """섹션 초기화"""
        client = self._get_client()
        for spec in specs:
            try:
                existing = client.table("report_sections").select("id").eq(
                    "job_id", job_id).eq("section_id", spec["id"]).execute()
                if not existing.data:
                    client.table("report_sections").insert({
                        "job_id": job_id,
                        "section_id": spec["id"],
                        "status": "pending",
                        "progress": 0
                    }).execute()
            except Exception as e:
                logger.warning(f"섹션 초기화 스킵: {spec['id']} | {e}")
    
    async def update_section_status(self, job_id: str, section_id: str, status: str, error: str = None):
        """섹션 상태 업데이트"""
        client = self._get_client()
        data = {"status": status}
        if error:
            data["error"] = error[:500]
        client.table("report_sections").update(data).eq(
            "job_id", job_id).eq("section_id", section_id).execute()
    
    async def get_jobs_by_status(self, status: str, limit: int = 50) -> List[Dict]:
        """상태별 Job 조회"""
        try:
            client = self._get_client()
            result = client.table("report_jobs").select("*").eq(
                "status", status).order("created_at", desc=True).limit(limit).execute()
            return result.data or []
        except:
            return []
    
    async def fix_null_tokens(self) -> int:
        """기존 NULL 토큰 수정"""
        client = self._get_client()
        result = client.table("report_jobs").select("id").is_("public_token", "null").execute()
        
        fixed = 0
        for job in (result.data or []):
            new_token = secrets.token_hex(16)
            client.table("report_jobs").update({
                "public_token": new_token
            }).eq("id", job["id"]).execute()
            fixed += 1
        
        return fixed


supabase_service = SupabaseService()
