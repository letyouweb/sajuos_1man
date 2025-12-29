"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2️⃣ DERIVE 모듈 - 사주 특징 파생
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
pillars → day_master, strong/weak elements, ten_gods, structure, timing
결과를 saju_features로 확정
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from collections import Counter

from app.services.calc_module import SajuPillars, PillarData

logger = logging.getLogger(__name__)


# 오행 상생상극 관계
ELEMENT_CYCLE = {
    "목": {"generates": "화", "conquers": "토", "conquered_by": "금", "generated_by": "수"},
    "화": {"generates": "토", "conquers": "금", "conquered_by": "수", "generated_by": "목"},
    "토": {"generates": "금", "conquers": "수", "conquered_by": "목", "generated_by": "화"},
    "금": {"generates": "수", "conquers": "목", "conquered_by": "화", "generated_by": "토"},
    "수": {"generates": "목", "conquers": "화", "conquered_by": "토", "generated_by": "금"},
}

# 십성(十星) 관계 - 일간 기준
TEN_GODS_RELATION = {
    # 나와 같은 오행
    "same": {"me_same_yin_yang": "비견", "me_diff_yin_yang": "겁재"},
    # 내가 생하는 오행
    "i_generate": {"me_same_yin_yang": "식신", "me_diff_yin_yang": "상관"},
    # 내가 극하는 오행
    "i_conquer": {"me_same_yin_yang": "편재", "me_diff_yin_yang": "정재"},
    # 나를 극하는 오행
    "conquers_me": {"me_same_yin_yang": "편관", "me_diff_yin_yang": "정관"},
    # 나를 생하는 오행
    "generates_me": {"me_same_yin_yang": "편인", "me_diff_yin_yang": "정인"},
}

# 천간 음양
CHEONGAN_YIN_YANG = {
    "갑": "양", "을": "음",
    "병": "양", "정": "음",
    "무": "양", "기": "음",
    "경": "양", "신": "음",
    "임": "양", "계": "음"
}


@dataclass
class TenGod:
    """십성(十星) 정보"""
    name: str               # 십성 이름 (비견, 식신, 정재 등)
    position: str          # 위치 (년간, 월간, 일지, 시간 등)
    element: str           # 오행
    gan_or_ji: str         # 천간/지지


@dataclass
class SajuFeatures:
    """사주 파생 특징"""
    # 원본 pillars
    pillars: Dict[str, Any]
    
    # 1. 일간 정보
    day_master: str                     # 일간 (나)
    day_master_element: str             # 일간 오행
    day_master_yin_yang: str           # 일간 음양
    
    # 2. 오행 강약
    element_count: Dict[str, int]      # 오행별 개수
    strong_elements: List[str]          # 강한 오행 (상위 2개)
    weak_elements: List[str]            # 약한 오행 (하위 2개)
    is_strong_self: bool                # 신강/신약 (나의 오행이 강한가)
    
    # 3. 십성 분포
    ten_gods: List[TenGod]              # 십성 목록
    ten_gods_count: Dict[str, int]      # 십성별 개수
    dominant_ten_god: str               # 주도 십성
    
    # 4. 사주 구조
    structure: str                      # 격국 (식신생재, 재다신약 등)
    structure_desc: str                 # 구조 설명
    
    # 5. 타이밍 (2026년)
    timing_year: int                    # 분석 연도
    year_luck_element: str              # 연운 오행 (2026년 = 병오년)
    is_favorable_year: bool             # 유리한 연도 여부
    timing_desc: str                    # 타이밍 설명
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return asdict(self)


