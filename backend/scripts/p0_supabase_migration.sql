-- =====================================================
-- P0-4: Supabase report_sections 테이블 보강 SQL
-- 실행 방법: Supabase Dashboard > SQL Editor에서 실행
-- =====================================================

-- 1) report_sections: 코드에서 쓰는 필드 보강 (없는 컬럼만 추가)
ALTER TABLE IF EXISTS report_sections
  ADD COLUMN IF NOT EXISTS status text DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS progress int DEFAULT 0,
  ADD COLUMN IF NOT EXISTS title text,
  ADD COLUMN IF NOT EXISTS confidence text,
  ADD COLUMN IF NOT EXISTS error text,
  ADD COLUMN IF NOT EXISTS section_order int,
  ADD COLUMN IF NOT EXISTS raw_json jsonb,
  ADD COLUMN IF NOT EXISTS body_markdown text,
  ADD COLUMN IF NOT EXISTS markdown text,
  ADD COLUMN IF NOT EXISTS content text,
  ADD COLUMN IF NOT EXISTS char_count int;

-- 2) 업서트 안정성: (job_id, section_id) 유니크 보장
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'report_sections_job_section_unique'
  ) THEN
    ALTER TABLE report_sections
      ADD CONSTRAINT report_sections_job_section_unique UNIQUE (job_id, section_id);
  END IF;
END$$;

-- 3) 인덱스 생성 (조회 성능 향상)
CREATE INDEX IF NOT EXISTS idx_report_sections_job_id ON report_sections(job_id);
CREATE INDEX IF NOT EXISTS idx_report_sections_section_id ON report_sections(section_id);
CREATE INDEX IF NOT EXISTS idx_report_sections_status ON report_sections(status);

-- 4) report_jobs 테이블 보강 (필요시)
ALTER TABLE IF EXISTS report_jobs
  ADD COLUMN IF NOT EXISTS input_data jsonb,
  ADD COLUMN IF NOT EXISTS saju_json jsonb,
  ADD COLUMN IF NOT EXISTS final_markdown text,
  ADD COLUMN IF NOT EXISTS progress int DEFAULT 0,
  ADD COLUMN IF NOT EXISTS error text;

-- 5) input_json vs input_data 호환성 확보
-- 기존 input_json 데이터를 input_data로 복사 (한번만 실행)
-- UPDATE report_jobs SET input_data = input_json WHERE input_data IS NULL AND input_json IS NOT NULL;

SELECT 'P0-4 SQL executed successfully' AS result;
