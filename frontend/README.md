# 🔮 AI 사주 프론트엔드

Next.js 14 기반 사주 서비스 프론트엔드입니다.

## 🚀 빠른 시작

### 1. 의존성 설치

```bash
cd frontend
npm install
```

### 2. 환경 변수 설정

```bash
# .env.local 파일 생성
copy .env.local.example .env.local  # Windows
# cp .env.local.example .env.local  # Linux/Mac

# 기본값: NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. 개발 서버 실행

```bash
npm run dev
```

http://localhost:3000 에서 확인

### 4. 프로덕션 빌드

```bash
npm run build
npm start
```

## 📁 프로젝트 구조

```
frontend/
├── app/
│   ├── layout.tsx        # 루트 레이아웃
│   ├── page.tsx          # 메인 페이지
│   └── globals.css       # 전역 스타일
├── components/
│   ├── SajuForm.tsx      # 입력 폼
│   └── ResultCard.tsx    # 결과 카드
├── lib/
│   └── api.ts            # API 통신 함수
├── types/
│   └── index.ts          # TypeScript 타입
├── tailwind.config.js
├── next.config.js
└── package.json
```

## 🎨 주요 기능

1. **입력 폼**
   - 생년월일 선택
   - 출생 시간 (선택)
   - 성별 선택
   - 고민 유형 선택
   - 질문 입력

2. **결과 카드**
   - 사주 원국 시각화 (4기둥)
   - 탭 UI (요약/상세분석/행동지침)
   - 공유 기능
   - 면책조항 표시

## 🔧 기술 스택

- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- Lucide React Icons

## 📱 반응형 디자인

모바일, 태블릿, 데스크톱 모두 지원합니다.

## ⚠️ 주의사항

백엔드 서버(`http://localhost:8000`)가 실행 중이어야 합니다.
