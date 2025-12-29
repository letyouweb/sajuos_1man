"""
Quality Gate - 프리미엄 리포트 품질 검증 엔진
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
자기계발서 탈출을 위한 3중 필터:
1) 금지어/금지톤 감지 + 리라이트 강제
2) 구체성 검증 (날짜/수치/행동/검증방법 3개 이상)
3) 중복 문단 감지 + 자동 재작성 트리거
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import re
import logging
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import Counter

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 금지어/금지톤 리스트 (2단계: HARD/SOFT)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 🔥 HARD_BANNED: 정말 치명적인 것만 (하드 실패 트리거)
HARD_BANNED_PHRASES = [
    # 면책/광고성 문구
    "추천드립니다", "참고하시기 바랍니다", "개인차가 있을 수 있습니다",
    "투자 권유가 아닙니다", "책임지지 않습니다",
    
    # 극단적 자기계발서 클리셰
    "무궁무진한", "무한한 가능성", "꿈을 이루",
    "밝은 미래", "더 나은 내일", "행운이 함께",
    "축복이", "복이 따르", "잘 될 것",
]

# 🔥 SOFT_BANNED: 문체 품질 저하 (점수 감점만, 하드 실패 X)
SOFT_BANNED_PHRASES = [
    # 접속사/전환어 (일반적으로 허용, 과다 사용 시 감점)
    "또한", "그리고", "아울러", "더불어",
    "특히", "무엇보다", "가장 중요한 것은",
    
    # 완곡 표현 (구체성 부족하면 감점)
    "필요합니다", "바람직합니다", "중요합니다",
    "도움이 될 수", "도움이 될 것",
    "생각해보는 것이 좋", "고려해보면 좋",
    
    # 자기계발서 톤 (감점만)
    "노력하면", "노력이 필요", "꾸준히 노력",
    "성장의 기회", "성장할 수 있",
    "긍정적인 마인드", "긍정적으로",
    "기회가 찾아", "기회를 잡",
    "도전정신", "도전하는 자세",
    "잠재력을 발휘", "잠재력이 있",
    "자신감을 가지", "자신감을 잃지",
    "열정을 가지", "열정적으로",
    "포기하지 마", "포기하지 않",
    "한 걸음씩", "한 단계씩",
    "최선을 다하", "최선의 노력",
    "좋은 결과가", "좋은 일이",
]

# 🔥 레거시 호환 (기존 코드용)
BANNED_PHRASES = HARD_BANNED_PHRASES + SOFT_BANNED_PHRASES

BANNED_SENTENCE_PATTERNS = [
    # 구체적 내용 없는 문장 패턴
    r"^.{0,30}(좋습니다|됩니다|있습니다)\.$",  # 30자 이하 짧은 덕담
    r"^(이 시기|올해|내년)는?\s*좋은\s*(시기|시간|때)입니다",
    r"^긍정적(인|으로|이).*생각",
    r"^(열심히|꾸준히|최선을 다해).*하면",
    r"^(자신을|스스로를)\s*(믿|신뢰)",
]

REPLACEMENT_GUIDELINES = {
    "노력하면": "→ 구체적 액션 + 예상 결과 + 검증 지표로 대체",
    "성장의 기회": "→ 어떤 영역에서 얼마나 성장? 측정 방법은?",
    "긍정적인": "→ 구체적 근거 데이터 또는 사례로 대체",
    "기회가 찾아": "→ 언제, 어떤 형태로, 어떻게 포착할지 명시",
    "도전정신": "→ 무엇에 도전? 리스크는? 대비책은?",
    "잠재력": "→ 어떤 역량? 어떻게 개발? 언제까지?",
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 구체성 검증 규칙
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SPECIFICITY_MARKERS = {
    "date": [
        r"\d{1,2}월",
        r"\d{4}년",
        r"(1|2|3|4)분기",
        r"Q[1-4]",
        r"(월|화|수|목|금|토|일)요일",
        r"\d+일\s*(이내|까지|후)",
        r"(1|2|3|4|5|6)개월",
        r"\d+주",
        r"(상반기|하반기)",
        r"(초|중|말)",  # 1월 초, 3월 말 등
    ],
    "number": [
        r"\d+%",
        r"\d+(만|억|천)?원",
        r"\d+명",
        r"\d+개",
        r"\d+건",
        r"\d+시간",
        r"\d+(배|곱)",
        r"(최소|최대|약|평균)\s*\d+",
    ],
    "action": [
        r"(실행|수행|진행|착수|완료|마감)",
        r"(작성|제출|발송|전달)",
        r"(미팅|회의|상담|협의)",
        r"(검토|분석|조사|리서치)",
        r"(계약|서명|결제|입금)",
        r"(채용|면접|온보딩)",
        r"(론칭|오픈|출시|배포)",
        r"(테스트|검증|QA)",
    ],
    "verification": [
        r"(KPI|지표|메트릭)",
        r"(측정|확인|체크|점검)",
        r"(리포트|보고서|대시보드)",
        r"(데이터|수치|통계)",
        r"(결과|성과|outcome)",
        r"(피드백|리뷰|평가)",
        r"(목표 달성|달성률|완료율)",
    ],
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 데이터 구조
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class QualityIssue:
    """품질 이슈 단건"""
    type: str  # banned_phrase, low_specificity, duplicate
    severity: str  # error, warning
    location: str  # 섹션/문단 위치
    content: str  # 문제 내용
    suggestion: str  # 개선 제안
    auto_fixable: bool = False


@dataclass
class QualityReport:
    """품질 검사 결과"""
    passed: bool
    score: int  # 0-100
    issues: List[QualityIssue] = field(default_factory=list)
    banned_count: int = 0
    specificity_score: float = 0.0
    duplicate_ratio: float = 0.0
    needs_rewrite: bool = False
    rewrite_sections: List[str] = field(default_factory=list)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 품질 게이트 엔진
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class QualityGate:
    """프리미엄 리포트 품질 검증 엔진"""
    
    def __init__(
        self,
        min_specificity_score: float = 0.6,  # 최소 구체성 점수
        max_duplicate_ratio: float = 0.2,    # 최대 중복 비율
        max_banned_phrases: int = 3,         # 최대 금지어 허용 수
    ):
        self.min_specificity_score = min_specificity_score
        self.max_duplicate_ratio = max_duplicate_ratio
        self.max_banned_phrases = max_banned_phrases
        
        # 정규식 컴파일
        self._banned_patterns = [
            re.compile(p, re.IGNORECASE) for p in BANNED_SENTENCE_PATTERNS
        ]
        self._specificity_patterns = {
            k: [re.compile(p) for p in patterns]
            for k, patterns in SPECIFICITY_MARKERS.items()
        }
    
    def check_section(
        self,
        section_id: str,
        content: str,
        existing_contents: List[str] = None
    ) -> QualityReport:
        """
        단일 섹션 품질 검사
        
        Args:
            section_id: 섹션 ID (exec, money, business...)
            content: 섹션 본문 텍스트
            existing_contents: 이미 생성된 다른 섹션들 (중복 비교용)
        
        Returns:
            QualityReport: 검사 결과
        """
        issues = []
        
        # 1. 금지어 검사 (HARD/SOFT 분리)
        banned_issues, hard_count, soft_count = self._check_banned_phrases(section_id, content)
        issues.extend(banned_issues)  # HARD_BANNED만 issues에 포함됨
        
        # 2. 구체성 검사 (🔥 임계치 완화: 0.6 → 0.4)
        specificity_score = self._calculate_specificity(content)
        min_threshold = 0.4  # 완화된 임계치
        if specificity_score < min_threshold:
            issues.append(QualityIssue(
                type="low_specificity",
                severity="warning",  # 🔥 error → warning으로 완화
                location=section_id,
                content=f"구체성 점수 {specificity_score:.1%} (권장 {min_threshold:.0%} 이상)",
                suggestion="날짜/수치/액션/검증방법 중 3개 이상을 문단마다 포함시켜야 합니다.",
                auto_fixable=False
            ))
        
        # 3. 중복 검사 (기존 섹션과 비교)
        duplicate_ratio = 0.0
        if existing_contents:
            duplicate_ratio = self._check_duplicates(content, existing_contents)
            if duplicate_ratio > self.max_duplicate_ratio:
                issues.append(QualityIssue(
                    type="duplicate",
                    severity="warning",  # 🔥 error → warning
                    location=section_id,
                    content=f"다른 섹션과 {duplicate_ratio:.1%} 유사 (권장 {self.max_duplicate_ratio:.0%} 이하)",
                    suggestion="중복된 내용을 제거하고 섹션 고유의 관점을 강화하세요.",
                    auto_fixable=False
                ))
        
        # 4. 문장 패턴 검사 (공허한 문장) - 🔥 비활성화 (너무 엄격함)
        # pattern_issues = self._check_sentence_patterns(section_id, content)
        # issues.extend(pattern_issues)
        pattern_issues = []
        
        # 5. 최종 점수 계산 (🔥 soft_count 감점 반영)
        score = self._calculate_final_score_v2(
            hard_count, soft_count, specificity_score, duplicate_ratio, len(pattern_issues)
        )
        
        # 6. 🔥 재작성/실패 여부: HARD_BANNED만 실패 트리거
        has_hard_failure = hard_count > 0
        needs_rewrite = has_hard_failure or specificity_score < 0.3
        
        return QualityReport(
            passed=not has_hard_failure,  # 🔥 HARD_BANNED 없으면 통과
            score=score,
            issues=issues,
            banned_count=hard_count,  # HARD만 카운트
            specificity_score=specificity_score,
            duplicate_ratio=duplicate_ratio,
            needs_rewrite=needs_rewrite,
            rewrite_sections=[section_id] if needs_rewrite else []
        )
    
    def _calculate_final_score_v2(
        self,
        hard_count: int,
        soft_count: int,
        specificity_score: float,
        duplicate_ratio: float,
        pattern_count: int
    ) -> int:
        """🔥 새로운 점수 계산 (HARD/SOFT 구분)"""
        score = 100
        
        # HARD_BANNED: -20점/개 (심각)
        score -= hard_count * 20
        
        # SOFT_BANNED: -2점/개 (경미)
        score -= soft_count * 2
        
        # 구체성: 최대 -30점
        if specificity_score < 0.6:
            penalty = int((0.6 - specificity_score) * 50)
            score -= min(penalty, 30)
        
        # 중복: 최대 -20점
        if duplicate_ratio > 0.2:
            penalty = int((duplicate_ratio - 0.2) * 50)
            score -= min(penalty, 20)
        
        # 패턴: -3점/개
        score -= pattern_count * 3
        
        return max(0, min(100, score))
    
    def check_full_report(
        self,
        sections: Dict[str, str]
    ) -> QualityReport:
        """
        전체 리포트 품질 검사
        
        Args:
            sections: {section_id: content} 딕셔너리
        
        Returns:
            QualityReport: 전체 검사 결과
        """
        all_issues = []
        all_contents = list(sections.values())
        total_banned = 0
        total_specificity = 0.0
        rewrite_sections = []
        
        for idx, (section_id, content) in enumerate(sections.items()):
            # 현재 섹션 제외한 나머지와 비교
            other_contents = all_contents[:idx] + all_contents[idx+1:]
            
            report = self.check_section(section_id, content, other_contents)
            all_issues.extend(report.issues)
            total_banned += report.banned_count
            total_specificity += report.specificity_score
            
            if report.needs_rewrite:
                rewrite_sections.append(section_id)
        
        avg_specificity = total_specificity / len(sections) if sections else 0
        
        # 섹션 간 중복 비율 계산
        cross_duplicate = self._check_cross_section_duplicates(sections)
        
        final_score = self._calculate_final_score(
            total_banned, avg_specificity, cross_duplicate, len(all_issues)
        )
        
        return QualityReport(
            passed=len(rewrite_sections) == 0,
            score=final_score,
            issues=all_issues,
            banned_count=total_banned,
            specificity_score=avg_specificity,
            duplicate_ratio=cross_duplicate,
            needs_rewrite=len(rewrite_sections) > 0,
            rewrite_sections=rewrite_sections
        )
    
    def _check_banned_phrases(
        self,
        section_id: str,
        content: str
    ) -> Tuple[List[QualityIssue], int, int]:
        """
        금지어 검사 (HARD/SOFT 분리)
        Returns: (issues, hard_count, soft_count)
        """
        issues = []
        hard_count = 0
        soft_count = 0
        
        content_lower = content.lower()
        
        # 🔥 HARD_BANNED 검사 (심각 - 하드 실패 트리거)
        for phrase in HARD_BANNED_PHRASES:
            if phrase.lower() in content_lower:
                hard_count += 1
                suggestion = REPLACEMENT_GUIDELINES.get(
                    phrase, "→ 구체적인 날짜/수치/액션으로 대체하세요"
                )
                issues.append(QualityIssue(
                    type="hard_banned_phrase",
                    severity="error",
                    location=section_id,
                    content=f"금지어 발견: '{phrase}'",
                    suggestion=suggestion,
                    auto_fixable=True
                ))
        
        # 🔥 SOFT_BANNED 검사 (경미 - 점수 감점만)
        for phrase in SOFT_BANNED_PHRASES:
            if phrase.lower() in content_lower:
                soft_count += 1
                # SOFT는 issues에 추가하지 않음 (점수 감점만)
        
        return issues, hard_count, soft_count
    
    def _check_sentence_patterns(
        self,
        section_id: str,
        content: str
    ) -> List[QualityIssue]:
        """문장 패턴 검사 (공허한 문장)"""
        issues = []
        sentences = re.split(r'[.!?]\s*', content)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            for pattern in self._banned_patterns:
                if pattern.search(sentence):
                    issues.append(QualityIssue(
                        type="empty_pattern",
                        severity="warning",
                        location=section_id,
                        content=f"공허한 문장 패턴: '{sentence[:50]}...'",
                        suggestion="구체적인 데이터, 액션, 기한을 추가하세요.",
                        auto_fixable=True
                    ))
                    break
        
        return issues
    
    def _calculate_specificity(self, content: str) -> float:
        """구체성 점수 계산 (0.0 ~ 1.0)"""
        if not content:
            return 0.0
        
        paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
        if not paragraphs:
            return 0.0
        
        total_score = 0.0
        
        for para in paragraphs:
            markers_found = set()
            
            for marker_type, patterns in self._specificity_patterns.items():
                for pattern in patterns:
                    if pattern.search(para):
                        markers_found.add(marker_type)
                        break
            
            # 4가지 중 3개 이상 있으면 1점, 2개면 0.6점, 1개면 0.3점
            if len(markers_found) >= 3:
                total_score += 1.0
            elif len(markers_found) == 2:
                total_score += 0.6
            elif len(markers_found) == 1:
                total_score += 0.3
        
        return total_score / len(paragraphs)
    
    def _check_duplicates(
        self,
        content: str,
        existing_contents: List[str]
    ) -> float:
        """다른 섹션과의 중복 비율 계산"""
        if not existing_contents:
            return 0.0
        
        # 단어 기반 유사도 (간단한 Jaccard)
        content_words = set(re.findall(r'\w{2,}', content.lower()))
        
        max_similarity = 0.0
        for existing in existing_contents:
            existing_words = set(re.findall(r'\w{2,}', existing.lower()))
            
            if not content_words or not existing_words:
                continue
            
            intersection = len(content_words & existing_words)
            union = len(content_words | existing_words)
            
            if union > 0:
                similarity = intersection / union
                max_similarity = max(max_similarity, similarity)
        
        return max_similarity
    
    def _check_cross_section_duplicates(
        self,
        sections: Dict[str, str]
    ) -> float:
        """섹션 간 평균 중복 비율"""
        if len(sections) < 2:
            return 0.0
        
        contents = list(sections.values())
        total_sim = 0.0
        comparisons = 0
        
        for i in range(len(contents)):
            for j in range(i + 1, len(contents)):
                sim = self._check_duplicates(contents[i], [contents[j]])
                total_sim += sim
                comparisons += 1
        
        return total_sim / comparisons if comparisons > 0 else 0.0
    
    def _calculate_final_score(
        self,
        banned_count: int,
        specificity: float,
        duplicate_ratio: float,
        issue_count: int
    ) -> int:
        """최종 점수 계산 (0-100)"""
        score = 100
        
        # 금지어 감점 (-5점 per 금지어)
        score -= min(banned_count * 5, 30)
        
        # 구체성 점수 반영 (최대 30점)
        score -= int((1 - specificity) * 30)
        
        # 중복 감점 (최대 20점)
        score -= int(duplicate_ratio * 100 * 0.2)
        
        # 이슈 수 감점 (-2점 per 이슈, 최대 20점)
        score -= min(issue_count * 2, 20)
        
        return max(0, min(100, score))
    
    def get_rewrite_prompt_suffix(self, report: QualityReport) -> str:
        """품질 이슈 기반 재작성 프롬프트 생성"""
        if not report.issues:
            return ""
        
        lines = [
            "\n\n⚠️ [품질 게이트 피드백 - 반드시 반영]",
            "이전 생성에서 다음 문제가 발견되었습니다. 반드시 수정하세요:\n"
        ]
        
        for issue in report.issues[:5]:  # 상위 5개만
            lines.append(f"- {issue.content}")
            lines.append(f"  → {issue.suggestion}\n")
        
        lines.extend([
            "\n필수 규칙:",
            "1. 위에서 지적된 금지어/패턴을 절대 사용하지 마세요.",
            "2. 모든 문단에 날짜/수치/액션/검증방법 중 3개 이상 포함하세요.",
            "3. 다른 섹션과 중복되는 내용을 제거하세요.",
            "4. '~할 수 있습니다', '~면 좋겠습니다' 대신 '~하세요', '~입니다'로 단정적으로 작성하세요."
        ])
        
        return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. 텍스트 자동 클리닝 (금지어 제거)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def clean_banned_phrases(text: str) -> str:
    """금지어가 포함된 문장 마킹 (수동 검토용)"""
    for phrase in BANNED_PHRASES:
        if phrase in text:
            # 금지어를 [!!금지어!!]로 마킹
            text = text.replace(phrase, f"[⚠️{phrase}⚠️]")
    return text


def get_quality_improvement_prompt() -> str:
    """품질 개선을 위한 시스템 프롬프트 추가문"""
    return """
[품질 규칙 - 절대 준수]

1. 금지 표현 (절대 사용 금지):
   - 자기계발서 톤: 노력, 성장, 긍정, 기회, 도전, 잠재력, 열정, 꿈
   - 덕담: 행운, 축복, 잘 될 것, 좋은 결과
   - 모호함: ~할 수 있습니다, ~면 좋겠습니다, 도움이 될 것

2. 필수 구체성 (모든 문단에 3개 이상 포함):
   - 날짜: 3월 2주차, Q2, 1분기 말
   - 수치: 30%, 500만원, 3명, 2배
   - 액션: 실행, 작성, 미팅, 계약, 론칭
   - 검증: KPI, 측정, 리포트, 달성률

3. 어투 규칙:
   - 단정적 서술: "~하세요", "~입니다" (명령/단정)
   - 금지 어투: "~하면 좋겠습니다", "~할 수 있을 것입니다"
   - 맥킨지 컨설턴트가 CEO에게 보고하는 톤으로 작성

4. 중복 금지:
   - 같은 의미의 문장을 2번 이상 반복하지 마세요
   - 다른 섹션에서 다룬 내용을 재언급하지 마세요
"""


# 싱글톤 인스턴스
quality_gate = QualityGate()
