"""
OpenAI API Key 관리 모듈
- 복붙 실수 방지: 숨은 문자(zero-width, BOM, NBSP) 제거
- 로그에 키 노출 없이 fingerprint + tail만 출력
"""
import os
import re
import hashlib

# 보이지 않는 문자들 (복붙 시 섞일 수 있음)
_INVISIBLES = ["\u200b", "\ufeff", "\xa0"]  # zero-width, BOM, NBSP


def get_openai_api_key() -> str:
    """
    환경변수에서 OpenAI API 키를 읽고 정규화.
    - 따옴표, 개행, 공백, invisible chars 모두 제거
    - 잘못된 키면 RuntimeError 발생
    """
    k = os.getenv("OPENAI_API_KEY", "")

    # 양끝 따옴표 제거 (대시보드 복붙 실수)
    k = k.strip().strip('"').strip("'")

    # invisible chars 제거
    for ch in _INVISIBLES:
        k = k.replace(ch, "")

    # 모든 공백/개행/탭 제거
    k = re.sub(r"\s+", "", k)

    # Bearer까지 넣었으면 제거
    if k.lower().startswith("bearer "):
        k = k[7:].strip()

    # 빈 문자열이면 에러
    if not k:
        raise RuntimeError("OPENAI_API_KEY is empty. Set it in Railway Variables.")

    # sk-로 시작하지 않으면 경고 (에러는 아님)
    if not k.startswith("sk-"):
        import logging
        logging.getLogger(__name__).warning(
            "OPENAI_API_KEY doesn't start with 'sk-'. fp=%s tail=%s",
            key_fingerprint(k), k[-6:]
        )

    return k


def key_fingerprint(k: str) -> str:
    """키 노출 없이 동일성 검증용 fingerprint (12자)"""
    if not k:
        return "(empty)"
    return hashlib.sha256(k.encode("utf-8")).hexdigest()[:12]


def key_tail(k: str, n: int = 6) -> str:
    """키 마지막 n글자 (디버깅용)"""
    return k[-n:] if k else "(empty)"
