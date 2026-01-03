"""
ReportWorker - generates premium report sections and persists them to Supabase.

Key goals:
- Be tolerant to different shapes of job.input_json (dict or JSON string, nested keys).
- Be tolerant to SupabaseService method-name differences (get_job vs get_report_job, etc.).
- Hard-block "forbidden word" rulecards before scoring/selection.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from app.services.report_builder import premium_report_builder
from app.services.rulecard_scorer import rulecard_scorer
from app.services.supabase_service import SupabaseService
from app.templates.master_samples import MasterSamples
from app.services.truth_anchor import forbidden_words_for_rulecards


logger = logging.getLogger(__name__)


def _maybe_json_loads(x: Any) -> Any:
    if isinstance(x, str):
        s = x.strip()
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            try:
                return json.loads(s)
            except Exception:
                return x
    return x


def _normalize_saju_data(raw: Any) -> Dict[str, Any]:
    """
    Accepts many shapes:
    - dict with year_pillar/month_pillar/day_pillar
    - dict with pillars: {year, month, day}
    - dict with saju_result / saju / result nested
    - JSON string of any of the above
    Returns a dict (possibly empty).
    """
    raw = _maybe_json_loads(raw)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        return {}

    # Unwrap common nesting
    for key in ("saju_result", "saju", "result", "data"):
        if isinstance(raw.get(key), (dict, str)):
            candidate = _maybe_json_loads(raw.get(key))
            if isinstance(candidate, dict) and ("year_pillar" in candidate or "pillars" in candidate):
                raw = candidate
                break

    # If pillars nested
    if "pillars" in raw and isinstance(raw["pillars"], dict):
        p = raw["pillars"]
        raw.setdefault("year_pillar", p.get("year") or p.get("year_pillar"))
        raw.setdefault("month_pillar", p.get("month") or p.get("month_pillar"))
        raw.setdefault("day_pillar", p.get("day") or p.get("day_pillar"))

    return raw


def _normalize_survey_data(raw: Any) -> Dict[str, Any]:
    raw = _maybe_json_loads(raw)
    if isinstance(raw, dict):
        return raw
    return {}


def _extract_job_payload(job: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], int, str, List[str]]:
    """
    Returns (saju_data, survey_data, target_year, user_question, feature_tags)
    """
    input_json = _maybe_json_loads(job.get("input_json")) or {}
    input_json = input_json if isinstance(input_json, dict) else {}

    # candidates
    saju_raw = (
        input_json.get("saju_data")
        or input_json.get("saju_result")
        or input_json.get("calculate_result")
        or input_json.get("saju")
        or job.get("saju_data")
        or job.get("saju_result")
    )
    survey_raw = input_json.get("survey_data") or input_json.get("survey") or job.get("survey_data")

    saju_data = _normalize_saju_data(saju_raw)
    survey_data = _normalize_survey_data(survey_raw)

    target_year = int(input_json.get("target_year") or job.get("target_year") or 2026)
    user_question = str(input_json.get("user_question") or survey_data.get("painPoint") or "").strip()

    feature_tags = input_json.get("feature_tags") or input_json.get("tags") or []
    feature_tags = feature_tags if isinstance(feature_tags, list) else []

    return saju_data, survey_data, target_year, user_question, feature_tags


def _filter_forbidden_cards(cards: List[Dict[str, Any]], forbidden_words: List[str]) -> List[Dict[str, Any]]:
    if not forbidden_words:
        return cards
    out: List[Dict[str, Any]] = []
    for c in cards:
        blob = f"{c.get('topic','')} {c.get('interpretation','')} {c.get('action','')}"
        if any(w in blob for w in forbidden_words):
            continue
        out.append(c)
    return out


class ReportWorker:
    """
    Router에서 호출하는 엔트리포인트는 반드시 `run_job(job_id, rulestore)` 이다.
    """

    def __init__(self, supabase: Optional[SupabaseService] = None):
        self.supabase = supabase or SupabaseService()

    async def _call_supabase(self, candidates: List[str], *args, **kwargs):
        """
        Tries supabase method names in order. Supports sync/async methods.
        """
        for name in candidates:
            fn = getattr(self.supabase, name, None)
            if not fn:
                continue
            try:
                res = fn(*args, **kwargs)
                if asyncio.iscoroutine(res):
                    return await res
                return res
            except AttributeError:
                continue
        raise AttributeError(f"SupabaseService has none of {candidates}")

    async def run_job(self, job_id: str, rulestore) -> None:
        logger.info(f"[Worker] 🚀 Job 시작: {job_id}")
        try:
            await self._execute_job(job_id=job_id, rulestore=rulestore)
            logger.info(f"[Worker] ✅ Job 완료: {job_id}")
        except Exception:
            logger.exception(f"[Worker] run_job 실패: {job_id}")
            # best-effort fail mark
            try:
                await self._call_supabase(["fail_job", "mark_job_failed"], job_id, "worker_error")
            except Exception:
                pass
            raise

    async def _execute_job(self, job_id: str, rulestore) -> None:
        # 1) job fetch (compat)
        job = await self._call_supabase(["get_job", "get_report_job"], job_id)
        if isinstance(job, list):
            job = job[0] if job else None
        if not isinstance(job, dict):
            raise RuntimeError(f"Job not found: {job_id}")

        saju_data, survey_data, target_year, user_question, feature_tags = _extract_job_payload(job)

        # 최소 필수 키 체크 (없으면 에러 메시지 명확히)
        missing = [k for k in ("year_pillar", "month_pillar", "day_pillar") if not saju_data.get(k)]
        if missing:
            raise ValueError(f"사주 데이터 누락: {missing}.")

        # 2) load sections
        sections = await self._call_supabase(["list_sections", "get_sections", "get_report_sections"], job_id)
        if not isinstance(sections, list):
            raise RuntimeError("Failed to load sections list")

        # 섹션 순서 고정 (없으면 DB 결과 순서 사용)
        desired_order = ["exec", "money", "business", "team", "health", "calendar", "sprint"]
        sections_sorted = sorted(
            sections,
            key=lambda s: desired_order.index(s.get("section_id")) if s.get("section_id") in desired_order else 999
        )

        used_ids: set = set()

        forbidden_words = forbidden_words_for_rulecards(saju_data)

        for sec in sections_sorted:
            section_row_id = sec.get("id")
            section_id = sec.get("section_id")
            if not section_row_id or not section_id:
                continue

            # 3) select rulecards
            all_cards = rulestore.get_all_cards() if hasattr(rulestore, "get_all_cards") else []
            all_cards = all_cards if isinstance(all_cards, list) else []
            all_cards = _filter_forbidden_cards(all_cards, forbidden_words)

            picked = rulecard_scorer.score_cards_for_section(
                all_cards=all_cards,
                section_id=section_id,
                feature_tags=feature_tags,
                survey_data=survey_data,
                saju_data=saju_data,
                used_ids=used_ids,
                top_k=8,
            )
            picked = picked if isinstance(picked, list) else []
            for c in picked:
                cid = c.get("id")
                if cid:
                    used_ids.add(cid)

            # 4) generate section with builder
            body_markdown, quality_warning = await premium_report_builder.regenerate_single_section(
                section_id=section_id,
                saju_data=saju_data,
                rulecards=picked,
                feature_tags=feature_tags,
                target_year=target_year,
                user_question=user_question,
                survey_data=survey_data,
            )

            # 5) persist section
            await self._call_supabase(
                ["save_section", "update_section", "update_report_section"],
                section_row_id,
                body_markdown,
                quality_warning,
            )

        # 6) complete
        await self._call_supabase(["complete_job", "mark_job_done", "finish_job"], job_id)
