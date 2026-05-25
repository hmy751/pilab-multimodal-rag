# ============================================================
# MediaFlow AI Agent — 메인 애플리케이션
# ============================================================

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Body
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import Request
import asyncio
import os
import requests
from uuid import uuid4
from typing import Dict, Any
from datetime import datetime

from .config import CONFIG, get_stage_config
from .diagnostics import get_config_snapshot
from .supabase_utils import (
    get_all_media,
    get_media_by_id,
    get_media_segments,
)
from .evaluation_utils import run_full_evaluation
from .pipelines.ingest_pipeline import run_ingest
from .pipelines.qa_pipeline import run_qa

app = FastAPI(title="MediaFlow AI Agent")

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ────────────────────────────────────────
# [완성 코드] Job State Machine
# pending → transcribing → analyzing_frames → embedding → ready | failed
# ────────────────────────────────────────
job_store: Dict[str, Dict[str, Any]] = {}


def allowed_file(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in CONFIG.allowed_media_extensions
    )


# ────────────────────────────────────────
# [완성 코드] 백그라운드 처리 오케스트레이터
# Job State: pending → transcribing → analyzing_frames → embedding → ready | failed
# 실제 오케스트레이션은 pipelines.ingest_pipeline.run_ingest에 위임.
# 이 함수는 FastAPI BackgroundTasks 진입점으로서 job_store를 주입하는 wrapper.
# ────────────────────────────────────────
async def process_media_background(
    job_id: str, media_id: str, file_path: str, filename: str
):
    await asyncio.to_thread(
        run_ingest, job_id, media_id, file_path, filename, job_store
    )


# ────────────────────────────────────────
# 라우트
# ────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def root_page(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/media/{media_id}/file")
async def serve_media_file(media_id: str):
    media = await asyncio.to_thread(get_media_by_id, media_id)
    if not media or not media.get("file_path"):
        raise HTTPException(status_code=404, detail="미디어 파일을 찾을 수 없습니다.")
    file_path = media["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="파일이 서버에 존재하지 않습니다.")
    return FileResponse(file_path)


# [완성 코드] 건강 체크
@app.get("/health")
async def health_check():
    cfg = get_stage_config()
    providers = {
        "transcription": cfg.transcription.provider,
        "vision": cfg.vision.provider,
        "embedding": cfg.embedding.provider,
        "qa": cfg.qa.provider,
        "judge": cfg.judge.provider,
    }
    components: Dict[str, Any] = {"status": "ok", "providers": providers}

    has_local = any(p == "local" for p in providers.values())
    if has_local:
        try:
            resp = await asyncio.to_thread(
                requests.get, f"{CONFIG.ollama_base}/api/tags", timeout=3
            )
            components["ollama"] = "ok" if resp.status_code == 200 else "error"
        except Exception:
            components["ollama"] = "unreachable"

    return components


# [완성 코드] Job 상태 폴링
@app.get("/media/jobs/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="job not found")
    return job_store[job_id]


# [완성 코드] 미디어 업로드 — 파이프라인 오케스트레이션은 process_media_background()가 처리
@app.post("/media/upload")
async def upload_media(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    미디어 파일(오디오/비디오)을 업로드하고 백그라운드 처리를 시작합니다.

    반환: job_id — 클라이언트는 GET /media/jobs/{job_id}로 상태를 폴링합니다.
    여러분이 구현한 함수들이 process_media_background() 내부에서 자동으로 호출됩니다.
    """
    if not allowed_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. 허용: {CONFIG.allowed_media_extensions}",
        )

    media_id = str(uuid4())
    job_id = str(uuid4())
    ext = file.filename.rsplit(".", 1)[1].lower()
    file_path = os.path.join(CONFIG.upload_dir, f"{media_id}.{ext}")

    _UPLOAD_CHUNK = 1024 * 1024  # 1MB
    with open(file_path, "wb") as f:
        while chunk := await file.read(_UPLOAD_CHUNK):
            f.write(chunk)

    job_store[job_id] = {
        "status": "pending",
        "media_id": media_id,
        "filename": file.filename,
        "created_at": datetime.utcnow().isoformat(),
    }

    background_tasks.add_task(
        process_media_background, job_id, media_id, file_path, file.filename
    )

    return {"job_id": job_id, "media_id": media_id, "status": "pending"}


# 미디어 목록 조회
@app.get("/media/")
async def list_media():
    result = await asyncio.to_thread(get_all_media)
    return {"media": result}


# Q&A
@app.post("/qa")
async def question_answering(body: Dict[str, Any] = Body(...)):
    if "query" not in body or "media_id" not in body:
        raise HTTPException(status_code=400, detail="query와 media_id가 필요합니다.")

    query = body["query"]
    media_id = body["media_id"]

    result = await asyncio.to_thread(run_qa, query, media_id)

    return {
        "answer": result["answer"],
        "context_text": result["context_text"],
        "sources": result["all_segments"],
        "media_id": media_id,
        "config": get_config_snapshot(),
        "latency_ms": result["latency_ms"],
        "trace_id": result["trace_id"],
    }


# 세그먼트 목록 조회 (UI 전사 패널에서 사용)
@app.get("/media/{media_id}/segments")
async def get_segments(media_id: str):
    segments = await asyncio.to_thread(get_media_segments, media_id)
    return {"segments": segments, "media_id": media_id}


# 요약
@app.post("/media/{media_id}/summary")
async def summarize_media(media_id: str):
    segments = await asyncio.to_thread(get_media_segments, media_id)

    full_text = "\n".join(seg["text"] for seg in segments)

    messages = [
        {
            "role": "system",
            "content": "당신은 인터뷰 내용을 요약하는 전문가입니다.",
        },
        {
            "role": "user",
            "content": f"아래 인터뷰 전사 내용을 핵심 위주로 요약하세요:\n\n{full_text}",
        },
    ]

    qa_cfg = get_stage_config().qa
    if qa_cfg.provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=qa_cfg.openai_api_key)
        resp = await asyncio.to_thread(
            client.chat.completions.create,
            model=qa_cfg.openai_chat_model,
            messages=messages,
        )
        summary = resp.choices[0].message.content
    else:
        resp = await asyncio.to_thread(
            requests.post,
            f"{qa_cfg.ollama_base}/api/chat",
            json={
                "model": qa_cfg.ollama_chat_model,
                "messages": messages,
                "stream": False,
            },
        )
        summary = resp.json()["message"]["content"]

    return {"summary": summary, "media_id": media_id}


# 평가
@app.get("/media/{media_id}/evaluate")
async def evaluate_media(
    media_id: str, test_questions: str = "", reference_transcript: str = ""
):
    questions = [q.strip() for q in test_questions.split(",") if q.strip()]
    if len(questions) < 1:
        raise HTTPException(
            status_code=400, detail="평가할 질문이 최소 1개 필요합니다."
        )
    result = await asyncio.to_thread(
        run_full_evaluation, media_id, questions, reference_transcript or None
    )

    return {
        "metrics": result["metrics"],
        "qa_results": result["qa_results"],
        "question_count": result["question_count"],
        "config": get_config_snapshot(),
        "media_id": media_id,
    }
