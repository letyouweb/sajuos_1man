# -*- coding: utf-8 -*-
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Debug Router - 엔진 검증용 V2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 개선사항:
- Calc→Derive→Match 흐름 증명
- 룰카드 로드 상태 확인
- 매칭 스코어링 랭킹 상세 표시
- 사주 4주가 반드시 다른 케이스에서 다르게 나오는지 검증
- Pillars 검증 개선 (한글 길이 문제 해결, 시주 선택적)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/debug", tags=["debug"])


class EngineDebugResponse(BaseModel):
    """엔진 디버그 응답"""
    # 1. 사주 계산 결과 (Calc)
    pillars: dict
    
    # 2. 파생 특징 (Derive)
    derived: dict
    
    # 3. 매칭 요약 (Match)
    match_summary: dict
    
    # 4. Raw JSON (상세 추적용)
    raw_json: dict
    
    # 5. 룰카드 로드 상태
    rulecard_status: dict
    
    # 6. 검증 플래그
    validation: dict


@router.get("/engine", response_model=EngineDebugResponse)
async def debug_engine(
    birth_year: int = Query(..., description="출생 연도", ge=1900, le=2100),
    birth_month: int = Query(..., description="출생 월", ge=1, le=12),
    birth_day: int = Query(..., description="출생 일", ge=1, le=31),
    birth_hour: Optional[int] = Query(None, description="출생 시 (0-23)", ge=0, le=23),
    target_year: int = Query(2026, description="분석 연도", ge=2020, le=2100)
):
    """
    🔍 **SajuOS V1.0 하이브리드 엔진 디버그 엔드포인트**
    
    **목적**: Calc→Derive→Match 흐름이 실제로 작동하는지 증명
    
    **반환**:
    - `pillars`: 사주 8글자 (년/월/일/시주)
    - `derived`: 파생 특징 (일간, 오행, 십성, 구조, 타이밍)
    - `match_summary`: 섹션별 매칭 결과 (카드 수, Top ID, 평균 점수)
    - `raw_json`: 전체 Raw JSON (matched_rule_ids, match_scores, fired_triggers)
    - `rulecard_status`: 룰카드 로드 상태 (총 카드 수, 토픽별 분포)
    - `validation`: 검증 플래그 (pillars_valid, matches_valid, scores_valid)
    
    **예제**:
    ```
    GET /api/v1/debug/engine?birth_year=1988&birth_month=5&birth_day=15&birth_hour=10&target_year=2026
    ```
    
    **검증 항목**:
    1. ✅ 입력 2개가 다르면 `pillars`가 반드시 다름
    2. ✅ 섹션별 매칭 카드 수가 0이 아님
    3. ✅ raw_json에 used_rulecard_ids + score trace 남음
    4. ✅ 룰카드 로드 상태 확인 (0장 방지)
    """
    try:
        from app.services.calc_module import calc_module
        from app.services.derive_module import derive_module
        from app.services.match_module import match_module
        
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"🔍 [Debug] 엔진 테스트 시작")
        logger.info(f"   입력: {birth_year}-{birth_month:02d}-{birth_day:02d} {birth_hour}시")
        logger.info(f"   분석년도: {target_year}년")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # STEP 1: Calc 모듈 - 사주 8글자 계산
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        logger.info(f"[Step 1] Calc 모듈 실행...")
        pillars = await calc_module.calculate_pillars(
            birth_year=birth_year,
            birth_month=birth_month,
            birth_day=birth_day,
            birth_hour=birth_hour,
            birth_minute=0
        )
        
        pillars_dict = pillars.to_dict()
        year_ganji = pillars.year.ganji if pillars.year else ""
        month_ganji = pillars.month.ganji if pillars.month else ""
        day_ganji = pillars.day.ganji if pillars.day else ""
        hour_ganji = pillars.hour.ganji if pillars.hour else ""
        
        logger.info(f"✅ Calc 완료: {year_ganji} {month_ganji} {day_ganji} {hour_ganji}")
        
        # 🔥 Pillars 검증 개선 (한글 길이 문제 해결, 시주 선택적)
        pillars_valid = all([
            pillars.year is not None,
            pillars.month is not None,
            pillars.day is not None,
            year_ganji and year_ganji != "?",  # 비어있지 않고 "?"가 아님
            month_ganji and month_ganji != "?",
            day_ganji and day_ganji != "?"
        ])
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # STEP 2: Derive 모듈 - 특징 파생
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        logger.info(f"[Step 2] Derive 모듈 실행...")
        features = derive_module.derive_features(pillars, target_year=target_year)
        features_dict = features.to_dict()
        
        logger.info(f"✅ Derive 완료:")
        logger.info(f"   일간: {features.day_master} ({features.day_master_element})")
        logger.info(f"   구조: {features.structure}")
        logger.info(f"   강약: {'신강' if features.is_strong_self else '신약'}")
        logger.info(f"   강한 오행: {features.strong_elements}")
        logger.info(f"   주도 십성: {features.dominant_ten_god}")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # STEP 3: Match 모듈 - 룰카드 매칭
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        logger.info(f"[Step 3] Match 모듈 실행...")
        
        # 3-1. 룰카드 로드 상태 확인
        if not match_module.loaded or not match_module.store:
            logger.info(f"   룰카드 미로드 상태 → 로드 시작")
            
            # 룰카드 경로 찾기
            backend_path = Path(__file__).parent.parent.parent
            rulecards_path = backend_path / "data" / "sajuos_master_db.jsonl"
            
            if not rulecards_path.exists():
                rulecards_path = backend_path / "data" / "rulecards.jsonl"
            
            if not rulecards_path.exists():
                # Fallback: temp_rulecards.jsonl
                rulecards_path = backend_path / "temp_rulecards.jsonl"
            
            if not rulecards_path.exists():
                raise FileNotFoundError(
                    f"❌ 룰카드 파일 없음: {rulecards_path}\n"
                    f"   data/sajuos_master_db.jsonl, data/rulecards.jsonl 또는 temp_rulecards.jsonl이 필요합니다."
                )
            
            logger.info(f"   룰카드 파일: {rulecards_path}")
            match_module.load_rulecards(str(rulecards_path))
        
        # 3-2. 룰카드 로드 상태 체크
        total_cards = len(match_module.store.cards) if match_module.store else 0
        by_topic = match_module.store.by_topic if match_module.store else {}
        
        logger.info(f"✅ 룰카드 로드 완료: {total_cards}장")
        for topic, cards in by_topic.items():
            logger.info(f"   {topic}: {len(cards)}장")
        
        # 3-3. 룰카드 0장 검증
        if total_cards == 0:
            raise RuntimeError(
                f"❌ 룰카드 로드 실패: 0장\n"
                f"   rulecards.jsonl 파일을 확인하세요."
            )
        
        # 3-4. 매칭 실행
        matches = match_module.match_all_sections(features)
        logger.info(f"✅ Match 완료: {len(matches)}개 섹션")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # STEP 4: Match Summary 생성 (스코어링 랭킹 표시)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        match_summary = {}
        total_matched_cards = 0
        
        for section_id, section_match in matches.items():
            card_count = len(section_match.cards)
            total_matched_cards += card_count
            
            # Top 5 카드 ID와 점수
            top_cards_with_scores = [
                {
                    "card_id": card.card_id,
                    "score": round(card.score, 2),
                    "score_details": card.score_details  # 점수 상세
                }
                for card in section_match.cards[:5]
            ]
            
            match_summary[section_id] = {
                "count": card_count,
                "top_cards": top_cards_with_scores,
                "avg_score": round(section_match.avg_score, 2)
            }
            
            logger.info(f"   {section_id}: {card_count}장, 평균점수: {section_match.avg_score:.2f}")
        
        # 매칭 검증
        matches_valid = all([
            len(section_match.cards) > 0
            for section_match in matches.values()
        ])
        
        scores_valid = all([
            section_match.avg_score > 0
            for section_match in matches.values()
        ])
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # STEP 5: Raw JSON 생성
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        raw_json = match_module.generate_raw_json(features, matches)
        
        # Raw JSON 간소화 (응답 크기 감소)
        raw_json_compact = {
            "matched_rule_ids": raw_json["matched_rule_ids"],
            "match_scores": raw_json["match_scores"],
            "fired_triggers": {
                k: v[:3] for k, v in raw_json["fired_triggers"].items()  # 각 카드당 Top 3 트리거만
            },
            "total_matched": len(raw_json["matched_rule_ids"]),
            "features_summary": {
                "day_master": features.day_master,
                "day_master_element": features.day_master_element,
                "structure": features.structure,
                "dominant_ten_god": features.dominant_ten_god,
                "is_strong_self": features.is_strong_self
            }
        }
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # STEP 6: 검증 플래그
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        validation = {
            "pillars_valid": pillars_valid,
            "pillars_year": year_ganji or "N/A",
            "pillars_month": month_ganji or "N/A",
            "pillars_day": day_ganji or "N/A",
            "pillars_hour": hour_ganji or "N/A",
            "matches_valid": matches_valid,
            "scores_valid": scores_valid,
            "total_matched_cards": total_matched_cards,
            "rulecards_loaded": total_cards,
            "all_checks_passed": all([
                pillars_valid,
                matches_valid,
                scores_valid,
                total_cards > 0,
                total_matched_cards > 0
            ])
        }
        
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"✅ 엔진 테스트 완료:")
        logger.info(f"   사주 유효: {pillars_valid}")
        logger.info(f"   매칭 유효: {matches_valid}")
        logger.info(f"   점수 유효: {scores_valid}")
        logger.info(f"   룰카드 로드: {total_cards}장")
        logger.info(f"   총 매칭 카드: {total_matched_cards}장")
        logger.info(f"   전체 검증: {'✅ PASS' if validation['all_checks_passed'] else '❌ FAIL'}")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        return EngineDebugResponse(
            pillars=pillars_dict,
            derived={
                "day_master": features.day_master,
                "day_master_element": features.day_master_element,
                "day_master_yin_yang": features.day_master_yin_yang,
                "is_strong_self": features.is_strong_self,
                "strong_elements": features.strong_elements,
                "weak_elements": features.weak_elements,
                "element_count": features.element_count,
                "dominant_ten_god": features.dominant_ten_god,
                "ten_gods_count": features.ten_gods_count,
                "ten_gods": features.ten_gods[:10],  # Top 10만
                "structure": features.structure,
                "structure_desc": features.structure_desc,
                "timing_year": features.timing_year,
                "year_luck_element": features.year_luck_element,
                "is_favorable_year": features.is_favorable_year,
                "timing_desc": features.timing_desc
            },
            match_summary=match_summary,
            raw_json=raw_json_compact,
            rulecard_status={
                "loaded": match_module.loaded,
                "total_cards": total_cards,
                "by_topic": {k: len(v) for k, v in by_topic.items()},
                "idf_tokens": len(match_module.store.idf) if match_module.store else 0
            },
            validation=validation
        )
    
    except Exception as e:
        logger.error(f"❌ [Debug] 엔진 테스트 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "type": type(e).__name__,
                "message": "엔진 디버그 실행 중 오류가 발생했습니다."
            }
        )


@router.get("/health")
async def health_check():
    """
    🏥 헬스 체크 엔드포인트
    
    룰카드 로드 상태 및 모듈 상태 확인
    """
    from app.services.match_module import match_module
    
    status = {
        "status": "ok",
        "rulecard_loaded": match_module.loaded,
        "total_cards": len(match_module.store.cards) if match_module.store else 0,
        "modules": {
            "calc": "available",
            "derive": "available",
            "match": "loaded" if match_module.loaded else "not_loaded"
        }
    }
    
    return status
