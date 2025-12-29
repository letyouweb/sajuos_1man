"""
Report Worker v12 - P0 Critical Fix: 사주 데이터 파이프라인 정상화
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 P0 핵심 수정:
1) _prepare_saju_data()에서 saju_result.year_pillar.ganji 추출
2) 생년월일/시간 정보도 함께 전달
3) 사주 4주가 비어있으면 ERROR 로그 + 프론트 표시
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List

from app.services.supabase_service import supabase_service, SECTION_SPECS

logger = logging.getLogger(__name__)


class ReportWorker:
    """백그라운드 리포트 생성 워커"""
    
    _running_jobs: set = set()
    
    async def run_job(self, job_id: str, rulestore: Any = None) -> None:
        """Job 실행"""
        if job_id in self._running_jobs:
            logger.warning(f"[Worker] 이미 실행 중: {job_id}")
            return
        
        self._running_jobs.add(job_id)
        start_time = time.time()
        
        if rulestore:
            card_count = len(getattr(rulestore, 'cards', [])) if hasattr(rulestore, 'cards') else 0
            logger.info(f"[Worker] RuleStore 수신: total={card_count}장")
        else:
            logger.warning(f"[Worker] ⚠️ RuleStore가 None!")
        
        try:
            success, error_msg = await self._execute_job(job_id, rulestore)
            elapsed = int((time.time() - start_time) * 1000)
            
            if success:
                logger.info(f"[Worker] ✅ Job 완료: {job_id} ({elapsed}ms)")
            else:
                logger.error(f"[Worker] ❌ Job 실패: {job_id} | {error_msg}")
            
        except Exception as e:
            logger.error(f"[Worker] ❌ Job 실패: {job_id} | {e}")
            try:
                await supabase_service.fail_job(job_id, str(e)[:500])
            except:
                pass
            
            try:
                job = await supabase_service.get_job(job_id)
                if job:
                    await self._send_failure_email(job, str(e))
            except Exception as email_err:
                logger.warning(f"[Worker] 실패 이메일 발송 실패: {email_err}")
        
        finally:
            self._running_jobs.discard(job_id)
    
    async def _execute_job(self, job_id: str, rulestore: Any = None) -> tuple[bool, str]:
        """실제 Job 실행"""
        job = await supabase_service.get_job(job_id)
        if not job:
            raise ValueError(f"Job 없음: {job_id}")
        
        email = job.get("user_email", "")
        input_json = job.get("input_json") or {}
        
        name = input_json.get("name", "고객")
        target_year = input_json.get("target_year", 2026)
        question = input_json.get("question", "")
        survey_data = input_json.get("survey_data")
        
        await supabase_service.update_progress(job_id, 5, "running")
        
        # 🔥🔥🔥 P0 핵심: 사주 데이터 추출 및 검증
        saju_data = self._prepare_saju_data(input_json)
        
        # 🔥 사주 4주 검증 - 비어있으면 경고
        missing_pillars = []
        for key in ["year_pillar", "month_pillar", "day_pillar"]:
            if not saju_data.get(key):
                missing_pillars.append(key)
        
        if missing_pillars:
            logger.error(f"[Worker] ⚠️⚠️⚠️ 사주 데이터 누락: {missing_pillars}")
            logger.error(f"[Worker] input_json keys: {list(input_json.keys())}")
            logger.error(f"[Worker] saju_result keys: {list(input_json.get('saju_result', {}).keys())}")
        else:
            logger.info(f"[Worker] ✅ 사주 데이터 확인: {saju_data['year_pillar']}/{saju_data['month_pillar']}/{saju_data['day_pillar']}/{saju_data.get('hour_pillar', '-')}")
        
        feature_tags = self._build_feature_tags(saju_data)
        rulecards = self._select_rulecards(rulestore, feature_tags)
        
        logger.info(f"[Worker] RuleCards 선택: {len(rulecards)}장 | FeatureTags: {len(feature_tags)}개")
        
        sections_result = {}
        failed_sections = []
        total_sections = len(SECTION_SPECS)
        
        for idx, spec in enumerate(SECTION_SPECS):
            section_id = spec["id"]
            
            progress = int((idx / total_sections) * 90) + 10
            await supabase_service.update_progress(job_id, progress, "running")
            
            try:
                section_result = await self._generate_section(
                    section_id=section_id,
                    saju_data=saju_data,
                    rulecards=rulecards,
                    feature_tags=feature_tags,
                    target_year=target_year,
                    question=question,
                    survey_data=survey_data
                )
                
                content = section_result.get("content", {})
                ok = section_result.get("ok", True)
                errors = section_result.get("guardrail_errors", [])
                
                # 🔥 P0 핵심: save_section에 content 전달 (body_markdown 포함)
                # 저장 전 검증
                body_markdown = content.get("body_markdown", "")
                if not body_markdown or len(body_markdown) < 100:
                    logger.error(f"[Worker] ⚠️⚠️⚠️ 섹션 본문이 너무 짧거나 비어있음: {section_id} | length={len(body_markdown)}")
                    logger.error(f"[Worker] content keys: {list(content.keys())}")
                    # 그래도 저장은 진행 (추적용)
                
                await supabase_service.save_section(
                    job_id=job_id,
                    section_id=section_id,
                    content_json=content
                )
                
                sections_result[section_id] = content
                
                logger.info(f"[Worker] 섹션 완료: {section_id} | body_markdown={len(body_markdown)}자 | ok={ok}")
                
                if not ok:
                    failed_sections.append({"section_id": section_id, "errors": errors})
                
            except Exception as e:
                logger.error(f"[Worker] 섹션 실패: {section_id} | {e}")
                failed_sections.append({
                    "section_id": section_id,
                    "errors": [f"Exception: {str(e)[:100]}"]
                })
        
        result_json = {
            "name": name,
            "target_year": target_year,
            "saju_summary": {
                "year_pillar": saju_data.get("year_pillar", ""),
                "month_pillar": saju_data.get("month_pillar", ""),
                "day_pillar": saju_data.get("day_pillar", ""),
                "hour_pillar": saju_data.get("hour_pillar", ""),
                "day_master": saju_data.get("day_master", ""),
                "birth_info": saju_data.get("birth_info", ""),
            },
            "sections": sections_result,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "failed_sections": failed_sections if failed_sections else None
        }
        
        # 🔥 P0: saju_json 생성 (DB 저장용)
        saju_json = {
            "year_pillar": saju_data.get("year_pillar", ""),
            "month_pillar": saju_data.get("month_pillar", ""),
            "day_pillar": saju_data.get("day_pillar", ""),
            "hour_pillar": saju_data.get("hour_pillar", ""),
            "day_master": saju_data.get("day_master", ""),
            "day_master_element": saju_data.get("day_master_element", ""),
            "day_master_description": saju_data.get("day_master_description", ""),
            "birth_info": saju_data.get("birth_info", ""),
            "feature_tags": feature_tags,
            "rulecards_used": [card.get("id") for card in rulecards[:10]],  # 🔥 사용한 룰카드 ID
            "calculated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        markdown = self._build_markdown(result_json, saju_data)
        
        # 🔥 P0: saju_json 전달
        await supabase_service.complete_job(job_id, result_json, markdown, saju_json)
        
        logger.info(f"[Worker] 🎯 사주 데이터 저장: {saju_json['year_pillar']}/{saju_json['month_pillar']}/{saju_json['day_pillar']}/{saju_json['hour_pillar']}")
        logger.info(f"[Worker] 🎯 사용한 룰카드: {len(saju_json['rulecards_used'])}개")
        
        try:
            await self._send_completion_email(email, name, job_id)
        except Exception as e:
            logger.warning(f"[Worker] 완료 이메일 실패: {e}")
        
        return True, ""
    
    async def _generate_section(
        self,
        section_id: str,
        saju_data: Dict,
        rulecards: List,
        feature_tags: List,
        target_year: int,
        question: str,
        survey_data: Dict = None
    ) -> Dict[str, Any]:
        """섹션 생성"""
        try:
            from app.services.report_builder import premium_report_builder
            
            logger.info(f"[Worker:Section:{section_id}] 생성 시작 | RuleCards={len(rulecards)}장")
            
            result = await premium_report_builder.regenerate_single_section(
                section_id=section_id,
                saju_data=saju_data,
                rulecards=rulecards,
                feature_tags=feature_tags,
                target_year=target_year,
                user_question=question,
                survey_data=survey_data
            )
            
            if not result.get("success"):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"[Worker:Section:{section_id}] 생성 실패: {error_msg}")
                return {
                    "ok": False,
                    "content": {"title": section_id, "body_markdown": "", "error": error_msg},
                    "guardrail_errors": [error_msg]
                }
            
            section_data = result.get("section", {})
            body_markdown = section_data.get("body_markdown", "")
            
            if body_markdown:
                logger.info(f"[Worker:Section:{section_id}] ✅ body_markdown={len(body_markdown)}자")
            else:
                logger.warning(f"[Worker:Section:{section_id}] ⚠️ body_markdown 비어있음!")
            
            content = {
                "title": section_data.get("title", section_id),
                "body_markdown": body_markdown,
                "confidence": section_data.get("confidence", "MEDIUM"),
                "diagnosis": section_data.get("diagnosis"),
                "hypotheses": section_data.get("hypotheses"),
                "strategy_options": section_data.get("strategy_options"),
                "recommended_strategy": section_data.get("recommended_strategy"),
                "kpis": section_data.get("kpis"),
                "risks": section_data.get("risks"),
                "annual_theme": section_data.get("annual_theme"),
                "monthly_plans": section_data.get("monthly_plans"),
                "quarterly_milestones": section_data.get("quarterly_milestones"),
                "peak_months": section_data.get("peak_months"),
                "risk_months": section_data.get("risk_months"),
                "mission_statement": section_data.get("mission_statement"),
                "phase_1_offer": section_data.get("phase_1_offer"),
                "phase_2_funnel": section_data.get("phase_2_funnel"),
                "phase_3_content": section_data.get("phase_3_content"),
                "phase_4_automation": section_data.get("phase_4_automation"),
                "milestones": section_data.get("milestones"),
                "risk_scenarios": section_data.get("risk_scenarios"),
            }
            
            return {
                "ok": bool(body_markdown),
                "content": content,
                "guardrail_errors": [] if body_markdown else ["EMPTY_BODY_MARKDOWN"]
            }
            
        except Exception as e:
            logger.error(f"[Worker:Section:{section_id}] 예외: {e}")
            return {
                "ok": False,
                "content": {"title": section_id, "body_markdown": "", "error": str(e)[:200]},
                "guardrail_errors": [f"Exception: {str(e)[:100]}"]
            }
    
    def _prepare_saju_data(self, input_json: Dict) -> Dict:
        """
        🔥🔥🔥 P0 핵심: 사주 데이터 정확히 추출
        
        지원하는 모든 구조:
        1. {"year_pillar": "갑진", ...}  # 문자열 직접
        2. {"year_pillar": {"ganji": "갑진", ...}, ...}  # Dict 구조
        3. {"saju_result": {"saju": {"year_pillar": {...}}}}  # 중첩 구조
        4. {"saju_result": {"year_pillar": {...}}}  # 프론트 구조
        """
        saju_result = input_json.get("saju_result") or {}
        
        # 🔥 핵심: pillar가 Dict이면 .ganji 추출, 문자열이면 그대로
        def extract_ganji(pillar_data):
            if not pillar_data:
                return ""
            if isinstance(pillar_data, dict):
                return pillar_data.get("ganji", "")
            if isinstance(pillar_data, str):
                return pillar_data
            return ""
        
        # 🔥 우선순위 1: saju_result 최상위에서 추출
        year_pillar = extract_ganji(saju_result.get("year_pillar"))
        month_pillar = extract_ganji(saju_result.get("month_pillar"))
        day_pillar = extract_ganji(saju_result.get("day_pillar"))
        hour_pillar = extract_ganji(saju_result.get("hour_pillar"))
        
        # 🔥 우선순위 2: saju_result.saju (중첩 구조)
        saju_nested = saju_result.get("saju") or {}
        if not year_pillar and saju_nested:
            year_pillar = extract_ganji(saju_nested.get("year_pillar"))
        if not month_pillar and saju_nested:
            month_pillar = extract_ganji(saju_nested.get("month_pillar"))
        if not day_pillar and saju_nested:
            day_pillar = extract_ganji(saju_nested.get("day_pillar"))
        if not hour_pillar and saju_nested:
            hour_pillar = extract_ganji(saju_nested.get("hour_pillar"))
        
        # 🔥 우선순위 3: input_json 최상위 (fallback)
        if not year_pillar:
            year_pillar = input_json.get("year_pillar", "")
        if not month_pillar:
            month_pillar = input_json.get("month_pillar", "")
        if not day_pillar:
            day_pillar = input_json.get("day_pillar", "")
        if not hour_pillar:
            hour_pillar = input_json.get("hour_pillar", "")
        
        # 🔥 day_master 추출
        day_master = saju_result.get("day_master", "")
        if not day_master and saju_nested:
            day_master = saju_nested.get("day_master", "")
        
        day_master_element = saju_result.get("day_master_element", "")
        day_master_description = saju_result.get("day_master_description", "")
        
        # 🔥 생년월일 정보 추출
        birth_info = saju_result.get("birth_info", "")
        
        # 🔥 검증: 필수 데이터 누락 시 명확한 로그
        missing = []
        if not year_pillar:
            missing.append("year_pillar")
        if not month_pillar:
            missing.append("month_pillar")
        if not day_pillar:
            missing.append("day_pillar")
        
        if missing:
            logger.error(f"[Worker] ❌❌❌ 사주 데이터 누락: {missing}")
            logger.error(f"[Worker] input_json keys: {list(input_json.keys())}")
            logger.error(f"[Worker] saju_result keys: {list(saju_result.keys())}")
            if saju_nested:
                logger.error(f"[Worker] saju_nested keys: {list(saju_nested.keys())}")
            
            # 원본 데이터 샘플 출력
            logger.error(f"[Worker] year_pillar raw: {saju_result.get('year_pillar')}")
            logger.error(f"[Worker] month_pillar raw: {saju_result.get('month_pillar')}")
            logger.error(f"[Worker] day_pillar raw: {saju_result.get('day_pillar')}")
        else:
            logger.info(f"[Worker] ✅ 사주 추출 결과: 년={year_pillar}, 월={month_pillar}, 일={day_pillar}, 시={hour_pillar or '미입력'}")
        
        return {
            "year_pillar": year_pillar,
            "month_pillar": month_pillar,
            "day_pillar": day_pillar,
            "hour_pillar": hour_pillar,
            "day_master": day_master,
            "day_master_element": day_master_element,
            "day_master_description": day_master_description,
            "birth_info": birth_info,
            # 🔥 원본 saju_result도 보존
            "saju_result": saju_result,
        }
    
    def _build_feature_tags(self, saju_data: Dict) -> List[str]:
        """Feature Tags 생성"""
        tags = []
        
        for pillar_key in ["year_pillar", "month_pillar", "day_pillar", "hour_pillar"]:
            pillar = saju_data.get(pillar_key, "")
            if pillar and len(pillar) >= 2:
                tags.append(f"천간:{pillar[0]}")
                tags.append(f"지지:{pillar[1]}")
        
        if saju_data.get("day_master"):
            tags.append(f"일간:{saju_data['day_master']}")
        
        logger.info(f"[Worker] Feature Tags: {tags}")
        return tags
    
    def _select_rulecards(self, rulestore: Any, feature_tags: List[str]) -> List:
        """RuleCards 선택"""
        if not rulestore:
            return []
        
        all_cards = getattr(rulestore, 'cards', [])
        
        if not all_cards:
            return []
        
        if not feature_tags:
            sorted_cards = sorted(all_cards, key=lambda c: getattr(c, 'priority', 0), reverse=True)
            selected = sorted_cards[:100]
            return [self._card_to_dict(c) for c in selected]
        
        matched = []
        feature_set = set(t.lower() for t in feature_tags)
        
        for card in all_cards:
            card_tags = getattr(card, 'tags', [])
            card_tags_lower = set(t.lower() for t in card_tags)
            
            if feature_set & card_tags_lower:
                matched.append(card)
        
        if matched:
            sorted_matched = sorted(matched, key=lambda c: getattr(c, 'priority', 0), reverse=True)
            selected = sorted_matched[:50]
            return [self._card_to_dict(c) for c in selected]
        
        sorted_cards = sorted(all_cards, key=lambda c: getattr(c, 'priority', 0), reverse=True)
        selected = sorted_cards[:50]
        return [self._card_to_dict(c) for c in selected]
    
    def _card_to_dict(self, card) -> Dict:
        """RuleCard를 dict로 변환"""
        return {
            "id": getattr(card, 'id', ''),
            "topic": getattr(card, 'topic', ''),
            "tags": getattr(card, 'tags', []),
            "priority": getattr(card, 'priority', 0),
            "trigger": getattr(card, 'trigger', ''),
            "mechanism": getattr(card, 'mechanism', ''),
            "interpretation": getattr(card, 'interpretation', ''),
            "action": getattr(card, 'action', ''),
            "cautions": getattr(card, 'cautions', []),
        }
    
    def _build_markdown(self, result_json: Dict, saju_data: Dict) -> str:
        """마크다운 생성"""
        lines = []
        
        name = result_json.get('name', '고객')
        target_year = result_json.get('target_year', 2026)
        
        lines.append(f"# {name}님의 {target_year}년 비즈니스 운세 리포트\n")
        
        # 🔥 사주 요약 추가
        lines.append("## 📜 사주 원국\n")
        lines.append(f"- 년주: {saju_data.get('year_pillar', '-')}")
        lines.append(f"- 월주: {saju_data.get('month_pillar', '-')}")
        lines.append(f"- 일주: {saju_data.get('day_pillar', '-')}")
        lines.append(f"- 시주: {saju_data.get('hour_pillar', '-') or '미입력'}")
        lines.append(f"- 일간: {saju_data.get('day_master', '-')} ({saju_data.get('day_master_element', '')})")
        if saju_data.get('birth_info'):
            lines.append(f"- 생년월일시: {saju_data['birth_info']}")
        lines.append("\n---\n")
        
        sections = result_json.get("sections", {})
        for spec in SECTION_SPECS:
            section = sections.get(spec["id"], {})
            lines.append(f"## {spec['title']}\n")
            body = section.get("body_markdown", "") or section.get("summary", "내용 없음")
            lines.append(body)
            lines.append("\n")
        
        return "\n".join(lines)
    
    async def _send_completion_email(self, email: str, name: str, job_id: str):
        """완료 이메일"""
        if not email:
            return
        
        try:
            from app.services.email_sender import email_sender
            
            job = await supabase_service.get_job(job_id)
            if not job:
                return
            
            access_token = job.get("public_token", "")
            if not access_token:
                logger.error(f"[Worker] ⚠️ public_token이 NULL! job_id={job_id}")
                return
            
            await email_sender.send_report_complete(
                to_email=email,
                name=name,
                report_id=job_id,
                access_token=access_token,
                target_year=2026
            )
            logger.info(f"[Worker] ✅ 완료 이메일 발송: {email}")
        except Exception as e:
            logger.warning(f"이메일 발송 실패: {e}")
    
    async def _send_failure_email(self, job: Dict, error: str):
        """실패 이메일"""
        email = job.get("user_email", "")
        if not email:
            return
        
        try:
            from app.services.email_sender import email_sender
            input_json = job.get("input_json") or {}
            name = input_json.get("name", "고객")
            job_id = job.get("id", "")
            
            await email_sender.send_report_failed(
                to_email=email,
                name=name,
                report_id=job_id,
                error_message=error[:200]
            )
            logger.info(f"[Worker] 실패 이메일 발송: {email}")
        except Exception as e:
            logger.warning(f"실패 이메일 발송 실패: {e}")


report_worker = ReportWorker()
