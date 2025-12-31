"""
Master Samples Loader - P0 HOTFIX v2
마스터 샘플 JSON 파일 로드 (BOM 처리 + 0개 폴백)
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

_MASTER_SAMPLES_CACHE: Dict[str, Dict[str, Any]] = {}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 P0: 0개 로드 시 폴백용 내장 기본 샘플
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EMBEDDED_MASTER_SAMPLES = {
    "exec": {
        "section_id": "exec",
        "title": "2026 비즈니스 전략 기상도",
        "body_markdown": """## 2026년 비즈니스 기상도: 전체 흐름 진단

**[엔진 결론]** 귀하의 원국 구조에 따르면 2026년은 변화와 도전의 기운이 감지됩니다.

### 원인(사주/룰카드) → 증상(현장) 연결
원국의 구조로 인해, 해당 업종에서 현재 병목 현상이 두드러지게 나타납니다.

### 리스크 2개
1. **시장 변동성**: 트리거 - 외부 환경 변화 / 피해 - 매출 감소 / 조기경보 - 선행지표 모니터링
2. **실행력 저하**: 트리거 - 리소스 분산 / 피해 - 기회 손실 / 조기경보 - 주간 KPI 체크

### 액션 3개
- **D+14**: 현황 점검 및 데이터 수집
- **D+30**: 핵심 지표 모니터링 시작
- **D+60**: 전략 재수립 및 실행

### 체크리스트 7개
- [ ] 현재 상황 객관적 진단
- [ ] 핵심 지표 정의
- [ ] 데이터 수집 체계 구축
- [ ] 주간 리뷰 일정 확정
- [ ] 팀 역할 재정의
- [ ] 리스크 대응 시나리오 준비
- [ ] 전문가 상담 검토
"""
    },
    "money": {
        "section_id": "money",
        "title": "자본 유동성 및 현금흐름 최적화",
        "body_markdown": """## 자본 유동성 및 현금흐름 최적화

**[엔진 결론]** 원국의 재성 구조에 따라 현금흐름 관리가 핵심 과제입니다.

### 원인(사주/룰카드) → 증상(현장) 연결
재성의 배치로 인해, 매출 변동성과 자금 회전 이슈가 예상됩니다.

### 리스크 2개
1. **현금흐름 불안정**: 트리거 - 매출 지연 / 피해 - 운영자금 부족 / 조기경보 - AR 회전일 모니터링
2. **과잉 투자**: 트리거 - 성급한 확장 / 피해 - 유동성 위기 / 조기경보 - 월별 투자 한도 설정

### 액션 3개
- **D+14**: 현금흐름표 작성 및 분석
- **D+30**: 매출채권 회수 프로세스 정비
- **D+60**: 3개월 자금 예측 시스템 구축

### 체크리스트 7개
- [ ] 월별 현금흐름 추이 분석
- [ ] 주요 매출처 결제 조건 검토
- [ ] 비용 구조 최적화 방안 수립
- [ ] 비상 자금 확보 계획
- [ ] 투자 우선순위 재정렬
- [ ] 금융기관 관계 점검
- [ ] 세금/공과금 일정 확인
"""
    },
    "business": {
        "section_id": "business",
        "title": "시장 포지셔닝 및 상품 확장 전략",
        "body_markdown": """## 시장 포지셔닝 및 상품 확장 전략

**[엔진 결론]** 원국의 관성 구조에 따라 시장 포지셔닝 재검토가 필요합니다.

### 원인(사주/룰카드) → 증상(현장) 연결
관성의 작용으로 인해, 경쟁 환경에서 차별화 전략이 중요해집니다.

### 리스크 2개
1. **포지셔닝 모호**: 트리거 - 시장 변화 / 피해 - 고객 이탈 / 조기경보 - NPS 추이 확인
2. **확장 실패**: 트리거 - 준비 부족 / 피해 - 자원 낭비 / 조기경보 - 파일럿 테스트 결과

