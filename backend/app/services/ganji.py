"""
60갑자 계산 모듈
- 천간(10개) × 지지(12개) = 60갑자
- 연두법(월간 계산)
- 일간 기준 시간 천간 계산
"""
from datetime import date, datetime
from typing import Tuple, Optional

# 천간 (10개)
CHEONGAN = ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계"]

# 지지 (12개)
JIJI = ["자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해"]

# 지지 오행
JIJI_HANJA = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
CHEONGAN_HANJA = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]

# 천간-오행 매핑
GAN_TO_ELEMENT = {
    "갑": "목", "을": "목",
    "병": "화", "정": "화",
    "무": "토", "기": "토",
    "경": "금", "신": "금",
    "임": "수", "계": "수"
}

# 지지-오행 매핑
JI_TO_ELEMENT = {
    "자": "수", "축": "토", "인": "목", "묘": "목",
    "진": "토", "사": "화", "오": "화", "미": "토",
    "신": "금", "유": "금", "술": "토", "해": "수"
}

# 일간 설명
DAY_MASTER_DESC = {
    "갑": "큰 나무(甲木) - 곧고 뻗어나가는 성장의 기운",
    "을": "작은 나무(乙木) - 유연하고 적응력 있는 기운",
    "병": "태양(丙火) - 밝고 뜨거운 열정의 기운",
    "정": "촛불(丁火) - 따뜻하고 은은한 빛의 기운",
    "무": "큰 산(戊土) - 안정적이고 묵직한 기운",
    "기": "논밭(己土) - 포용하고 키워내는 기운",
    "경": "바위/쇠(庚金) - 강하고 결단력 있는 기운",
    "신": "보석(辛金) - 섬세하고 빛나는 기운",
    "임": "큰 물(壬水) - 넓고 깊은 지혜의 기운",
    "계": "이슬/비(癸水) - 촉촉하고 스며드는 기운"
}


