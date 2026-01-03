"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import ReactMarkdown from "react-markdown";

// 🔥 P0: API URL 단일화
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://api.sajuos.com";

// 🔥🔥🔥 P0 FIX: target_year 기본값 고정 (2026 시즌)
const DEFAULT_TARGET_YEAR = 2026;

// 🔥🔥🔥 P0 FIX: SECTION_SPECS 단일 소스 (ID/라벨 분리 금지!)
const SECTION_SPECS = [
  { id: "exec",     title: "전략 기상도",     icon: "🌦️", tabName: "전략",     order: 1 },
  { id: "money",    title: "현금흐름 최적화", icon: "💰", tabName: "현금흐름", order: 2 },
  { id: "business", title: "비즈니스 전략",   icon: "📍", tabName: "시장전략", order: 3 },
  { id: "team",     title: "파트너십/팀",     icon: "🤝", tabName: "파트너십", order: 4 },
  { id: "health",   title: "오너 리스크",     icon: "🧯", tabName: "리스크",   order: 5 },
  { id: "calendar", title: "12개월 캘린더",   icon: "🗓️", tabName: "12개월",   order: 6 },
  { id: "sprint",   title: "90일 액션플랜",   icon: "🚀", tabName: "90일플랜", order: 7 },
].sort((a, b) => a.order - b.order);

// 🔥 P0: 헬퍼 함수들
const getSpec = (id: string) => SECTION_SPECS.find(s => s.id === id);
const getSectionId = (s: any): string => s?.section_id ?? s?.sectionId ?? s?.id ?? "";

// 🔥 P0: 안전한 includes 헬퍼
const safeIncludes = (arr: unknown, value: string): boolean => {
  return Array.isArray(arr) && arr.includes(value);
};

// 🔥🔥🔥 P0 FIX: 정확도 계산 함수 (단순 hasBirthTime → 복합 조건)
function calculateAccuracy(data: any): { level: "high" | "medium" | "low"; reason: string } {
  if (!data) return { level: "low", reason: "데이터 없음" };
  
  const saju = data?.input?.saju_result || {};
  const sajuSummary = saju?.saju_summary || {};
  const surveyData = data?.input?.survey_data || {};
  const sections = Array.isArray(data?.sections) ? data.sections : [];
  
  // 조건 체크
  const hasBirthTime = !!(saju?.saju?.hour_pillar || saju?.quality?.has_birth_time);
  const hasSajuSummary = !!(sajuSummary?.ten_gods_present?.length > 0 || sajuSummary?.elements_count);
  const hasSurveyData = !!(surveyData?.industry || surveyData?.painPoint || surveyData?.goal);
  const hasEnoughSections = sections.filter((s: any) => {
    const content = s?.markdown || s?.body_markdown || "";
    return content.length > 200;
  }).length >= 3;
  
  // 🔥 P0: 섹션 내용에 "정보 부족", "추가 정보" 등 거절 패턴 있는지 체크
  const hasRejectionContent = sections.some((s: any) => {
    const content = s?.markdown || s?.body_markdown || "";
    return content.includes("정보가 부족") || 
           content.includes("추가 정보") || 
           content.includes("작성할 수 없") ||
           content.includes("죄송");
  });
  
  // 높음: 출생시간 + saju_summary + survey + 충분한 섹션 + 거절 패턴 없음
  if (hasBirthTime && hasSajuSummary && hasSurveyData && hasEnoughSections && !hasRejectionContent) {
    return { level: "high", reason: "모든 데이터 확보" };
  }
  
  // 낮음: 거절 패턴 있거나 섹션 부족
  if (hasRejectionContent || !hasEnoughSections) {
    return { level: "low", reason: hasRejectionContent ? "콘텐츠 생성 오류" : "섹션 부족" };
  }
  
  // 보통: 나머지
  const missingParts = [];
  if (!hasBirthTime) missingParts.push("출생시간");
  if (!hasSurveyData) missingParts.push("설문");
  
  return { 
    level: "medium", 
    reason: missingParts.length > 0 ? `${missingParts.join(", ")} 미입력` : "일부 데이터 부족"
  };
}

interface ReportClientProps {
  jobId: string;
  token: string;
}