### 액션 3개
- **D+14**: 경쟁사 분석 및 벤치마킹
- **D+30**: 핵심 가치 제안 재정의
- **D+60**: 신규 상품/서비스 로드맵 수립

### 체크리스트 7개
- [ ] 타겟 고객 세그먼트 재정의
- [ ] 경쟁 우위 요소 도출
- [ ] 가격 전략 검토
- [ ] 채널 전략 최적화
- [ ] 브랜드 메시지 정비
- [ ] 파트너십 기회 탐색
- [ ] 시장 트렌드 모니터링 체계
"""
    },
    "team": {
        "section_id": "team",
        "title": "조직 확장 및 파트너십 가이드",
        "body_markdown": """## 조직 확장 및 파트너십 가이드

**[엔진 결론]** 원국의 비겁 구조에 따라 파트너십과 팀 관리가 핵심입니다.

### 원인(사주/룰카드) → 증상(현장) 연결
비겁의 배치로 인해, 협력 관계에서 역할 조정이 필요합니다.

### 리스크 2개
1. **팀 갈등**: 트리거 - 역할 모호 / 피해 - 생산성 저하 / 조기경보 - 정기 1:1 미팅
2. **파트너십 실패**: 트리거 - 이해관계 불일치 / 피해 - 기회비용 / 조기경보 - 계약 조건 명확화

### 액션 3개
- **D+14**: 조직 구조 및 역할 재정의
- **D+30**: 핵심 인재 확보 계획 수립
- **D+60**: 파트너십 평가 및 재계약 검토

### 체크리스트 7개
- [ ] 현재 조직도 및 역할 매트릭스 작성
- [ ] 핵심 역량 갭 분석
- [ ] 채용 파이프라인 구축
- [ ] 성과 평가 기준 정비
- [ ] 파트너 관계 현황 점검
- [ ] 협업 프로세스 개선
- [ ] 팀 커뮤니케이션 강화 방안
"""
    },
    "health": {
        "section_id": "health",
        "title": "주요 장애물 및 리스크 (2026)",
        "body_markdown": """## 주요 장애물 및 리스크 (2026)

**[엔진 결론]** 현재 구조상 주요 리스크 요소를 선제적으로 관리해야 합니다.

### 원인(사주/룰카드) → 증상(현장) 연결
원국의 충/형/파 구조로 인해, 예기치 않은 장애물이 발생할 수 있습니다.

### 리스크 2개
1. **번아웃**: 트리거 - 과부하 / 피해 - 의사결정 품질 저하 / 조기경보 - 주간 에너지 체크
2. **외부 리스크**: 트리거 - 시장/규제 변화 / 피해 - 사업 연속성 / 조기경보 - 뉴스 모니터링

### 액션 3개
- **D+14**: 리스크 맵핑 및 우선순위화
- **D+30**: 대응 시나리오별 플랜 B 수립
- **D+60**: 리스크 모니터링 시스템 가동

### 체크리스트 7개
- [ ] 주요 리스크 식별 및 분류
- [ ] 리스크별 영향도/발생확률 평가
- [ ] 대응 책임자 지정
- [ ] 비상 연락망 정비
- [ ] 보험/법적 대비 점검
- [ ] 건강 관리 루틴 확립
- [ ] 스트레스 관리 방안 마련
"""
    },
    "calendar": {
        "section_id": "calendar",
        "title": "12개월 비즈니스 스프린트 캘린더",
        "body_markdown": """## 12개월 비즈니스 스프린트 캘린더

**[엔진 결론]** 원국의 월운 흐름에 따라 시기별 전략 조정이 필요합니다.

### 원인(사주/룰카드) → 증상(현장) 연결
대운/세운의 흐름으로 인해, 분기별 에너지 변화를 고려한 계획이 효과적입니다.

### Q1 (1-3월): 기반 구축
- 연간 목표 수립 및 팀 얼라인먼트
- 핵심 프로세스 정비

### Q2 (4-6월): 성장 가속
- 마케팅 캠페인 집중
- 신규 고객 확보 드라이브