class GanjiCalculator:
    """60갑자 계산기"""
    
    # ===== 연주 계산 =====
    @staticmethod
    def calc_year_ganji(adjusted_year: int) -> Tuple[str, str, int, int]:
        """
        연주 계산 (입춘 보정된 연도 기준)
        
        Args:
            adjusted_year: 입춘 보정된 연도 (solar_terms에서 계산)
        
        Returns:
            (천간, 지지, 천간인덱스, 지지인덱스)
        """
        # 1984년 = 갑자년 기준
        gan_idx = (adjusted_year - 4) % 10
        ji_idx = (adjusted_year - 4) % 12
        
        return CHEONGAN[gan_idx], JIJI[ji_idx], gan_idx, ji_idx
    
    # ===== 월주 계산 =====
    @staticmethod
    def calc_month_ganji(
        year_gan_idx: int,
        month_ji_idx: int
    ) -> Tuple[str, str, int, int]:
        """
        월주 계산 (연두법)
        
        Args:
            year_gan_idx: 연간 인덱스 (0=갑, 1=을, ...)
            month_ji_idx: 월지 인덱스 (0=인, 1=묘, ..., 11=축)
        
        연두법 공식:
        - 갑/기년: 인월 천간 = 병(2)
        - 을/경년: 인월 천간 = 무(4)
        - 병/신년: 인월 천간 = 경(6)
        - 정/임년: 인월 천간 = 임(8)
        - 무/계년: 인월 천간 = 갑(0)
        
        Returns:
            (천간, 지지, 천간인덱스, 지지인덱스)
        """
        # 연간 → 인월 천간 시작점
        year_to_month_start = {
            0: 2,  # 갑 → 병인월
            1: 4,  # 을 → 무인월
            2: 6,  # 병 → 경인월
            3: 8,  # 정 → 임인월
            4: 0,  # 무 → 갑인월
            5: 2,  # 기 → 병인월
            6: 4,  # 경 → 무인월
            7: 6,  # 신 → 경인월
            8: 8,  # 임 → 임인월
            9: 0,  # 계 → 갑인월
        }
        
        start_gan_idx = year_to_month_start[year_gan_idx]
        
        # 월간 = 인월 천간 + (월지 인덱스) mod 10
        month_gan_idx = (start_gan_idx + month_ji_idx) % 10
        
        # 월지 = 인(2) + 월지인덱스 = 실제 지지
        # month_ji_idx: 0=인, 1=묘, ..., 11=축
        actual_ji_idx = (2 + month_ji_idx) % 12  # 인(寅)=2부터 시작
        
        return CHEONGAN[month_gan_idx], JIJI[actual_ji_idx], month_gan_idx, actual_ji_idx
    
    # ===== 일주 계산 =====
    @staticmethod
    def calc_day_ganji(year: int, month: int, day: int) -> Tuple[str, str, int, int]:
        """
        일주 계산
        
        기준일: 1900년 1월 31일 = 갑자일 (검증된 기준)
        (참고: 1900년 1월 1일은 갑술일이 아니라 계해일이라는 자료도 있음)
        
        ※ 여기서는 검증된 기준일 사용: 2000년 1월 1일 = 갑진일
        
        Returns:
            (천간, 지지, 천간인덱스, 지지인덱스)
        """
        # 검증된 기준: 2000년 1월 1일 = 갑진일 (갑=0, 진=4)
        base_date = date(2000, 1, 1)
        target_date = date(year, month, day)
        days_diff = (target_date - base_date).days
        
        # 2000년 1월 1일: 갑(0) + 진(4)
        day_gan_idx = (0 + days_diff) % 10
        day_ji_idx = (4 + days_diff) % 12
        
        return CHEONGAN[day_gan_idx], JIJI[day_ji_idx], day_gan_idx, day_ji_idx
    
    # ===== 시주 계산 =====
    @staticmethod
    def calc_hour_ganji(
        day_gan_idx: int,
        hour: int,
        minute: int = 0
    ) -> Tuple[str, str, int, int]:
        """
        시주 계산
        
        시간 → 지지 매핑 (2시간 단위):
        - 子시: 23:00~00:59
        - 丑시: 01:00~02:59
        - 寅시: 03:00~04:59
        - 卯시: 05:00~06:59
        - 辰시: 07:00~08:59
        - 巳시: 09:00~10:59
        - 午시: 11:00~12:59
        - 未시: 13:00~14:59
        - 申시: 15:00~16:59
        - 酉시: 17:00~18:59
        - 戌시: 19:00~20:59
        - 亥시: 21:00~22:59
        
        시간 천간: 일간 기준 자시 천간 + 지지 index
        
        Args:
            day_gan_idx: 일간 인덱스
            hour: 시 (0-23)
            minute: 분 (0-59)
        
        Returns:
            (천간, 지지, 천간인덱스, 지지인덱스)
        """
        # 시간 → 지지 인덱스 계산
        # 23시~00시59분 = 자시(0), 01시~02시59분 = 축시(1), ...
        if hour == 23:
            hour_ji_idx = 0  # 자시
        else:
            hour_ji_idx = (hour + 1) // 2
        
        # 일간 → 자시 천간 시작점
        day_to_hour_start = {
            0: 0,  # 갑일 → 갑자시
            1: 2,  # 을일 → 병자시
            2: 4,  # 병일 → 무자시
            3: 6,  # 정일 → 경자시
            4: 8,  # 무일 → 임자시
            5: 0,  # 기일 → 갑자시
            6: 2,  # 경일 → 병자시
            7: 4,  # 신일 → 무자시
            8: 6,  # 임일 → 경자시
            9: 8,  # 계일 → 임자시
        }
        
        start_gan_idx = day_to_hour_start[day_gan_idx]
        hour_gan_idx = (start_gan_idx + hour_ji_idx) % 10
        
        return CHEONGAN[hour_gan_idx], JIJI[hour_ji_idx], hour_gan_idx, hour_ji_idx
    
    @staticmethod
    def get_hour_ji_index(hour: int) -> int:
        """시간 → 지지 인덱스"""
        if hour == 23:
            return 0
        return (hour + 1) // 2
    
    @staticmethod
    def get_hour_range(ji_idx: int) -> Tuple[str, str]:
        """지지 인덱스 → 시간 범위 문자열"""
        ranges = [
            ("23:00", "00:59"),  # 자
            ("01:00", "02:59"),  # 축
            ("03:00", "04:59"),  # 인
            ("05:00", "06:59"),  # 묘
            ("07:00", "08:59"),  # 진
            ("09:00", "10:59"),  # 사
            ("11:00", "12:59"),  # 오
            ("13:00", "14:59"),  # 미
            ("15:00", "16:59"),  # 신
            ("17:00", "18:59"),  # 유
            ("19:00", "20:59"),  # 술
            ("21:00", "22:59"),  # 해
        ]
        return ranges[ji_idx]


# 유틸리티 함수
def get_ganji_str(gan: str, ji: str) -> str:
    """간지 문자열 생성"""
    return f"{gan}{ji}"


def get_ganji_hanja(gan_idx: int, ji_idx: int) -> str:
    """간지 한자 문자열"""
    return f"{CHEONGAN_HANJA[gan_idx]}{JIJI_HANJA[ji_idx]}"


def get_element(gan_or_ji: str, is_gan: bool = True) -> str:
    """천간/지지의 오행 반환"""
    if is_gan:
        return GAN_TO_ELEMENT.get(gan_or_ji, "")
    return JI_TO_ELEMENT.get(gan_or_ji, "")


# 싱글톤
ganji_calc = GanjiCalculator()
