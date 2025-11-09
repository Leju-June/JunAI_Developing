# catalog/services/lda.py
from pathlib import Path
import os
from functools import lru_cache

from dotenv import load_dotenv
from openai import OpenAI

# api.env를 이 파일과 같은 폴더에서 확실히 로드
_ENV_PATH = Path(__file__).with_name("api.env")
load_dotenv(_ENV_PATH)  # 파일 없으면 조용히 넘어감(문제없음)

@lru_cache(maxsize=1)
def _client() -> OpenAI:
    # 우선순위: 환경변수 → settings.OPENAI_API_KEY
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        try:
            from django.conf import settings
            api_key = getattr(settings, "OPENAI_API_KEY", None)
        except Exception:
            api_key = None
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY가 설정되지 않았습니다. "
            "catalog/services/api.env 또는 OS 환경변수를 확인하세요."
        )
    return OpenAI(api_key=api_key)

def get_answer(question: str) -> str:
    """
    질문을 받아 OpenAI 응답 텍스트를 반환.
    """
    client = _client()

    # ① Responses API(간단히 문자열 입력)
    # resp = client.responses.create(
    #     model="gpt-4o",
    #     input=question,
    # )
    # return resp.output_text.strip()

    # ② Chat Completions API(시스템 프롬프트 포함을 원하면 이쪽 권장)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "너는 한국어로 대답하는 유능한 AI 어시스턴트야."},
            {"role": "user", "content": question},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()