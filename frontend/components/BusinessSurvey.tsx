'use client';

import { useState } from 'react';

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 🔥 P0 Pivot: 1인 사업가용 핵심 5개 필드로 간소화
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const REVENUE_RANGES = [
  { value: '0', label: '매출 없음' },
  { value: 'under_500', label: '500만원 미만' },
  { value: '500_1000', label: '500~1000만원' },
  { value: '1000_3000', label: '1000~3000만원' },
  { value: '3000_5000', label: '3000~5000만원' },
  { value: '5000_1b', label: '5000만원~1억' },
  { value: 'over_1b', label: '1억 이상' },
];

const BOTTLENECKS = [
  { value: 'lead', label: '🎯 고객 확보', desc: '잠재 고객이 부족' },
  { value: 'conversion', label: '💰 전환율', desc: '관심→구매 전환이 낮음' },
  { value: 'operations', label: '⚙️ 운영/시스템', desc: '업무 효율이 낮음' },
  { value: 'funding', label: '💸 자금', desc: '돈이 부족' },
  { value: 'mental', label: '🧠 번아웃', desc: '체력/의욕 저하' },
  { value: 'direction', label: '🧭 방향성', desc: '무엇을 해야 할지 모르겠음' },
];

const TIME_OPTIONS = [
  { value: 'under_10', label: '10시간 미만 (부업)' },
  { value: '10_30', label: '10~30시간 (파트타임)' },
  { value: '30_50', label: '30~50시간 (풀타임)' },
  { value: 'over_50', label: '50시간+ (올인)' },
];

// 🔥 P0: 핵심 5개 필드만 사용
export interface SurveyData {
  industry: string;          // 업종
  revenue: string;           // 월매출 (monthly_revenue)
  painPoint: string;         // 병목 (primary_bottleneck)
  goal: string;              // 목표 (goal_detail)
  time: string;              // 투입시간 (time_availability)
}

interface SurveyFormProps {
  onComplete: (data: SurveyData) => void;
  onSkip?: () => void;
}

export default function SurveyForm({ onComplete, onSkip }: SurveyFormProps) {
  const [formData, setFormData] = useState<SurveyData>({
    industry: '',
    revenue: 'under_1000',
    painPoint: 'lead',
    goal: '',
    time: '30_50',
  });

  const updateField = (field: keyof SurveyData, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onComplete(formData);
  };

  const isValid = () => {
    return formData.industry.length >= 2 && formData.goal.length >= 5;
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-lg p-6 md:p-8 animate-fade-in-up">
      {/* 헤더 */}
      <div className="mb-6">
        <h2 className="text-xl font-bold text-gray-800 flex items-center gap-2 mb-2">
          <span>📋</span> 비즈니스 현황 (60초)
        </h2>
        <p className="text-sm text-gray-500">
          이 정보로 <strong>당신 상황에 맞는 전략</strong>을 제공합니다.
        </p>
      </div>

      {/* 1. 업종 */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          업종/사업 분야 <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          value={formData.industry}
          onChange={e => updateField('industry', e.target.value)}
          placeholder="예: IT/SaaS, 온라인 커머스, 교육, 컨설팅..."
          className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
        />
      </div>

      {/* 2. 월매출 */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          현재 월매출
        </label>
        <select
          value={formData.revenue}
          onChange={e => updateField('revenue', e.target.value)}
          className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500"
        >
          {REVENUE_RANGES.map(option => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {/* 3. 병목 */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          지금 가장 큰 병목은?
        </label>
        <div className="grid grid-cols-2 gap-2">
          {BOTTLENECKS.map(option => (
            <button
              key={option.value}
              type="button"
              onClick={() => updateField('painPoint', option.value)}
              className={`p-3 rounded-lg border-2 text-left transition ${
                formData.painPoint === option.value
                  ? 'border-purple-500 bg-purple-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="font-medium text-sm">{option.label}</div>
              <div className="text-xs text-gray-500 mt-1">{option.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* 4. 목표 */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          2026년 가장 중요한 목표 1개 <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          value={formData.goal}
          onChange={e => updateField('goal', e.target.value)}
          placeholder="예: 월매출 5000만원, 시스템 자동화, 브랜드 인지도 확보..."
          className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500"
        />
      </div>

      {/* 5. 투입시간 */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          주당 투입 가능 시간
        </label>
        <div className="grid grid-cols-2 gap-2">
          {TIME_OPTIONS.map(option => (
            <button
              key={option.value}
              type="button"
              onClick={() => updateField('time', option.value)}
              className={`p-3 rounded-lg border-2 text-sm transition ${
                formData.time === option.value
                  ? 'border-purple-500 bg-purple-50 text-purple-700'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {/* 버튼 */}
      <div className="flex items-center justify-between">
        {onSkip && (
          <button
            type="button"
            onClick={onSkip}
            className="px-4 py-2 text-gray-500 hover:text-gray-700 text-sm"
          >
            건너뛰기
          </button>
        )}

        <button
          type="submit"
          disabled={!isValid()}
          className={`ml-auto px-6 py-3 rounded-lg font-medium transition ${
            isValid()
              ? 'bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 text-white'
              : 'bg-gray-200 text-gray-400 cursor-not-allowed'
          }`}
        >
          리포트 생성 시작 →
        </button>
      </div>

      {/* 안내 */}
      <div className="mt-4 p-3 bg-blue-50 rounded-lg">
        <p className="text-xs text-blue-700">
          💡 이 정보는 리포트 생성에만 사용되며, 외부에 공유되지 않습니다.
        </p>
      </div>
    </form>
  );
}
