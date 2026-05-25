# Python 동시성 개념 정리

> ingest_pipeline.py 프레임 병렬화 및 main.py 비동기 개선 과정에서 정리한 개념입니다.

---

## 1. GIL (Global Interpreter Lock)

GIL은 CPython(표준 Python)의 전역 뮤텍스로, 한 번에 Python 바이트코드를 실행하는 스레드를 1개로 제한합니다.

**존재 이유**: CPython의 메모리 관리(reference counting)가 thread-safe하지 않아, 여러 스레드가 동시에 Python 객체를 건드리면 메모리 오염이 발생합니다. GIL이 이를 방지합니다.

### CPU bound vs I/O bound

| 작업 유형 | GIL 영향 | thread 병렬화 효과 |
|---|---|---|
| **CPU bound** (연산) | GIL이 한 스레드만 허용 | 없음 — 사실상 순차 실행 |
| **I/O bound** (네트워크, 파일) | 대기 중 GIL 자동 반납 | 있음 — 대기 시간이 겹침 |

```
# I/O bound에서 thread가 동작하는 원리
Thread A: Vision API 요청 → 대기 중 → GIL 반납
Thread B:                              GIL 획득 → Vision API 요청 → 대기 중 → GIL 반납
Thread A:                                                                       응답 받음 → GIL 재획득
```

CPU bound를 진짜로 병렬화하려면 `multiprocessing` 또는 `ProcessPoolExecutor`(프로세스 분리, GIL 별개)를 사용해야 합니다.

---

## 2. asyncio.gather vs ThreadPoolExecutor

둘 다 "여러 작업을 동시에 실행"하는 도구이지만 실행 모델이 다릅니다.

| | `asyncio.gather` | `ThreadPoolExecutor` |
|---|---|---|
| 실행 모델 | 비동기 coroutine interleave | OS 스레드 병렬 실행 |
| 필요 조건 | event loop 안에서만 실행 가능 | 없음 |
| I/O bound 효과 | 있음 | 있음 (GIL 양보) |

---

## 3. 왜 ingest_pipeline에서 gather를 사용할 수 없었는가

`run_ingest`는 **sync 함수**입니다. FastAPI는 sync handler를 `run_in_executor`로 worker thread에서 실행합니다.

```
asyncio event loop
  └─ run_in_executor
       └─ run_ingest()        ← 이미 worker thread 안
            └─ _trace_vision()
                 └─ asyncio.gather(...)  ← RuntimeError: no current event loop
```

`asyncio.gather`는 event loop 위에서만 동작하는데, thread 안에는 event loop가 없습니다. 우회책으로 `asyncio.run()`을 사용할 수 있지만, thread 안에서 새 event loop를 생성하는 안티패턴입니다.

`ThreadPoolExecutor`는 event loop에 의존하지 않아 sync 컨텍스트에서 그대로 사용할 수 있습니다.

---

## 4. run_ingest를 async로 바꾸면 되지 않는가

기술적으로는 가능하지만 파급 범위가 큽니다.

```
# async로 바꾸면 호출 스택 전체가 연쇄적으로 async 필요
FastAPI route      → async def 필요
  run_ingest       → async def
    _trace_vision  → async def
      _analyze_frames_parallel → async def
        asyncio.gather(...)    ← 여기서야 사용 가능
```

추가로:
- `@traceable` 데코레이터의 async 처리 검증이 필요합니다.
- `run_qa`(sync)와 pipeline 패턴이 달라져 일관성이 깨집니다.

**결론**: 목적이 "프레임 병렬화" 하나라면 `ThreadPoolExecutor`가 합리적인 선택입니다. async 전환은 파이프라인 전체를 비동기로 재설계할 때 함께 진행해야 합니다.

---

## 5. asyncio.to_thread — main.py blocking 문제 해결

### 문제

`app/main.py`의 모든 route handler가 `async def`였지만, 내부에서 blocking I/O를 직접 호출하고 있었습니다.

