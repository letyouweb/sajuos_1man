"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4단계: Supabase 통합 테스트 - 실제 데이터 저장 확인
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import asyncio
import json
import sys
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# .env 파일 로드
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)
print(f"Environment loaded from: {env_path}")
print(f"SUPABASE_URL: {os.getenv('SUPABASE_URL', 'NOT SET')[:30]}...")

# UTF-8 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from app.services.supabase_service import supabase_service, SECTION_SPECS

async def test_supabase_integration():
    """실제 Supabase 저장/조회 테스트"""
    
    print("\n" + "="*80)
    print("🔥 4단계: Supabase 통합 테스트 시작")
    print("="*80)
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 1. Supabase 연결 확인
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n[1] Supabase 연결 확인...")
    if not supabase_service.is_available():
        print("❌ Supabase 설정이 없습니다!")
        return
    
    try:
        supabase_service._get_client()
        print("✅ Supabase 연결 성공!")
    except Exception as e:
        print(f"❌ Supabase 연결 실패: {e}")
        return
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 2. 테스트 Job 생성
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n[2] 테스트 Job 생성...")
    test_email = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}@test.com"
    test_input = {
        "birth_date": "1985-05-15",
        "birth_hour": 14,
        "birth_minute": 30,
        "is_solar": True,
        "gender": "남",
        "name": "테스트사용자"
    }
    
    try:
        job = await supabase_service.create_job(
            email=test_email,
            name="테스트사용자",
            input_data=test_input,
            target_year=2026
        )
        print(f"✅ Job 생성 성공!")
        print(f"   Job ID: {job['id']}")
        print(f"   Token: {job['public_token'][:16]}...")
    except Exception as e:
        print(f"❌ Job 생성 실패: {e}")
        return
    
    job_id = job['id']
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 3. 섹션 초기화
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n[3] 섹션 초기화...")
    try:
        await supabase_service.init_sections(job_id, SECTION_SPECS)
        sections = await supabase_service.get_sections(job_id)
        print(f"✅ 섹션 초기화 성공! ({len(sections)}개)")
        for sec in sections:
            print(f"   - {sec['section_id']}: {sec['status']}")
    except Exception as e:
        print(f"❌ 섹션 초기화 실패: {e}")
        return
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 4. 테스트 섹션 저장 (content 필드 확인)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n[4] 테스트 섹션 저장...")
    
    test_sections = [
        {
            "section_id": "exec",
            "content": {
                "title": "Executive Summary",
                "body_markdown": "# Executive Summary\n\n이것은 테스트 리포트입니다.\n\n[RC-TEST-001] 테스트 룰카드\n\n### 근거:\n- 테스트 근거 1\n- 테스트 근거 2\n\n본문 내용이 여기에 들어갑니다. 최소 100자 이상의 내용을 작성하여 검증합니다. " * 3,
                "char_count": 200,
                "confidence": "high",
                "used_rulecard_ids": ["RC-TEST-001"]
            }
        },
        {
            "section_id": "money",
            "content": {
                "title": "Money & Cashflow",
                "markdown": "# Money & Cashflow\n\n재물운 분석입니다.\n\n[RC-MONEY-001] 재물 룰카드\n\n### 근거:\n- 재물 근거 1\n\n재물운 본문 내용입니다. " * 5,
                "char_count": 150,
                "confidence": "medium"
            }
        }
    ]
    
    for test_sec in test_sections:
        try:
            await supabase_service.save_section(
                job_id=job_id,
                section_id=test_sec["section_id"],
                content_json=test_sec["content"]
            )
            print(f"✅ 섹션 저장 성공: {test_sec['section_id']}")
        except Exception as e:
            print(f"❌ 섹션 저장 실패 ({test_sec['section_id']}): {e}")
            continue
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 5. 저장된 섹션 조회 및 검증
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n[5] 저장된 섹션 조회 및 검증...")
    try:
        sections = await supabase_service.get_sections(job_id)
        print(f"✅ 섹션 조회 성공! ({len(sections)}개)")
        
        for sec in sections:
            if sec['section_id'] in ['exec', 'money']:
                print(f"\n📋 섹션: {sec['section_id']}")
                print(f"   Status: {sec['status']}")
                print(f"   Title: {sec.get('title', 'N/A')}")
                print(f"   Char Count: {sec.get('char_count', 0)}")
                
                # 🔥 핵심: content 필드 확인
                content = sec.get('content', '')
                body_markdown = sec.get('body_markdown', '')
                markdown = sec.get('markdown', '')
                
                print(f"   Content Length: {len(content)}")
                print(f"   Body Markdown Length: {len(body_markdown)}")
                print(f"   Markdown Length: {len(markdown)}")
                
                # 🔥 검증: RC-xxxx, 근거: 제거 확인
                if 'RC-' in content or '근거:' in content:
                    print(f"   ⚠️ 경고: RC 토큰 또는 근거가 남아있음!")
                else:
                    print(f"   ✅ Sanitize 성공!")
                
                # 🔥 검증: 내용 미리보기
                preview = content[:100] if content else "EMPTY"
                print(f"   Preview: {preview}...")
                
                # 🔥 검증: raw_json에 원본 보존 확인
                raw_json = sec.get('raw_json', {})
                if raw_json:
                    print(f"   Raw JSON Keys: {list(raw_json.keys())}")
                    if 'used_rulecard_ids' in raw_json:
                        print(f"   Used Rulecards: {raw_json['used_rulecard_ids']}")
                
    except Exception as e:
        print(f"❌ 섹션 조회 실패: {e}")
        return
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 6. Job 완료 처리
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n[6] Job 완료 처리...")
    
    test_saju_json = {
        "year_pillar": "을축",
        "month_pillar": "신사",
        "day_pillar": "계미",
        "hour_pillar": "기미",
        "year_stem": "을",
        "year_branch": "축",
        "month_stem": "신",
        "month_branch": "사",
        "day_stem": "계",
        "day_branch": "미",
        "hour_stem": "기",
        "hour_branch": "미"
    }
    
    try:
        await supabase_service.complete_job(
            job_id=job_id,
            result_json={"test": "완료"},
            markdown="# 전체 리포트\n\n테스트 마크다운",
            saju_json=test_saju_json
        )
        print("✅ Job 완료 처리 성공!")
    except Exception as e:
        print(f"❌ Job 완료 처리 실패: {e}")
        return
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 7. 최종 검증
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n[7] 최종 검증...")
    try:
        job_final = await supabase_service.get_job(job_id)
        print(f"✅ Job 최종 상태: {job_final['status']}")
        print(f"   Progress: {job_final['progress']}%")
        print(f"   Markdown Length: {len(job_final.get('markdown', ''))}")
        
        if job_final.get('saju_json'):
            saju = job_final['saju_json']
            print(f"   🎯 Saju JSON 확인:")
            print(f"      Year: {saju.get('year_pillar', 'N/A')}")
            print(f"      Month: {saju.get('month_pillar', 'N/A')}")
            print(f"      Day: {saju.get('day_pillar', 'N/A')}")
            print(f"      Hour: {saju.get('hour_pillar', 'N/A')}")
        else:
            print(f"   ⚠️ Saju JSON 없음!")
        
    except Exception as e:
        print(f"❌ 최종 검증 실패: {e}")
        return
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 8. 결과 요약
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n" + "="*80)
    print("✅ 4단계 Supabase 통합 테스트 완료!")
    print("="*80)
    print(f"\n📊 테스트 결과:")
    print(f"   Job ID: {job_id}")
    print(f"   Status: {job_final['status']}")
    print(f"   Sections: {len(sections)}개")
    print(f"   Token: {job['public_token'][:16]}...")
    print(f"\n🔍 프론트엔드 테스트 URL:")
    print(f"   https://sajuos.com/report/{job_id}?token={job['public_token']}")
    print("\n" + "="*80)

if __name__ == "__main__":
    asyncio.run(test_supabase_integration())
