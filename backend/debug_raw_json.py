# -*- coding: utf-8 -*-
"""
P0 DEBUG: raw_json vs body_markdown comparison
"""
import os
import sys
import json
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("=" * 60)
print("[DEBUG] Checking raw_json vs body_markdown")
print("=" * 60)

# Get latest job
jobs = client.table("report_jobs").select("id").order("created_at", desc=True).limit(1).execute()
if not jobs.data:
    print("[ERROR] No jobs found!")
    sys.exit(1)

job_id = jobs.data[0]['id']
print(f"Job ID: {job_id}")

# Get sections for this job
sections = client.table("report_sections").select("section_id, body_markdown, raw_json, char_count, status").eq("job_id", job_id).execute()

if not sections.data:
    print("[ERROR] No sections found!")
    sys.exit(1)

print(f"\nTotal sections: {len(sections.data)}")
print("-" * 60)

for sec in sections.data:
    sid = sec.get('section_id', 'N/A')
    body = sec.get('body_markdown', '')
    raw = sec.get('raw_json', {})
    char_count = sec.get('char_count', 0)
    status = sec.get('status', 'N/A')
    
    print(f"\n[SECTION] {sid}")
    print(f"  status: {status}")
    print(f"  body_markdown: {len(body) if body else 0} chars")
    print(f"  char_count (DB): {char_count}")
    
    if raw:
        raw_body = raw.get('body_markdown', '')
        raw_content = raw.get('content', '')
        raw_markdown = raw.get('markdown', '')
        print(f"  raw_json.body_markdown: {len(raw_body) if raw_body else 0} chars")
        print(f"  raw_json.content: {len(raw_content) if raw_content else 0} chars")
        print(f"  raw_json.markdown: {len(raw_markdown) if raw_markdown else 0} chars")
        
        # Preview
        preview_text = raw_body or raw_content or raw_markdown or ""
        if preview_text:
            safe_preview = preview_text[:150].encode('ascii', 'replace').decode('ascii')
            print(f"  raw preview: {safe_preview}...")
        else:
            print("  [CRITICAL] raw_json also has EMPTY body!")
    else:
        print("  [WARN] raw_json is NULL/empty")

print("\n" + "=" * 60)
print("[DONE]")