### Q3 (7-9월): 최적화
- 성과 분석 및 피벗
- 효율성 개선 프로젝트

### Q4 (10-12월): 수확 및 준비
- 연말 마감 및 성과 정산
- 차년도 전략 수립

### 체크리스트 7개
- [ ] 분기별 OKR 설정
- [ ] 월간 리뷰 일정 확정
- [ ] 주요 마일스톤 캘린더 등록
- [ ] 시즌별 프로모션 계획
- [ ] 휴가/이벤트 고려한 리소스 플래닝
- [ ] 외부 일정(컨퍼런스, 전시회) 체크
- [ ] 분기별 예산 배분 계획
"""
    },
    "sprint": {
        "section_id": "sprint",
        "title": "향후 90일 매출 극대화 액션플랜",
        "body_markdown": """## 향후 90일 매출 극대화 액션플랜

**[엔진 결론]** 원국의 식상 구조에 따라 90일 집중 실행이 효과적입니다.

### 원인(사주/룰카드) → 증상(현장) 연결
식상의 에너지로 인해, 단기 집중 프로젝트에서 성과가 기대됩니다.

### Week 1-2: 진단 및 셋업
- 현재 매출 구조 분석
- 퀵윈 기회 식별
- 팀 역할 배분

### Week 3-6: 실행 1단계
- 핵심 액션 아이템 실행
- 주간 성과 트래킹
- 빠른 피드백 루프

### Week 7-10: 가속 및 조정
- 성과 기반 리소스 재배치
- 병목 해결
- 추가 기회 발굴

### Week 11-12: 마무리 및 다음 사이클 준비
- 90일 성과 정산
- 학습 포인트 정리
- 다음 90일 계획 수립

### 체크리스트 7개
- [ ] 90일 목표 수치 확정
- [ ] 주간 체크인 일정 설정
- [ ] 핵심 KPI 대시보드 구축
- [ ] 팀별 책임 액션 리스트
- [ ] 위클리 리뷰 포맷 확정
- [ ] 성과 인센티브 구조 설계
- [ ] 90일 후 회고 일정 예약
"""
    }
}


def load_master_samples(version: str = "v1") -> Dict[str, Any]:
    """
    마스터 샘플 로드 (utf-8-sig로 BOM 처리 + 0개 폴백)
    """
    cache_key = version
    if cache_key in _MASTER_SAMPLES_CACHE:
        return _MASTER_SAMPLES_CACHE[cache_key]
    
    base_dir = Path(__file__).parent / version
    samples = {}
    
    if base_dir.exists():
        for json_file in base_dir.glob("*.json"):
            try:
                # 🔥 P0 철벽: bytes BOM + unicode BOM 둘 다 제거
                raw = json_file.read_bytes()
                
                # 1) bytes BOM 제거 (정확히 prefix 제거)
                if raw.startswith(b"\xef\xbb\xbf"):
                    raw = raw[3:]
                
                text = raw.decode("utf-8", errors="strict")
                
                # 2) unicode BOM 제거 (혹시 남아있으면)
                text = text.lstrip("\ufeff")
                
                data = json.loads(text)
                
                section_id = data.get("section_id", json_file.stem)
                samples[section_id] = data
                logger.debug(f"[MasterSamples] ✅ 로드: {section_id}")
            except Exception as e:
                logger.error(f"[MasterSamples] ❌ 파일 로드 실패: {json_file.name} | error={e}")
    else:
        logger.warning(f"[MasterSamples] ⚠️ 디렉토리 없음: {base_dir}")
    
    # 🔥 P0: 0개 로드 시 내장 폴백
    if len(samples) == 0:
        logger.error(f"[MasterSamples] ❌ {version}=0개 → fallback to EMBEDDED_MASTER_SAMPLES")
        samples = EMBEDDED_MASTER_SAMPLES.copy()
    
    # 🔥 로드 완료 로그 (섹션 키 목록 포함)
    logger.info(f"[MasterSamples] {version} 로드 완료: {len(samples)}개 섹션 | keys={sorted(samples.keys())}")
    
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