export default function ReportClient({ jobId, token }: ReportClientProps) {
  const searchParams = useSearchParams();
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string>("");
  const [status, setStatus] = useState<"loading" | "generating" | "completed" | "error">("loading");
  const [progress, setProgress] = useState(0);
  // 🔥 P0 FIX: 백엔드 섹션 ID와 일치 (exec)
  const [activeSection, setActiveSection] = useState<string>("exec");
  
  // 🔥 P0: 전체보기 모드
  const [viewMode, setViewMode] = useState<"tabs" | "full">("tabs");

  const BRAND_NAME = process.env.NEXT_PUBLIC_BRAND_NAME ?? "사주OS";

  // 🔥 URL에서 view=full 파라미터 확인
  useEffect(() => {
    const viewParam = searchParams.get("view");
    if (viewParam === "full") {
      setViewMode("full");
    }
  }, [searchParams]);

  // 🔥 P0: 토큰 검증 + 데이터 로딩
  useEffect(() => {
    if (!jobId || typeof jobId !== "string" || jobId.length < 10) {
      setError("유효하지 않은 리포트 ID입니다.");
      setStatus("error");
      return;
    }
    
    if (!token || typeof token !== "string" || token.length < 10) {
      setError("유효하지 않은 토큰입니다.");
      setStatus("error");
      return;
    }

    let pollingInterval: NodeJS.Timeout | null = null;
    let isMounted = true;

    const fetchView = async () => {
      try {
        const url = `${API_BASE}/api/v1/reports/view/${jobId}?token=${encodeURIComponent(token)}`;
        console.log("[ReportView] Fetching:", url);
        
        const res = await fetch(url, { cache: "no-store" });

        if (!res.ok) {
          const txt = await res.text();
          throw new Error(`view failed ${res.status}: ${txt.slice(0, 300)}`);
        }

        const json = await res.json();
        
        console.log("[ReportView] Response:", {
          jobStatus: json?.job?.status,
          sectionCount: json?.sections?.length,
          fullMarkdownLength: json?.full_markdown?.length,
        });
        
        if (!isMounted) return;
        
        setData(json);

        const jobStatus = json?.job?.status || "unknown";
        const jobProgress = json?.job?.progress || 0;

        if (jobStatus === "completed") {
          setProgress(100);
          setStatus("completed");
          if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
          }
        } else if (jobStatus === "failed") {
          setError(json?.job?.error || "리포트 생성에 실패했습니다");
          setStatus("error");
          if (pollingInterval) clearInterval(pollingInterval);
        } else if (safeIncludes(["running", "queued", "pending"], jobStatus)) {
          setProgress(jobProgress);
          setStatus("generating");
          startPolling();
        } else {
          setProgress(jobProgress);
          setStatus("generating");
          startPolling();
        }
      } catch (e: any) {
        if (!isMounted) return;
        console.error("[ReportView] Error:", e);
        setError(e?.message || "알 수 없는 오류가 발생했습니다");
        setStatus("error");
      }
    };

    const startPolling = () => {
      if (pollingInterval) return;
      
      pollingInterval = setInterval(async () => {
        try {
          const url = `${API_BASE}/api/v1/reports/view/${jobId}?token=${encodeURIComponent(token)}`;
          const res = await fetch(url, { cache: "no-store" });
          
          if (!res.ok) return;
          
          const json = await res.json();
          if (!isMounted) return;
          
          setData(json);
          
          const jobStatus = json?.job?.status || "unknown";
          const jobProgress = json?.job?.progress || 0;
          
          if (jobStatus === "completed") {
            if (pollingInterval) clearInterval(pollingInterval);
            pollingInterval = null;
            setProgress(100);
            setStatus("completed");
          } else if (jobStatus === "failed") {
            if (pollingInterval) clearInterval(pollingInterval);
            setError(json?.job?.error || "리포트 생성에 실패했습니다");
            setStatus("error");
          } else {
            setProgress(jobProgress);
          }
        } catch (e) {
          console.warn("[ReportView] Polling error:", e);
        }
      }, 3000);
    };

    fetchView();

    return () => {
      isMounted = false;
      if (pollingInterval) clearInterval(pollingInterval);
    };
  }, [jobId, token]);

  // 🔥🔥🔥 P0: PDF 저장 함수
  const handlePrintPDF = () => {
    window.print();
  };

  // 🔥🔥🔥 P0: 전체보기 토글
  const toggleViewMode = () => {
    setViewMode(viewMode === "tabs" ? "full" : "tabs");
  };

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // 에러 화면
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  if (status === "error") {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-purple-50 py-8">
        <div className="container mx-auto px-4 max-w-4xl">
          <Header brandName={BRAND_NAME} />
          
          <div className="bg-red-50 border border-red-200 rounded-2xl p-8 text-center">
            <div className="text-5xl mb-4">⚠️</div>
            <h2 className="text-xl font-bold text-red-700 mb-4">오류가 발생했습니다</h2>
            <pre className="text-left bg-white p-4 rounded-lg text-sm text-red-600 overflow-auto max-h-40 mb-6 whitespace-pre-wrap">
              {error}
            </pre>
            
            <div className="space-x-4">
              <button
                onClick={() => window.location.reload()}
                className="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition"
              >
                다시 시도
              </button>
              <button
                onClick={() => window.location.href = "/"}
                className="px-6 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition"
              >
                홈으로
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // 로딩 화면
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  if (status === "loading") {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-purple-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mb-6 mx-auto" />
          <p className="text-slate-600 text-lg">리포트 불러오는 중...</p>
        </div>
      </div>
    );
  }

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // 생성 중 화면
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  if (status === "generating") {
    const sections = Array.isArray(data?.sections) ? data.sections : [];
    
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-purple-50 py-8">
        <div className="container mx-auto px-4 max-w-4xl">
          <Header brandName={BRAND_NAME} />

          <div className="bg-white rounded-2xl shadow-lg p-8">
            <div className="text-center mb-6">
              <div className="text-5xl mb-4">⏳</div>
              <h2 className="text-xl font-bold text-gray-800">보고서 생성 중입니다</h2>
              <p className="text-gray-600 mt-2">잠시만 기다려주세요. 완료되면 자동으로 표시됩니다.</p>
            </div>

            <div className="max-w-md mx-auto mb-8">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-600">진행률</span>
                <span className="text-sm font-bold text-purple-600">{progress}%</span>
              </div>
              <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-purple-600 to-amber-500 rounded-full transition-all duration-500"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>

            {sections.length > 0 && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {SECTION_SPECS.map((spec) => {
                  // 🔥 P0 FIX: SECTION_SPECS 단일 소스 사용
                  const section = sections.find((s: any) => getSectionId(s) === spec.id);
                  const sectionStatus = section?.status || "pending";
                  return (
                    <div
                      key={spec.id}
                      className={`px-3 py-2 rounded-lg text-xs font-medium text-center ${
                        sectionStatus === "completed"
                          ? "bg-green-100 text-green-700"
                          : sectionStatus === "running"
                          ? "bg-yellow-100 text-yellow-700 animate-pulse"
                          : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {spec.icon} {spec.tabName}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // 🔥🔥🔥 완료 화면 (핵심!)
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  if (status === "completed" && data) {
    const { job, input, sections, full_markdown } = data;
    const saju = input?.saju_result || {};
    
    // 🔥🔥🔥 P0 FIX: target_year 단일 소스 (+1 제거, 2026 고정)
    const targetYear = 
      job?.target_year ?? 
      job?.targetYear ?? 
      input?.target_year ?? 
      input?.targetYear ?? 
      DEFAULT_TARGET_YEAR;
    
    // 🔥 P0 FIX: ready 플래그로 빈 본문 노출 방지
    const isReady = data?.ready ?? true;  // 백엔드에서 ready 없으면 기본 true (하위 호환)
    
    const boundary = saju?.quality?.solar_term_boundary ?? null;
    const birthInfo = saju?.birth_info || "";
    const dayMaster = saju?.day_master || "";
    const dayMasterElement = saju?.day_master_element || "";
    const dayMasterDesc = saju?.day_master_description || "";
    const pillars = saju?.saju || {};
    
    const safeSections = Array.isArray(sections) ? sections : [];
    
    // 🔥🔥🔥 P0 FIX: 탭에 표시할 섹션 수 계산 (SECTION_SPECS 사용)
    const matchedTabCount = SECTION_SPECS.filter(spec => 
      safeSections.some(s => getSectionId(s) === spec.id)
    ).length;
    
    // 🔥 P0: 탭이 0개면 자동으로 전체보기 모드로 전환
    const effectiveViewMode = (viewMode === "tabs" && matchedTabCount === 0 && safeSections.length > 0) 
      ? "full" 
      : viewMode;
    
    // 🔥🔥🔥 P0 FIX: 정확도 계산 (복합 조건)
    const accuracy = calculateAccuracy(data);
    
    // 🔥 P0 FIX: ready=false면 생성중 UI 표시
    if (!isReady) {
      return (
        <div className="min-h-screen bg-gradient-to-b from-slate-50 to-purple-50 py-8">
          <div className="container mx-auto px-4 max-w-4xl">
            <Header brandName={BRAND_NAME} targetYear={targetYear} />
            
            <div className="bg-white rounded-2xl shadow-lg p-8">
              <div className="text-center mb-6">
                <div className="text-5xl mb-4">📝</div>
                <h2 className="text-xl font-bold text-gray-800">콘텐츠 준비 중</h2>
                <p className="text-gray-600 mt-2">리포트 생성이 완료되었으나 콘텐츠를 준비 중입니다.</p>
                <p className="text-gray-500 text-sm mt-2">잠시 후 새로고침해주세요.</p>
              </div>
              
              <div className="flex justify-center">
                <button
                  onClick={() => window.location.reload()}
                  className="px-6 py-3 bg-purple-600 text-white rounded-xl font-medium hover:bg-purple-700 transition"
                >
                  🔄 새로고침
                </button>
              </div>
            </div>
            
            <Footer brandName={BRAND_NAME} />
          </div>
        </div>
      );
    }
    
    return (
      <>
        {/* 🔥 P0: Print CSS */}
        <style jsx global>{`
          @media print {
            .no-print { display: none !important; }
            .print-only { display: block !important; }
            body { background: white !important; }
            .container { max-width: 100% !important; padding: 0 !important; }
          }
          .print-only { display: none; }
        `}</style>
        
        <div className="min-h-screen bg-gradient-to-b from-slate-50 to-purple-50 py-8">
          <div className="container mx-auto px-4 max-w-5xl">
            {/* 🔥 P0 FIX: Header에 target_year 전달 */}
            <Header brandName={BRAND_NAME} targetYear={targetYear} />

            {/* 🔥🔥🔥 P0: 액션 버튼 (전체보기 + PDF 저장) */}
            <div className="flex justify-center gap-4 mb-6 no-print">
              <button
                onClick={toggleViewMode}
                className={`px-6 py-3 rounded-xl font-medium transition-all ${
                  effectiveViewMode === "full"
                    ? "bg-purple-600 text-white shadow-lg"
                    : "bg-white text-purple-600 border-2 border-purple-600 hover:bg-purple-50"
                }`}
              >
                {effectiveViewMode === "full" ? "📑 탭 보기" : "📄 전체보기"}
              </button>
              <button
                onClick={handlePrintPDF}
                className="px-6 py-3 bg-amber-500 text-white rounded-xl font-medium hover:bg-amber-600 transition-all shadow-lg"
              >
                🖨️ PDF 저장
              </button>
            </div>

            {/* 🔥🔥🔥 P0 FIX: 정확도 배지 (복합 조건 기반) */}
            <div className="mb-6 no-print">
              <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium ${
                accuracy.level === "high"
                  ? "bg-green-100 text-green-800 border border-green-200"
                  : accuracy.level === "medium"
                  ? "bg-yellow-100 text-yellow-800 border border-yellow-200"
                  : "bg-red-100 text-red-800 border border-red-200"
              }`}>
                {accuracy.level === "high" ? "✅" : accuracy.level === "medium" ? "⚠️" : "❌"} 
                정확도: {accuracy.level === "high" ? "높음" : accuracy.level === "medium" ? "보통" : "낮음"}
                {accuracy.reason && ` (${accuracy.reason})`}
              </div>
            </div>

            {/* 사주 원국 카드 */}
            <div className="bg-gradient-to-r from-purple-600 to-amber-500 text-white rounded-2xl p-6 mb-8 shadow-lg">
              {/* 🔥 P0 FIX: 연도 단일 소스 */}
              <h2 className="text-xl font-bold mb-2">📜 {targetYear}년 사주 원국</h2>
              {birthInfo && <p className="text-purple-100 mb-4">{birthInfo}</p>}
              
              <div className="grid grid-cols-4 gap-3 mb-4">
                {["hour_pillar", "day_pillar", "month_pillar", "year_pillar"].map((key) => {
                  const pillar = pillars[key];
                  const labels: Record<string, string> = { 
                    hour_pillar: "시주(時)", 
                    day_pillar: "일주(日)", 
                    month_pillar: "월주(月)", 
                    year_pillar: "년주(年)" 
                  };
                  
                  // 🔥 P0: pillar가 객체일 때 ganji 추출
                  let ganjiText = "";
                  if (pillar && typeof pillar === "string" && pillar.length >= 2) {
                    ganjiText = pillar;
                  } else if (pillar && typeof pillar === "object" && "ganji" in pillar) {
                    ganjiText = pillar.ganji || "";
                  }
                  
                  return (
                    <div key={key} className="bg-white/20 rounded-xl p-3 text-center backdrop-blur">
                      <div className="text-xs text-purple-100 mb-1">{labels[key]}</div>
                      {ganjiText && ganjiText.length >= 2 ? (
                        <div className="text-2xl font-bold">
                          {ganjiText[0]}<br/>{ganjiText[1]}
                        </div>
                      ) : (
                        <div className="text-lg text-purple-200">-</div>
                      )}
                    </div>
                  );
                })}
              </div>
              
              {dayMaster && (
                <div className="bg-white/10 rounded-lg p-3">
                  <div className="text-sm text-purple-100">당신의 일간</div>
                  <div className="font-bold text-lg">{dayMaster} ({dayMasterElement})</div>
                  {dayMasterDesc && <div className="text-sm text-purple-100 mt-1">{dayMasterDesc}</div>}
                </div>
              )}
            </div>

            {/* 🔥🔥🔥 P0: 탭 모드 vs 전체보기 모드 */}
            {effectiveViewMode === "tabs" && safeSections.length > 0 && (
              <>
                {/* 탭 네비게이션 - SECTION_SPECS 단일 소스 사용 */}
                <div className="flex flex-wrap gap-2 mb-6 bg-white rounded-xl p-2 shadow no-print">
                  {SECTION_SPECS.map((spec) => {
                    // 🔥 P0 FIX: SECTION_SPECS에서 직접 ID/라벨 가져옴
                    const section = safeSections.find((s: any) => getSectionId(s) === spec.id);
                    if (!section) return null;
                    
                    return (
                      <button
                        key={spec.id}
                        onClick={() => setActiveSection(spec.id)}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                          activeSection === spec.id
                            ? "bg-purple-600 text-white shadow"
                            : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                        }`}
                      >
                        {spec.icon} {spec.tabName}
                      </button>
                    );
                  })}
                </div>

                {/* 활성 섹션 콘텐츠 */}
                <div className="bg-white rounded-2xl shadow-lg overflow-hidden">
                  {safeSections.map((section: any) => {
                    // 🔥 P0 FIX: 안전한 section_id 추출
                    const sid = getSectionId(section);
                    if (sid !== activeSection) return null;
                    
                    const spec = getSpec(sid);
                    const markdown = section?.markdown || section?.body_markdown || section?.bodyMarkdown || section?.content || "";
                    const title = spec?.title || section?.title || section?.sectionTitle || sid;
                    
                    return (
                      <div key={sid} className="p-6 md:p-8">
                        {/* 🔥 P0 FIX: 섹션 타이틀 (SECTION_SPECS 단일 소스) */}
                        <h2 className="text-2xl font-bold text-gray-800 mb-6 pb-4 border-b">
                          {spec?.icon || "📄"} {targetYear}년 {title}
                        </h2>
                        
                        {markdown ? (
                          <div className="prose prose-purple max-w-none">
                            <ReactMarkdown>{markdown}</ReactMarkdown>
                          </div>
                        ) : (
                          <div className="text-gray-500 text-center py-8">
                            콘텐츠 준비 중...
                          </div>
                        )}
                        
                        <div className="mt-8 pt-4 border-t flex items-center justify-between text-xs text-gray-400">
                          <span>신뢰도: {section?.confidence || "MEDIUM"}</span>
                          <span>{section?.char_count || (typeof markdown === "string" ? markdown.length : 0)}자</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}

            {/* 🔥🔥🔥 P0: 전체보기 모드 - full_markdown 한 페이지 렌더링 */}
            {effectiveViewMode === "full" && (
              <div className="bg-white rounded-2xl shadow-lg p-6 md:p-8">
                {full_markdown ? (
                  <div className="prose prose-purple max-w-none prose-headings:text-purple-800 prose-h1:text-3xl prose-h2:text-2xl prose-h2:border-b prose-h2:pb-2 prose-h2:mb-4">
                    <ReactMarkdown>{full_markdown}</ReactMarkdown>
                  </div>
                ) : safeSections.length > 0 ? (
                  // full_markdown이 없으면 섹션별 markdown을 합쳐서 렌더
                  <div className="prose prose-purple max-w-none">
                    {safeSections.map((section: any) => {
                      // 🔥 P0 FIX: SECTION_SPECS 단일 소스 사용
                      const sid = getSectionId(section);
                      const spec = getSpec(sid);
                      const markdown = section?.markdown || section?.body_markdown || section?.bodyMarkdown || "";
                      const title = spec?.title || section?.title || section?.sectionTitle || sid;
                      
                      return (
                        <div key={sid} className="mb-8 pb-8 border-b last:border-b-0">
                          <h2 className="text-2xl font-bold text-purple-800 mb-4">
                            {spec?.icon || "📄"} {targetYear}년 {title}
                          </h2>
                          {markdown ? (
                            <ReactMarkdown>{markdown}</ReactMarkdown>
                          ) : (
                            <p className="text-gray-500">콘텐츠 준비 중...</p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    콘텐츠가 없습니다.
                  </div>
                )}
              </div>
            )}

            {/* 섹션이 없는 경우 */}
            {safeSections.length === 0 && !full_markdown && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-2xl p-8 text-center">
                <div className="text-5xl mb-4">📭</div>
                <h2 className="text-xl font-bold text-yellow-800 mb-2">섹션 데이터가 없습니다</h2>
                <p className="text-yellow-700">리포트 생성이 완료되었으나 섹션 데이터를 불러올 수 없습니다.</p>
              </div>
            )}

            {/* 🔥🔥🔥 P0 FIX: 푸터 1개만 (레이아웃/페이지 중복 제거) */}
            <Footer brandName={BRAND_NAME} />
          </div>
        </div>
      </>
    );
  }

  // fallback
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-purple-50 flex items-center justify-center">
      <div className="text-center">
        <p className="text-slate-600">데이터를 불러오는 중...</p>
      </div>
    </div>
  );
}

// 🔥 P0 FIX: 헤더 컴포넌트 (target_year 단일 소스)
function Header({ brandName, targetYear }: { brandName: string; targetYear?: number }) {
  return (
    <header className="text-center py-6">
      <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-600 to-amber-500 bg-clip-text text-transparent">
        🔮 {brandName}
      </h1>
      <p className="text-slate-600 mt-2">
        {targetYear ? `${targetYear}년` : ""} 프리미엄 비즈니스 컨설팅 보고서
      </p>
    </header>
  );
}

// 🔥🔥🔥 P0 FIX: 푸터 컴포넌트 (1개만 렌더)
function Footer({ brandName }: { brandName: string }) {
  return (
    <footer className="text-center py-8 text-sm text-gray-500 no-print">
      <p>⚠️ 본 서비스는 오락/참고 목적으로 제공되며, 의학/법률/투자 등 전문적 조언을 대체하지 않습니다.</p>
      <p className="mt-2">© {new Date().getFullYear()} {brandName}. All rights reserved.</p>
    </footer>
  );
}