class DeriveModule:
    """
    사주 특징 파생 모듈
    
    Features:
    1. 일간 추출
    2. 오행 분석 (강약)
    3. 십성 계산
    4. 구조 판단
    5. 타이밍 분석 (2026년)
    """
    
    def derive_features(
        self,
        pillars: SajuPillars,
        target_year: int = 2026
    ) -> SajuFeatures:
        """
        사주 특징 파생
        
        Args:
            pillars: 사주 8글자
            target_year: 분석 기준 연도
        
        Returns:
            SajuFeatures: 파생된 특징
        """
        logger.info("[DeriveModule] 특징 파생 시작")
        
        # 1. 일간 정보
        day_master = pillars.day.gan
        day_master_element = pillars.day.gan_element
        day_master_yin_yang = CHEONGAN_YIN_YANG[day_master]
        
        # 2. 오행 분석
        element_count = self._count_elements(pillars)
        strong_elements, weak_elements = self._analyze_element_strength(element_count)
        is_strong_self = self._is_strong_self(day_master_element, element_count, pillars)
        
        # 3. 십성 계산
        ten_gods = self._calculate_ten_gods(pillars)
        ten_gods_count = Counter([tg.name for tg in ten_gods])
        dominant_ten_god = ten_gods_count.most_common(1)[0][0] if ten_gods_count else "미상"
        
        # 4. 구조 판단
        structure, structure_desc = self._determine_structure(
            day_master_element, element_count, ten_gods_count, is_strong_self
        )
        
        # 5. 타이밍 분석 (2026년 = 병오년)
        year_luck_element, is_favorable_year, timing_desc = self._analyze_timing(
            target_year, day_master_element, strong_elements, weak_elements
        )
        
        features = SajuFeatures(
            pillars=pillars.to_dict(),
            day_master=day_master,
            day_master_element=day_master_element,
            day_master_yin_yang=day_master_yin_yang,
            element_count=element_count,
            strong_elements=strong_elements,
            weak_elements=weak_elements,
            is_strong_self=is_strong_self,
            ten_gods=[asdict(tg) for tg in ten_gods],
            ten_gods_count=dict(ten_gods_count),
            dominant_ten_god=dominant_ten_god,
            structure=structure,
            structure_desc=structure_desc,
            timing_year=target_year,
            year_luck_element=year_luck_element,
            is_favorable_year=is_favorable_year,
            timing_desc=timing_desc
        )
        
        logger.info(f"[DeriveModule] 완료 - 일간:{day_master}, 구조:{structure}, 타이밍:{timing_desc}")
        
        return features
    
    def _count_elements(self, pillars: SajuPillars) -> Dict[str, int]:
        """오행 개수 세기"""
        elements = []
        
        # 천간
        elements.append(pillars.year.gan_element)
        elements.append(pillars.month.gan_element)
        elements.append(pillars.day.gan_element)
        if pillars.hour:
            elements.append(pillars.hour.gan_element)
        
        # 지지
        elements.append(pillars.year.ji_element)
        elements.append(pillars.month.ji_element)
        elements.append(pillars.day.ji_element)
        if pillars.hour:
            elements.append(pillars.hour.ji_element)
        
        return dict(Counter(elements))
    
    def _analyze_element_strength(
        self,
        element_count: Dict[str, int]
    ) -> tuple[List[str], List[str]]:
        """오행 강약 분석"""
        sorted_elements = sorted(
            element_count.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        strong = [e[0] for e in sorted_elements[:2]]  # 상위 2개
        weak = [e[0] for e in sorted_elements[-2:]]   # 하위 2개
        
        return strong, weak
    
    def _is_strong_self(
        self,
        day_master_element: str,
        element_count: Dict[str, int],
        pillars: SajuPillars
    ) -> bool:
        """신강/신약 판단"""
        
        # 일간 오행 개수
        my_count = element_count.get(day_master_element, 0)
        
        # 생하는 오행 (생아) 개수
        cycle = ELEMENT_CYCLE[day_master_element]
        support_element = cycle["generated_by"]
        support_count = element_count.get(support_element, 0)
        
        # 같은 오행(비겁) + 생하는 오행(인성) >= 3이면 신강
        total_support = my_count + support_count
        
        return total_support >= 3
    
    def _calculate_ten_gods(self, pillars: SajuPillars) -> List[TenGod]:
        """십성 계산"""
        ten_gods = []
        
        day_gan = pillars.day.gan
        day_element = pillars.day.gan_element
        day_yin_yang = CHEONGAN_YIN_YANG[day_gan]
        
        # 각 기둥의 천간 십성 계산
        positions = [
            ("년간", pillars.year.gan, pillars.year.gan_element),
            ("월간", pillars.month.gan, pillars.month.gan_element),
            ("시간", pillars.hour.gan, pillars.hour.gan_element) if pillars.hour else None,
        ]
        
        for pos_data in positions:
            if pos_data is None:
                continue
            
            position, gan, element = pos_data
            
            # 일간 자신은 제외
            if gan == day_gan:
                continue
            
            ten_god_name = self._get_ten_god_name(
                day_element, element, day_yin_yang, CHEONGAN_YIN_YANG[gan]
            )
            
            ten_gods.append(TenGod(
                name=ten_god_name,
                position=position,
                element=element,
                gan_or_ji=gan
            ))
        
        # 지지도 간략히 추가 (장간 생략)
        ji_positions = [
            ("년지", pillars.year.ji_element),
            ("월지", pillars.month.ji_element),
            ("일지", pillars.day.ji_element),
            ("시지", pillars.hour.ji_element) if pillars.hour else None,
        ]
        
        for pos_data in ji_positions:
            if pos_data is None:
                continue
            
            position, element = pos_data
            
            # 지지의 십성은 간략히 판단 (음양 고려 안함)
            ten_god_name = self._get_ten_god_simple(day_element, element)
            
            ten_gods.append(TenGod(
                name=ten_god_name,
                position=position,
                element=element,
                gan_or_ji="지지"
            ))
        
        return ten_gods
    
    def _get_ten_god_name(
        self,
        day_element: str,
        target_element: str,
        day_yin_yang: str,
        target_yin_yang: str
    ) -> str:
        """십성 이름 계산 (정확한 음양 고려)"""
        
        cycle = ELEMENT_CYCLE[day_element]
        same_yin_yang = (day_yin_yang == target_yin_yang)
        
        # 나와 같은 오행
        if target_element == day_element:
            return "비견" if same_yin_yang else "겁재"
        
        # 내가 생하는 오행
        if target_element == cycle["generates"]:
            return "식신" if same_yin_yang else "상관"
        
        # 내가 극하는 오행 (재성)
        if target_element == cycle["conquers"]:
            return "편재" if same_yin_yang else "정재"
        
        # 나를 극하는 오행 (관성)
        if target_element == cycle["conquered_by"]:
            return "편관" if same_yin_yang else "정관"
        
        # 나를 생하는 오행 (인성)
        if target_element == cycle["generated_by"]:
            return "편인" if same_yin_yang else "정인"
        
        return "미상"
    
    def _get_ten_god_simple(self, day_element: str, target_element: str) -> str:
        """십성 간략 판단 (지지용, 음양 무시)"""
        cycle = ELEMENT_CYCLE[day_element]
        
        if target_element == day_element:
            return "비겁"
        if target_element == cycle["generates"]:
            return "식상"
        if target_element == cycle["conquers"]:
            return "재성"
        if target_element == cycle["conquered_by"]:
            return "관성"
        if target_element == cycle["generated_by"]:
            return "인성"
        
        return "미상"
    
    def _determine_structure(
        self,
        day_element: str,
        element_count: Dict[str, int],
        ten_gods_count: Dict[str, int],
        is_strong_self: bool
    ) -> tuple[str, str]:
        """사주 구조 판단"""
        
        # 재성 많음
        if ten_gods_count.get("정재", 0) + ten_gods_count.get("편재", 0) >= 3:
            if is_strong_self:
                return "재왕신강", "재물이 많고 내가 강함 - 재물을 잘 다룰 수 있음"
            else:
                return "재다신약", "재물은 많으나 감당하기 어려움 - 과욕 주의"
        
        # 식상생재 구조
        if (ten_gods_count.get("식신", 0) + ten_gods_count.get("상관", 0) >= 2) and \
           (ten_gods_count.get("정재", 0) + ten_gods_count.get("편재", 0) >= 1):
            return "식신생재", "창작/표현으로 재물을 버는 구조 - 자기표현 중요"
        
        # 관인상생
        if (ten_gods_count.get("정관", 0) + ten_gods_count.get("편관", 0) >= 2) and \
           (ten_gods_count.get("정인", 0) + ten_gods_count.get("편인", 0) >= 2):
            return "관인상생", "직장과 학습이 조화로움 - 안정적 성장"
        
        # 비겁 많음
        if ten_gods_count.get("비견", 0) + ten_gods_count.get("겁재", 0) >= 3:
            return "비겁중중", "경쟁과 협력이 많음 - 독립성 중요"
        
        # 인성 많음
        if ten_gods_count.get("정인", 0) + ten_gods_count.get("편인", 0) >= 3:
            return "인성과다", "학습과 후원이 많음 - 행동력 필요"
        
        # 신강/신약 기본
        if is_strong_self:
            return "신강", "자아가 강함 - 주도적 실행력"
        else:
            return "신약", "자아가 약함 - 협력과 지원 필요"
    
    def _analyze_timing(
        self,
        target_year: int,
        day_element: str,
        strong_elements: List[str],
        weak_elements: List[str]
    ) -> tuple[str, bool, str]:
        """타이밍 분석 (특정 연도)"""
        
        # 2026년 = 병오년 (화 오행)
        year_element_map = {
            2026: "화"  # 병오
        }
        
        year_element = year_element_map.get(target_year, "미상")
        
        if year_element == "미상":
            return year_element, False, f"{target_year}년 오행 정보 없음"
        
        # 내 오행과 연도 오행의 관계
        cycle = ELEMENT_CYCLE[day_element]
        
        # 유리한 경우
        favorable_conditions = [
            year_element == cycle["generated_by"],  # 나를 생하는 해
            year_element in strong_elements,         # 이미 강한 오행
        ]
        
        # 불리한 경우
        unfavorable_conditions = [
            year_element == cycle["conquered_by"],  # 나를 극하는 해
            year_element in weak_elements,           # 약한 오행
        ]
        
        is_favorable = any(favorable_conditions) and not any(unfavorable_conditions)
        
        if is_favorable:
            timing_desc = f"{target_year}년은 {year_element} 오행 - 나에게 유리한 시기"
        else:
            timing_desc = f"{target_year}년은 {year_element} 오행 - 신중한 대응 필요"
        
        return year_element, is_favorable, timing_desc


# 싱글톤 인스턴스
derive_module = DeriveModule()
