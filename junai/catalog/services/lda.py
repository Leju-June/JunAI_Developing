# catalog/services/lda.py
from __future__ import annotations

import os
import re
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from openai import OpenAI
from django.conf import settings

# api.env 로드
_ENV_PATH = Path(__file__).with_name("api.env")
load_dotenv(_ENV_PATH)


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY가 설정되지 않았습니다. "
            "catalog/services/api.env 또는 OS 환경변수 또는 settings.py를 확인하세요."
        )
    return OpenAI(api_key=api_key)


@dataclass
class LDAJobResult:
    answer_text: str
    saved_relpaths: List[str]  # MEDIA_ROOT 기준 상대경로 리스트


BASE_LDA_PROMPT = """
너는 데이터 분석가다. 제공된 CSV 파일로 LDA 토픽 모델링을 수행하고 그래프/결과파일을 생성하라.

[입력 CSV 형식]
- (우선) 'tokens' 컬럼이 있으면: 각 행의 tokens는 공백으로 구분된 토큰 문자열이다.
- (그 외) 헤더 없는 토큰 리스트 CSV로 보고, 각 행의 각 셀을 토큰으로 취급한다.
- 빈 토큰/NaN 제거, 길이 1 토큰 제거.

[요구사항]
1) 바이그램 적용(가능하면 gensim Phrases/Phraser).
2) 후보 K={8,10,12,15}로 모델 학습 후 가능한 경우 Coherence(c_v)로 최적 K 선택.
3) 최종 K로 LDA 학습.
4) 아래 파일을 반드시 현재 작업 디렉토리에 저장:
   - coherence_by_k.png
   - topic_prevalence.png
   - topics.csv (topic_id, term, weight 상위 20)
   - doc_topic.csv (문서별 토픽 확률)
   - 가능하면 topic_terms_topic{i}.png (토픽별 상위 단어 막대그래프)
5) 한국어로 (a) 최적 K (b) 토픽 요약(각 1줄)만 간단히 출력하라.
시각화는 Matplotlib로 하고, 한글이 깨지거나 잘리지 않도록 (1) 사용 가능한 한글 폰트를 자동 탐색해 설정하고, (2) 모든 savefig에 bbox_inches="tight", pad_inches=0.2, dpi>=200, tight_layout()을 적용하라
""".strip()


def _safe_filename(name: str) -> str:
    name = (name or "").strip()
    name = Path(name).name  # 경로 제거
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name or "output"


def _extract_container_file_citations(resp_dict: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    code_interpreter 생성 파일은 message.content[*].annotations[*]에
    type=container_file_citation으로 포함됩니다.
    """
    out: List[Dict[str, str]] = []
    for item in resp_dict.get("output", []) or []:
        if item.get("type") != "message":
            continue
        for part in item.get("content", []) or []:
            for ann in part.get("annotations", []) or []:
                if ann.get("type") == "container_file_citation":
                    out.append({
                        "container_id": ann["container_id"],
                        "file_id": ann["file_id"],
                        "filename": ann.get("filename", ann["file_id"]),
                    })

    # 중복 제거
    seen = set()
    uniq: List[Dict[str, str]] = []
    for x in out:
        k = (x["container_id"], x["file_id"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(x)
    return uniq


def _download_container_file_bytes(api_key: str, container_id: str, file_id: str) -> bytes:
    """
    GET /v1/containers/{container_id}/files/{file_id}/content
    (Container Files API Reference) :contentReference[oaicite:2]{index=2}
    """
    url = f"https://api.openai.com/v1/containers/{container_id}/files/{file_id}/content"
    req = Request(url, headers={"Authorization": f"Bearer {api_key}"})
    with urlopen(req, timeout=180) as r:
        return r.read()


def run_lda_from_csv(csv_path: Path, job_dir: Path, extra_instruction: str = "", model: str = "gpt-5") -> LDAJobResult:
    """
    views.py에서 호출하는 시그니처와 동일:
      run_lda_from_csv(upload_path, job_dir, extra_instruction=extra)

    CSV는 input_file로 주입하지 말고,
    code_interpreter container의 file_ids로 첨부해야 합니다. :contentReference[oaicite:3]{index=3}
    """
    client = _client()
    api_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")

    csv_path = Path(csv_path)
    job_dir = Path(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)

    if not csv_path.exists():
        raise FileNotFoundError(f"입력 CSV가 존재하지 않습니다: {csv_path}")

    # 1) Files API 업로드
    with csv_path.open("rb") as f:
        up = client.files.create(file=f, purpose="user_data")

    prompt = BASE_LDA_PROMPT
    if extra_instruction.strip():
        prompt += "\n\n[추가 지시]\n" + extra_instruction.strip()

    # 2) Responses + code_interpreter (auto container + file_ids)
    resp = client.responses.create(
        model=model,
        tool_choice="required",
        tools=[{
            "type": "code_interpreter",
            "container": {
                "type": "auto",
                "memory_limit": "4g",
                "file_ids": [up.id],
            },
        }],
        instructions="너는 한국어로 답하는 데이터 분석가다. 반드시 python tool로 LDA를 수행하고 파일을 생성하라.",
        input=[{
            "role": "user",
            "content": [{"type": "input_text", "text": prompt}],
        }],
    )

    resp_dict = resp.model_dump() if hasattr(resp, "model_dump") else json.loads(json.dumps(resp, default=str))
    answer_text = (resp_dict.get("output_text") or "").strip()

    # 3) 생성 파일 다운로드 후 job_dir에 저장
    citations = _extract_container_file_citations(resp_dict)

    media_root = Path(settings.MEDIA_ROOT).resolve()
    saved_relpaths: List[str] = []

    for c in citations:
        data = _download_container_file_bytes(api_key, c["container_id"], c["file_id"])
        fname = _safe_filename(c["filename"])
        out_path = (job_dir / fname).resolve()
        out_path.write_bytes(data)

        rel = out_path.relative_to(media_root)
        saved_relpaths.append(str(rel).replace("\\", "/"))

    if not answer_text:
        answer_text = "[완료] 실행은 끝났지만 요약 텍스트가 비어 있습니다."

    return LDAJobResult(answer_text=answer_text, saved_relpaths=saved_relpaths)
