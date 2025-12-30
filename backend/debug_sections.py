# -*- coding: utf-8 -*-
"""
P0 DEBUG: report_sections 저장 상태 확인
"""
import os
import sys
from dotenv import load_dotenv

# .env 로드
load_dotenv()

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

print("=" * 60)
print("[DEBUG] Supabase Connection Info")
print("=" * 60)
print(f"URL: {SUPABASE_URL[:50]}..." if SUPABASE_URL else "URL: NOT SET")
print(f"KEY: {SUPABASE_KEY[:20]}..." if SUPABASE_KEY else "KEY: NOT SET")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("[ERROR] Supabase env vars missing!")
    sys.exit(1)

client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 1. 최근 jobs 조회
print("\n" + "=" * 60)
print("[1] Recent 10 report_jobs")
print("=" * 60)

jobs = client.table("report_jobs").select("id, status, progress, current_step, created_at").order("created_at", desc=True).limit(10).execute()

if jobs.data:
    for job in jobs.data:
        print(f"  job_id: {job['id']}")
        print(f"  status: {job['status']} | progress: {job['progress']}% | step: {job.get('current_step', 'N/A')}")
        print(f"  created_at: {job['created_at']}")
        print("-" * 40)
else:
    print("  [ERROR] No jobs found!")

# 2. 특정 job_id로 sections 조회 (가장 최근 job)
if jobs.data:
    latest_job_id = jobs.data[0]['id']
    print("\n" + "=" * 60)
    print(f"[2] report_sections for job_id: {latest_job_id}")
    print("=" * 60)
    
    sections = client.table("report_sections").select("*").eq("job_id", latest_job_id).execute()
    
    if sections.data:
        print(f"  [OK] Total {len(sections.data)} sections saved")
        for sec in sections.data:
            sid = sec.get('section_id', 'N/A')
            body = sec.get('body_markdown', '')
            content = sec.get('content', '')
            markdown = sec.get('markdown', '')
            char_count = sec.get('char_count', 0)
            
            print(f"\n  [SECTION] section_id: {sid}")
            print(f"     body_markdown: {len(body) if body else 0} chars")
            print(f"     content: {len(content) if content else 0} chars")
            print(f"     markdown: {len(markdown) if markdown else 0} chars")
            print(f"     char_count (DB): {char_count}")
            print(f"     status: {sec.get('status', 'N/A')}")
            
            # 첫 100자 미리보기
            preview = (body or content or markdown or "")[:100]
            if preview:
                # ASCII로 변환하여 출력
                safe_preview = preview.encode('ascii', 'replace').decode('ascii')
                print(f"     preview: {safe_preview}...")
            else:
                print(f"     [WARN] Body is EMPTY!")
    else:
        print(f"  [ERROR] No sections for job_id={latest_job_id}")
        
        # 전체 sections 확인
        print("\n  [DEBUG] Checking all report_sections...")
        all_sections = client.table("report_sections").select("job_id, section_id, char_count").limit(20).execute()
        if all_sections.data:
            print(f"  Total sections in table: {len(all_sections.data)}")
            for s in all_sections.data[:5]:
                print(f"    - job_id: {s['job_id'][:20]}... | section: {s['section_id']} | chars: {s.get('char_count', 0)}")
        else:
            print("  [ERROR] report_sections table is EMPTY!")

# 3. 섹션 ID 분포 확인
print("\n" + "=" * 60)
print("[3] section_id distribution (last 50)")
print("=" * 60)

recent_sections = client.table("report_sections").select("section_id").order("created_at", desc=True).limit(50).execute()
if recent_sections.data:
    from collections import Counter
    sid_counts = Counter(s['section_id'] for s in recent_sections.data)
    for sid, count in sid_counts.most_common():
        print(f"  {sid}: {count}")
else:
    print("  [ERROR] No sections!")

print("\n" + "=" * 60)
print("[DONE] Debug complete")
print("=" * 60)
