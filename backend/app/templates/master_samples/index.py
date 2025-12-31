"""
Master Samples Loader - P0
마스터 샘플 JSON 파일 로드
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# 캐시
_MASTER_SAMPLES_CACHE: Dict[str, Dict[str, Any]] = {}


def load_master_samples(version: str = "v1") -> Dict[str, Any]:
    """
    마스터 샘플 로드
    
    Args:
        version: 버전 (v1, v2, ...)
    
    Returns:
        {section_id: {title, body_markdown, ...}}
    """
    cache_key = version
    if cache_key in _MASTER_SAMPLES_CACHE:
        return _MASTER_SAMPLES_CACHE[cache_key]
    
    # 경로 결정
    base_dir = Path(__file__).parent / version
    
    if not base_dir.exists():
        logger.warning(f"[MasterSamples] 디렉토리 없음: {base_dir}")
        return {}
    
    samples = {}
    
    for json_file in base_dir.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            section_id = data.get("section_id", json_file.stem)
            samples[section_id] = data
            logger.debug(f"[MasterSamples] 로드: {section_id}")
        except Exception as e:
            logger.warning(f"[MasterSamples] 파일 로드 실패: {json_file} | {e}")
    
    logger.info(f"[MasterSamples] {version} 로드 완료: {len(samples)}개 섹션")
    _MASTER_SAMPLES_CACHE[cache_key] = samples
    
    return samples


def get_master_sample(section_id: str, version: str = "v1") -> Optional[Dict[str, Any]]:
    """특정 섹션의 마스터 샘플 반환"""
    samples = load_master_samples(version)
    return samples.get(section_id)


def get_master_body_markdown(section_id: str, version: str = "v1") -> str:
    """특정 섹션의 body_markdown 반환"""
    sample = get_master_sample(section_id, version)
    if sample:
        return sample.get("body_markdown", "")
    return ""


# 섹션 ID 매핑 (한글 제목 → section_id)
SECTION_ID_MAP = {
    "2026 비즈니스 전략 기상도": "exec",
    "자본 유동성 및 현금흐름 최적화": "money",
    "시장 포지셔닝 및 상품 확장 전략": "business",
    "조직 확장 및 파트너십 가이드": "team",
    "오너 리스크 관리 및 번아웃 방어": "health",
    "12개월 비즈니스 스프린트 캘린더": "calendar",
    "향후 90일 매출 극대화 액션플랜": "sprint",
}


def normalize_section_id(section_id_or_title: str) -> str:
    """섹션 ID 정규화"""
    return SECTION_ID_MAP.get(section_id_or_title, section_id_or_title)