```python
# 문제 — async def인데 실제로는 이벤트 루프를 차단
async def process_media_background(...):
    segments = transcribe_audio(audio_path)   # blocking
    frames = extract_key_frames(...)          # blocking
    # ...약 40분짜리 처리 동안 다른 요청 응답 불가
```

FastAPI의 `async def` handler는 event loop에서 직접 실행됩니다. 내부에 blocking 호출이 있으면 그 시간 동안 event loop 전체가 멈춰 다른 요청을 처리할 수 없습니다.

### asyncio.to_thread()

sync 함수를 별도 thread에서 실행하고 완료를 `await`으로 기다립니다. event loop는 그 사이에 다른 요청을 처리할 수 있습니다.

```python
# after — thread로 파견, event loop는 해방
async def process_media_background(...):
    await asyncio.to_thread(run_ingest, job_id, media_id, file_path, filename, job_store)
```

```
event loop
  ├─ to_thread(run_ingest) → worker thread로 파견 후 await
  ├─ GET /health 요청 → 즉시 응답 가능  ← 개선 포인트
  └─ GET /media/jobs/{id} 폴링 → 즉시 응답 가능
```

### 적용 범위 (main.py 전체)

| 대상 | 변경 내용 |
|---|---|
| `process_media_background` | `run_ingest` → `to_thread` |
| `/health` | `requests.get` (Ollama 체크) → `to_thread` |
| `/media/` | `get_all_media` → `to_thread` |
| `/media/{id}/file` | `get_media_by_id` → `to_thread` |
| `/qa` | 임베딩·검색·답변 생성 각각 `to_thread` |
| `/media/{id}/segments` | `get_media_segments` → `to_thread` |
| `/media/{id}/summary` | DB 조회 + LLM 호출 → `to_thread` |
| `/media/{id}/evaluate` | `run_full_evaluation` → `to_thread` |

### 도메인 함수를 sync로 유지한 이유

`evals/_stages.py`는 `app/ingest/`, `app/qa/` 안의 도메인 함수를 sync로 직접 호출합니다.

```python
# evals/_stages.py
from app.ingest.transcription import transcribe_audio
from app.ingest.vision import analyze_frame_with_vision_model

segments = transcribe_audio(audio_path)             # sync 직접 호출
description = analyze_frame_with_vision_model(...)  # sync 직접 호출
```

evals는 FastAPI 바깥의 CLI 스크립트라 event loop가 없습니다. 도메인 함수를 async로 바꾸면 evals의 모든 호출부를 `asyncio.run(...)`으로 수정해야 합니다.

`to_thread`는 **호출 지점(main.py)만 래핑**하는 방식이라 함수 시그니처는 그대로 유지됩니다. 같은 sync 함수를 main.py는 `to_thread`로, evals는 직접 호출하는 방식으로 두 컨텍스트가 각자 방식으로 사용합니다.

### time.sleep 처리

rate limit 재시도에 사용되던 `time.sleep()`도 `to_thread` 덕분에 수정이 불필요했습니다. thread 안에서 sleep하므로 event loop는 차단되지 않습니다.

---

## 6. 현재 구현 — Vision 프레임 병렬화

```python
_VISION_CONCURRENCY = 4  # OpenAI Vision API rate limit 대비 동시 실행 수 상한

def _analyze_frames_parallel(frames, cfg):
    def _analyze_one(frame):
        description = analyze_frame_with_vision_model(
            frame["frame_path"], frame["timestamp"], cfg=cfg
        )
        return {"timestamp": frame["timestamp"], "description": description}

    with ThreadPoolExecutor(max_workers=_VISION_CONCURRENCY) as executor:
        return list(executor.map(_analyze_one, frames))
```

Vision API 호출은 I/O bound(네트워크 대기) 작업입니다. 대기 중에 GIL이 자동으로 반납되므로 thread 병렬화가 실질적으로 동작합니다. `max_workers=4`가 동시 실행 수를 제한해 Vision API rate limit에 대응합니다.

---