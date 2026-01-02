"""
report_worker.py
Background worker that generates premium report sections.

P0 fixes included:
- _ensure_dict(): Supabase JSON fields can arrive as strings
- daeun_direction reference bug fixed (read from saju_data)
- LLM quality guardrails + retry
- Forbidden rulecard physical filtering
- Output normalization for known typos (걸록->건록 etc)
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from app.services.report_builder import PREMIUM_SECTIONS, premium_report_builder
from app.services.rulecard_scorer import RuleCardScorer
from app.services.supabase_service import SupabaseService
from app.services.truth_anchor import forbidden_words_for_rulecards

try:
    from app.services.saju_analyzer import get_saju_summary  # optional but recommended
except Exception:  # pragma: no cover
    get_saju_summary = None  # type: ignore


# -----------------------------
# Helpers
# -----------------------------

def _ensure_dict(v: Any) -> Dict[str, Any]:
    """Supabase/프론트에서 JSON이 문자열로 올 때 dict로 안전 변환"""
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            vv = json.loads(v)
            return vv if isinstance(vv, dict) else {}
        except Exception:
            return {}
    return {}

def _ensure_list(v: Any) -> List[Any]:
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            vv = json.loads(v)
            return vv if isinstance(vv, list) else []
        except Exception:
            return []
    return []

_NORMALIZE_REPLACEMENTS = {
    "걸록격": "건록격",
    "걸록": "건록",
}

def _normalize_text(s: str) -> str:
    out = s or ""
    for a, b in _NORMALIZE_REPLACEMENTS.items():
        out = out.replace(a, b)
    return out


# -----------------------------
# Worker
# -----------------------------

class ReportWorker:
    def __init__(self):
        self.supabase = SupabaseService()
        self.scorer = RuleCardScorer()

    async def process(self, job_id: str) -> Tuple[bool, str]:
        started = time.time()
        try:
            ok, msg = await self._execute_job(job_id)
            return ok, msg
        finally:
            _ = time.time() - started

    # -----------------------------------------------------------------
    # Backward-compat alias
    # reports.py / 기존 코드가 run_job(...)을 호출하는 경우가 있어 alias를 유지합니다.
    # -----------------------------------------------------------------
    async def run_job(self, job_id: str, rulestore: Any = None) -> Tuple[bool, str]:
        """Backward compatible entrypoint (alias of process)."""
        # rulestore는 legacy signature 호환용(현재는 내부에서 self.scorer를 사용)
        return await self.process(job_id)

    async def _execute_job(self, job_id: str, rulestore: Any = None) -> Tuple[bool, str]:
        job = await self.supabase.get_job(job_id)
        if not job:
            return False, f"job not found: {job_id}"

        # P0: Supabase JSON columns can be string
        input_json = _ensure_dict(job.get("input_json") or job.get("input_data") or {})
        survey_data = _ensure_dict(input_json.get("survey_data") or input_json.get("survey") or {})

        # saju_data
        saju_data = self._prepare_saju_data(input_json)
        self._assert_required_saju(saju_data)

        # enrich saju_summary (P0)
        if get_saju_summary is not None and not saju_data.get("saju_summary"):
            try:
                saju_summary = get_saju_summary(saju_data)  # type: ignore
                saju_data["saju_summary"] = saju_summary
                saju_data["ten_gods_present"] = saju_summary.get("ten_gods_present", [])
                saju_data["has_wealth_star"] = saju_summary.get("has_wealth_star", False)
            except Exception as e:
                # don't fail job for summary; just log-friendly string
                print(f"[Worker] saju_summary 생성 실패: {e}")

        target_year = int(input_json.get("target_year") or survey_data.get("target_year") or time.gmtime().tm_year)

        # sections to generate (use PREMIUM_SECTIONS order)
        section_ids = list(PREMIUM_SECTIONS.keys())

        all_used_card_ids: List[str] = []
        existing_contents: List[str] = []
        failed_sections: List[Dict[str, Any]] = []

        # all cards from rulestore or scorer store
        all_cards = rulestore.cards if rulestore and hasattr(rulestore, "cards") else None
        if all_cards is None:
            all_cards = await self.scorer.get_all_cards()  # type: ignore

        used_ids: set = set()

        for idx, section_id in enumerate(section_ids, start=1):
            spec = PREMIUM_SECTIONS.get(section_id)
            min_chars = spec.min_chars if spec else 800

            # Select rulecards for section (with physical filtering)
            rulecards = self._select_rulecards_for_section(
                all_cards=all_cards,
                section_id=section_id,
                survey_data=survey_data,
                saju_data=saju_data,
                used_ids=used_ids,
                k=100,
            )
            for c in rulecards:
                cid = c.get("id")
                if cid:
                    used_ids.add(cid)

            MAX_RETRIES = 2
            last_result: Optional[Dict[str, Any]] = None
            guardrail_errors: List[str] = []
            quality_warning = False

            for attempt in range(MAX_RETRIES):
                result = await premium_report_builder.regenerate_single_section(
                    section_id,
                    saju_data,
                    rulecards,
                    survey_data,
                    target_year,
                    user_question=input_json.get("user_question") or "",
                    existing_contents=existing_contents[-3:],
                    job_id=job_id,
                )
                body = _normalize_text(result.get("body_markdown", ""))

                issues = self._check_llm_quality(body, target_year, saju_data, min_chars=min_chars)
                if issues:
                    guardrail_errors = issues
                    if attempt < MAX_RETRIES - 1:
                        print(f"[Worker] 섹션 {section_id} 품질 이슈: {issues} -> 재시도")
                        continue
                    # last attempt: store but mark warning
                    quality_warning = True

                result["body_markdown"] = body
                result["guardrail_violations"] = issues
                last_result = result
                break

            if not last_result:
                failed_sections.append({"section_id": section_id, "error": "LLM_GENERATION_FAILED"})
                continue

            # save section
            await self.supabase.save_section(job_id, last_result)
            existing_contents.append(last_result.get("body_markdown", "")[:1200])

            # collect ids
            all_used_card_ids.extend(last_result.get("used_rulecard_ids", []) or [])

            if quality_warning:
                print(f"[Worker] 섹션 {section_id} 품질 경고: {guardrail_errors}")

            # progress update
            await self.supabase.update_progress(job_id, idx, len(section_ids))

        # finalize job
        if failed_sections:
            await self.supabase.fail_job(job_id, f"FAILED_SECTIONS: {failed_sections}")
            return False, f"failed sections: {[x['section_id'] for x in failed_sections]}"

        # saju_json creation (P0: daeun_direction bug fix)
        saju_json = {
            "year_pillar": saju_data.get("year_pillar", ""),
            "month_pillar": saju_data.get("month_pillar", ""),
            "day_pillar": saju_data.get("day_pillar", ""),
            "hour_pillar": saju_data.get("hour_pillar", ""),
            "day_master": saju_data.get("day_master", ""),
            "day_master_element": saju_data.get("day_master_element", ""),
            "daeun_direction": saju_data.get("daeun_direction"),
            "current_daeun": saju_data.get("current_daeun"),
            "feature_tags": input_json.get("feature_tags") or [],
            "rulecards_used": all_used_card_ids[:20],
            "survey_data": survey_data,
            "calculated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        await self.supabase.complete_job(job_id, saju_json=saju_json)
        return True, "ok"

    # -------------------------
    # Saju handling
    # -------------------------

    def _prepare_saju_data(self, input_json: Dict[str, Any]) -> Dict[str, Any]:
        # saju_result can be nested JSON string
        saju_result = _ensure_dict(input_json.get("saju_result") or input_json.get("saju") or {})
        # sometimes pillars are at top-level
        saju_data = {
            "year_pillar": saju_result.get("year_pillar") or input_json.get("year_pillar"),
            "month_pillar": saju_result.get("month_pillar") or input_json.get("month_pillar"),
            "day_pillar": saju_result.get("day_pillar") or input_json.get("day_pillar"),
            "hour_pillar": saju_result.get("hour_pillar") or input_json.get("hour_pillar"),
            "day_master": saju_result.get("day_master") or input_json.get("day_master"),
            "day_master_element": saju_result.get("day_master_element") or input_json.get("day_master_element"),
            "daeun_direction": saju_result.get("daeun_direction") or input_json.get("daeun_direction"),
            "current_daeun": saju_result.get("current_daeun") or input_json.get("current_daeun"),
            "primary_structure": saju_result.get("primary_structure") or input_json.get("primary_structure"),
            "month_tengod": saju_result.get("month_tengod") or input_json.get("month_tengod"),
            "saju_summary": saju_result.get("saju_summary") or input_json.get("saju_summary"),
        }
        # include summary passthrough fields
        saju_data["ten_gods_present"] = saju_result.get("ten_gods_present") or input_json.get("ten_gods_present") or []
        saju_data["has_wealth_star"] = saju_result.get("has_wealth_star") or input_json.get("has_wealth_star") or False
        return saju_data

    def _assert_required_saju(self, saju_data: Dict[str, Any]) -> None:
        missing = [k for k in ("year_pillar", "month_pillar", "day_pillar") if not saju_data.get(k)]
        if missing:
            raise ValueError(f"사주 데이터 누락: {missing}.")

    # -------------------------
    # RuleCard selection + filtering
    # -------------------------

    def _select_rulecards_for_section(
        self,
        *,
        all_cards: List[Dict[str, Any]],
        section_id: str,
        survey_data: Dict[str, Any],
        saju_data: Dict[str, Any],
        used_ids: set,
        k: int = 100,
    ) -> List[Dict[str, Any]]:
        # P0: physical filter to remove hallucination-prone cards
        forbidden = forbidden_words_for_rulecards()

        filtered: List[Dict[str, Any]] = []
        for c in all_cards:
            cid = c.get("id")
            if cid and cid in used_ids:
                continue
            blob = f"{c.get('trigger_json','')} {c.get('mechanism','')} {c.get('interpretation','')} {c.get('action','')} {c.get('tags_json','')} {c.get('cautions_json','')}"
            if any(w in blob for w in forbidden):
                continue
            filtered.append(c)

        # score
        scored = self.scorer.score_cards_for_section(filtered, section_id, survey_data, saju_data, k=k)
        return scored

    # -------------------------
    # LLM quality guardrail
    # -------------------------

    def _check_llm_quality(
        self,
        body_markdown: str,
        target_year: int,
        saju_data: Dict[str, Any],
        *,
        min_chars: int = 800,
    ) -> List[str]:
        issues: List[str] = []
        s = body_markdown or ""

        # meta refusal
        refusal_patterns = ["죄송하지만", "분석할 수 없", "추가 정보가 필요", "제공해 주시면", "cannot", "I can't"]
        for p in refusal_patterns:
            if p in s:
                issues.append(f"거절문구:{p}")
                break

        # year sanity: don't drift heavily to previous year
        if str(target_year) in s:
            pass
        else:
            # allow missing but if mentions target_year-1 a lot, flag
            prev = str(target_year - 1)
            if prev in s and s.count(prev) >= 3:
                issues.append(f"연도오류:{prev} 언급과다")

        # length
        if len(s) < int(min_chars):
            issues.append(f"길이부족:{len(s)}<{min_chars}")

        # hallucinated ten-gods check (simple keyword scan)
        summary = saju_data.get("saju_summary") or {}
        present = set(summary.get("ten_gods_present") or [])
        if present:
            all_tengods = ["비견","겁재","식신","상관","정재","편재","정관","편관","정인","편인"]
            mentioned = {tg for tg in all_tengods if tg in s}
            halluc = sorted(list(mentioned - present))
            if halluc:
                issues.append(f"환각십성:{halluc}")

        return issues


report_worker = ReportWorker()

__all__ = ["ReportWorker", "report_worker"]
