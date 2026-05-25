import time
import requests
from langsmith import traceable

from ..config import QACfg, get_stage_config
from ..prompts import get_qa_system_prompt


@traceable(name="qa.4_chat_completion", run_type="llm")
def get_answer_by_chat_model(query, similar_segments, cfg: QACfg | None = None):
    cfg = cfg or get_stage_config().qa
    context_text = "\n".join(
        f"[{seg['start_time']:.0f}s] "
        + (f"({seg['speaker_id']}) " if seg.get("speaker_id") else "")
        + seg["text"]
        + (
            f"\n[비전] {seg['frame_description']}"
            if seg.get("frame_description")
            else ""
        )
        for seg in similar_segments
    )

    system_prompt = get_qa_system_prompt()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"컨텍스트:\n{context_text}\n\n질문: {query}"},
    ]

    if cfg.provider == "openai":
        from openai import OpenAI, RateLimitError

        client = OpenAI(api_key=cfg.openai_api_key)
        for attempt in range(5):
            try:
                resp = client.chat.completions.create(
                    model=cfg.openai_chat_model,
                    messages=messages,
                )
                answer = resp.choices[0].message.content
                break
            except RateLimitError:
                wait = min(2**attempt, 10)
                print(
                    f"[chat] Rate limit hit, retrying in {wait}s... ({attempt + 1}/5)"
                )
                time.sleep(wait)
        else:
            raise RuntimeError("OpenAI chat rate limit: 5회 재시도 후에도 실패")
    else:
        resp = requests.post(
            f"{cfg.ollama_base}/api/chat",
            json={
                "model": cfg.ollama_chat_model,
                "messages": messages,
                "stream": False,
            },
        )
        answer = resp.json()["message"]["content"]

    return answer, context_text
