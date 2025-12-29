"""
사주 웹사이트 문제 진단 스크립트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
진단 항목:
1. 년/월/일/시주가 -로 나오는 문제
2. 리포트가 모두 똑같이 나오는 문제
3. supabase report_sections.content가 EMPTY인 문제
"""
import os
import sys
import asyncio
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def diagnose():
    """문제 진단"""
    from supabase import create_client
    
    url = "https://brpxawpbyjjiiwmqkvub.supabase.co"
    key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJycHhhd3BieWpqaWl3bXFrdnViIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NjMxMjQzMCwiZXhwIjoyMDgxODg4NDMwfQ.u_8Q7BKxeoSOxiYzr4_oCL3Jt_MYqt2kaveQwzrWTbw"
    
    supabase = create_client(url, key)
    
    print("=" * 80)
    print("📊 사주 웹사이트 문제 진단")
    print("=" * 80)
    print()
    
    # 최근 완료된 Job 3개 조회
    jobs_result = supabase.table("report_jobs")\
        .select("*")\
        .eq("status", "completed")\
        .order("completed_at", desc=True)\
        .limit(3)\
        .execute()
    
    jobs = jobs_result.data if jobs_result.data else []
    
    if not jobs:
        print("⚠️ 완료된 Job이 없습니다.")
        return
    
    print(f"✅ 최근 완료된 Job {len(jobs)}개 발견")
    print()
    
    for idx, job in enumerate(jobs, 1):
        job_id = job.get("id")
        email = job.get("user_email", "")
        input_json = job.get("input_json") or {}
        result_json = job.get("result_json") or {}
        
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"Job #{idx}: {job_id}")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"이메일: {email}")
        print(f"완료 시간: {job.get('completed_at', 'N/A')}")
        print()
        
        # 1) 사주 데이터 확인
        print("1️⃣ 사주 데이터 확인:")
        print("-" * 60)
        
        saju_result = input_json.get("saju_result") or {}
        saju_summary = result_json.get("saju_summary") or {}
        
        def extract_ganji(pillar_data):
            if not pillar_data:
                return ""
            if isinstance(pillar_data, dict):
                return pillar_data.get("ganji", "")
            if isinstance(pillar_data, str):
                return pillar_data
            return ""
        
        # input_json에서 추출
        year_pillar = extract_ganji(saju_result.get("year_pillar")) or input_json.get("year_pillar", "")
        month_pillar = extract_ganji(saju_result.get("month_pillar")) or input_json.get("month_pillar", "")
        day_pillar = extract_ganji(saju_result.get("day_pillar")) or input_json.get("day_pillar", "")
        hour_pillar = extract_ganji(saju_result.get("hour_pillar")) or input_json.get("hour_pillar", "")
        
        print(f"input_json에서 추출:")
        print(f"  년주: {year_pillar or '❌ EMPTY'}")
        print(f"  월주: {month_pillar or '❌ EMPTY'}")
        print(f"  일주: {day_pillar or '❌ EMPTY'}")
        print(f"  시주: {hour_pillar or '❌ EMPTY (미입력일 수 있음)'}")
        print()
        
        print(f"result_json.saju_summary:")
        print(f"  년주: {saju_summary.get('year_pillar', '❌ EMPTY')}")
        print(f"  월주: {saju_summary.get('month_pillar', '❌ EMPTY')}")
        print(f"  일주: {saju_summary.get('day_pillar', '❌ EMPTY')}")
        print(f"  시주: {saju_summary.get('hour_pillar', '❌ EMPTY')}")
        print()
        
        # 문제 진단
        if not year_pillar or not month_pillar or not day_pillar:
            print("❌ 문제 발견: 년/월/일주가 비어있습니다!")
            print("   원인: input_json.saju_result 구조가 올바르지 않음")
            print()
        else:
            print("✅ 사주 데이터 정상")
            print()
        
        # 2) 섹션 데이터 확인
        print("2️⃣ 섹션 데이터 확인:")
        print("-" * 60)
        
        sections_result = supabase.table("report_sections")\
            .select("*")\
            .eq("job_id", job_id)\
            .execute()
        
        sections = sections_result.data if sections_result.data else []
        
        if not sections:
            print("⚠️ 섹션 데이터가 없습니다.")
            print()
            continue
        
        print(f"총 {len(sections)}개 섹션:")
        print()
        
        empty_sections = []
        for section in sections:
            section_id = section.get("section_id", "unknown")
            status = section.get("status", "unknown")
            char_count = section.get("char_count") or 0
            
            # body_markdown, markdown, content 확인
            body_markdown = section.get("body_markdown") or ""
            markdown = section.get("markdown") or ""
            content = section.get("content") or ""
            
            body_len = len(body_markdown)
            md_len = len(markdown)
            cont_len = len(content)
            
            is_empty = (body_len < 100 and md_len < 100 and cont_len < 100)
            
            status_icon = "✅" if not is_empty else "❌"
            print(f"{status_icon} {section_id:10s} | status={status:10s} | "
                  f"body_markdown={body_len:5d}자 | markdown={md_len:5d}자 | "
                  f"content={cont_len:5d}자 | char_count={char_count}")
            
            if is_empty:
                empty_sections.append(section_id)
        
        print()
        
        if empty_sections:
            print(f"❌ 문제 발견: {len(empty_sections)}개 섹션이 비어있습니다!")
            print(f"   빈 섹션: {', '.join(empty_sections)}")
            print("   원인: save_section()에서 content 저장이 안 되고 있음")
            print()
        else:
            print("✅ 모든 섹션에 데이터가 있습니다.")
            print()
        
        # 3) 섹션 내용 중복 확인
        print("3️⃣ 섹션 내용 중복 확인:")
        print("-" * 60)
        
        # 첫 100자 기준 중복 확인
        content_samples = {}
        for section in sections:
            section_id = section.get("section_id", "")
            body_markdown = section.get("body_markdown") or section.get("markdown") or section.get("content") or ""
            sample = body_markdown[:100].strip()
            
            if sample:
                if sample not in content_samples:
                    content_samples[sample] = []
                content_samples[sample].append(section_id)
        
        duplicates = {k: v for k, v in content_samples.items() if len(v) > 1}
        
        if duplicates:
            print(f"❌ 문제 발견: 중복된 내용이 발견되었습니다!")
            for sample, section_ids in duplicates.items():
                print(f"   동일 내용: {', '.join(section_ids)}")
                print(f"   내용: {sample}...")
                print()
        else:
            print("✅ 섹션 내용이 모두 다릅니다.")
            print()
        
        print()

if __name__ == "__main__":
    asyncio.run(diagnose())
