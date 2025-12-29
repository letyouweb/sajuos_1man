"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5단계: Supabase 저장 검증 테스트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
목적:
1. 섹션 저장 시 content, markdown, body_markdown 모두 저장되는지 확인
2. 저장된 데이터 조회 가능한지 확인
3. raw_json에 원본 데이터 보존 확인
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import asyncio
import sys
import os
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# .env 파일 로드
from dotenv import load_dotenv
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

from app.services.supabase_service import supabase_service


async def test_save_and_retrieve_section():
    """섹션 저장 및 조회 테스트"""
    print("=" * 80)
    print("5단계: Supabase 저장 검증 테스트")
    print("=" * 80)
    print()
    
    # Supabase 사용 가능 여부 확인
    if not supabase_service.is_available():
        print("[SKIP] Supabase 설정 없음")
        return
    
    # 1. 테스트용 Job 생성
    print("[Step 1] 테스트용 Job 생성...")
    try:
        job = await supabase_service.create_job(
            email="test@example.com",
            name="테스트 사용자",
            input_data={"test": "data"},
            target_year=2026
        )
        job_id = job["id"]
        print(f"[OK] Job 생성 완료: {job_id}")
    except Exception as e:
        print(f"[ERROR] Job 생성 실패: {e}")
        return
    
    # 2. 테스트용 섹션 데이터 생성
    test_section_id = "exec"
    test_content = {
        "title": "Executive Summary",
        "body_markdown": """
# Executive Summary

이것은 테스트 리포트입니다.

## 2026년 전망

**핵심 메시지**: 올해는 좋은 해입니다.

### 주요 포인트

1. 첫 번째 포인트
2. 두 번째 포인트
3. 세 번째 포인트

## 결론

성공적인 한 해가 될 것입니다.

[RC-test123] 이것은 내부 토큰입니다.

### 근거:
- 이것은 근거입니다.
""".strip(),
        "confidence": "HIGH",
        "char_count": 200,
        "diagnosis": "테스트 진단",
        "hypotheses": ["가설1", "가설2"],
        "strategy_options": ["전략1", "전략2"]
    }
    
    print(f"\n[Step 2] 섹션 저장...")
    print(f"   Section ID: {test_section_id}")
    print(f"   Body Markdown: {len(test_content['body_markdown'])}자")
    
    try:
        await supabase_service.save_section(
            job_id=job_id,
            section_id=test_section_id,
            content_json=test_content
        )
        print(f"[OK] 섹션 저장 완료")
    except Exception as e:
        print(f"[ERROR] 섹션 저장 실패: {e}")
        return
    
    # 3. 저장된 섹션 조회
    print(f"\n[Step 3] 섹션 조회...")
    try:
        sections = await supabase_service.get_sections(job_id)
        
        if not sections:
            print(f"[ERROR] 섹션 조회 실패: 섹션이 없습니다")
            return
        
        section = sections[0]
        print(f"[OK] 섹션 조회 완료: {len(sections)}개")
        
        # 4. 데이터 검증
        print(f"\n[Step 4] 데이터 검증...")
        
        # 4-1. 필수 컬럼 존재 확인
        required_columns = ["content", "markdown", "body_markdown", "raw_json"]
        missing_columns = [col for col in required_columns if col not in section or section[col] is None]
        
        if missing_columns:
            print(f"[FAIL] 누락된 컬럼: {missing_columns}")
        else:
            print(f"[OK] 모든 필수 컬럼 존재: {required_columns}")
        
        # 4-2. 내용 검증
        content = section.get("content", "")
        markdown = section.get("markdown", "")
        body_markdown = section.get("body_markdown", "")
        raw_json = section.get("raw_json", {})
        
        print(f"\n[검증 결과]")
        print(f"   content 길이: {len(content)}자")
        print(f"   markdown 길이: {len(markdown)}자")
        print(f"   body_markdown 길이: {len(body_markdown)}자")
        print(f"   raw_json 키 수: {len(raw_json)}개")
        
        # 4-3. Sanitize 검증 (RC- 토큰이 제거되었는지)
        if "RC-test123" in content:
            print(f"[FAIL] RC- 토큰이 제거되지 않음")
        else:
            print(f"[OK] RC- 토큰 제거됨")
        
        if "### 근거:" in content:
            print(f"[FAIL] 근거 섹션이 제거되지 않음")
        else:
            print(f"[OK] 근거 섹션 제거됨")
        
        # 4-4. raw_json에 원본 보존 확인
        raw_body = raw_json.get("body_markdown", "")
        if "RC-test123" in raw_body:
            print(f"[OK] raw_json에 원본 보존됨")
        else:
            print(f"[FAIL] raw_json에 원본이 없음")
        
        # 4-5. 메타 데이터 확인
        print(f"\n[메타 데이터]")
        print(f"   title: {section.get('title', 'N/A')}")
        print(f"   confidence: {section.get('confidence', 'N/A')}")
        print(f"   char_count: {section.get('char_count', 0)}")
        print(f"   status: {section.get('status', 'N/A')}")
        print(f"   section_order: {section.get('section_order', 'N/A')}")
        
        # 5. Job 완료 처리
        print(f"\n[Step 5] Job 완료 처리...")
        try:
            result_json = {
                "name": "테스트 사용자",
                "target_year": 2026,
                "sections": {test_section_id: test_content}
            }
            markdown = test_content["body_markdown"]
            saju_json = {
                "year_pillar": "갑진",
                "month_pillar": "병오",
                "day_pillar": "기축",
                "hour_pillar": "미입력"
            }
            
            await supabase_service.complete_job(
                job_id=job_id,
                result_json=result_json,
                markdown=markdown,
                saju_json=saju_json
            )
            print(f"[OK] Job 완료 처리 완료")
        except Exception as e:
            print(f"[ERROR] Job 완료 실패: {e}")
        
        # 6. 최종 검증
        print(f"\n{'=' * 80}")
        print(f"[최종 검증]")
        print(f"{'=' * 80}")
        
        all_ok = (
            len(content) > 100 and
            len(markdown) > 100 and
            len(body_markdown) > 100 and
            len(raw_json) > 0 and
            "RC-test123" not in content and
            "### 근거:" not in content and
            "RC-test123" in raw_body
        )
        
        if all_ok:
            print(f"[OK] 모든 테스트 통과!")
            print(f"   - content/markdown/body_markdown 저장됨")
            print(f"   - Sanitize 적용됨 (RC- 토큰, 근거 제거)")
            print(f"   - raw_json에 원본 보존됨")
        else:
            print(f"[FAIL] 일부 테스트 실패")
        
    except Exception as e:
        print(f"[ERROR] 테스트 실패: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_save_and_retrieve_section())
