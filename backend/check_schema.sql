-- report_jobs 테이블 스키마 확인
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' 
  AND table_name = 'report_jobs'
ORDER BY ordinal_position;

-- report_sections 테이블 스키마 확인
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' 
  AND table_name = 'report_sections'
ORDER BY ordinal_position;

-- 필요한 컬럼 추가 (없으면 추가)
ALTER TABLE public.report_jobs
ADD COLUMN IF NOT EXISTS input_json jsonb,
ADD COLUMN IF NOT EXISTS saju_json jsonb;

ALTER TABLE public.report_sections
ADD COLUMN IF NOT EXISTS content text,
ADD COLUMN IF NOT EXISTS raw_json jsonb,
ADD COLUMN IF NOT EXISTS char_count int;

-- 확인
SELECT 
    j.id,
    j.user_email,
    j.status,
    j.input_json IS NOT NULL as has_input_json,
    j.saju_json IS NOT NULL as has_saju_json,
    j.result_json IS NOT NULL as has_result_json
FROM report_jobs j
WHERE j.status = 'completed'
ORDER BY j.completed_at DESC
LIMIT 5;
