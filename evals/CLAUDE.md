# evals/ — 실험 자동화 디렉토리

> 파이프라인 설정을 바꿨을 때 "나아졌는가?"를 재현 가능하게 측정하는 도구.

> **⚠️ 실행 환경**: 이 프로젝트는 `Pipfile`로 의존성을 관리한다. 패키지 설치와 스크립트 실행은 반드시 `pipenv`를 통해야 한다. 시스템 Python에 `pip install`/`pip install --break-system-packages`로 직접 설치하지 않는다.

---

## 1. 역할

`/evaluate` 엔드포인트와 `evals/`는 목적이 다르다.

|      | `/media/{id}/evaluate`  | `evals/`                                                   |
| ---- | ----------------------- | ---------------------------------------------------------- |
| 질문 | "지금 품질이 괜찮은가?" | "왜 이 수치가 나왔고, 뭘 바꾸면 나아지는가?"               |
| 실행 | 서버 API 호출           | CLI 스크립트 (`pipenv run python evals/run_experiment.py`) |
| 범위 | QA 메트릭 4종           | 파이프라인 전 구간 (전사 ~ QA)                             |
| 결과 | API 응답 (휘발)         | JSON 파일 (git 추적, 실험 간 비교)                         |

`/evaluate`는 품질 게이트("통과/미달"), `evals/`는 진단 도구("어디가 병목이고, 설정 A vs B 중 뭐가 나은가")다.

---

## 2. 실험 원칙

- 매 실험 실행 시, 실행 명령 전에 현재 실행 환경이 의도한 조건과 일치하는지 사용자에게 확인받는다. (예: config, .env, 프롬프트 버전, fixture 상태, 데이터셋 등. `.env`가 `config.py` 기본값을 오버라이드하므로 코드만 보면 안 되고, 실제 로드된 값을 확인해야 한다.)
- 실험용으로 변경한 config, .env, prompts는 실험 완료 후 baseline 상태로 되돌린다. 복원하지 않으면 다음 실험의 기준이 흐트러진다.
- **evals/는 app/에 의존한다.** evals/ 코드를 수정할 때는 의존하는 app/ 코드(config, prompts, 유틸 함수의 시그니처·반환값)가 변경되지 않았는지 확인한다. 반대로 app/ 쪽을 수정했을 때는 evals/의 호출부·스냅샷·문서가 여전히 맞는지 확인한다.
- `results/`의 실험 결과 JSON은 삭제하지 않는다. 실험 이력이 비교의 기반이다.
- `fixtures/`를 수동 편집하지 않는다. 스크립트가 자동 생성한다.
- **fixture는 같은 데이터셋+타입이면 설정과 무관하게 덮어쓴다.** 비교가 필요한 fixture는 실험 전에 수동 백업한다.
- 프롬프트를 바꿀 때는 `app/prompts.py`에 새 버전을 등록하고 `CURRENT_*_VERSION`을 갱신한다. 코드 내 하드코딩을 직접 수정하지 않는다.

---

## 3. 배경

### 왜 자동화가 필요한가

비디오 파이프라인은 전사와 비전 분석에 대부분의 시간이 소요된다. 설정을 바꾸고 수동으로 업로드 → QA → 결과 확인을 반복하면 실험 사이클이 느려지고, 조건 기록이 누락되기 쉬우며, 이전 실험과 정확한 비교가 어렵다.

### n=1 문제

기존 실험에서 질문 1개 × 1회 실행으로 측정했더니, LLM-as-Judge의 분산이 결과에 그대로 반영됐다. Answer Relevance가 0.25 → 0.90으로 뛴 사례에서 실제 개선인지 LLM 분산인지 구분할 수 없었다. 질문 5개 이상이면 평균 + 표준편차로 유의미한 비교가 가능하다.

### 재현성

매 실험 결과 JSON에 config 스냅샷과 프롬프트 전문을 함께 기록한다. "이 결과가 어떤 조건에서 나왔는지" 파일 하나만 열면 바로 확인할 수 있다.

---

## 4. 테스트 기준과 5개 마디

### 4가지 측정 기준

파이프라인 각 단계를 아래 4가지 질문으로 검토하여 테스트 마디를 도출했다.

| 기준       | 질문                                        | 해당 단계                                                       |
| ---------- | ------------------------------------------- | --------------------------------------------------------------- |
| **품질**   | 설정을 바꿨을 때 나아졌는지 비교 가능한가?  | LLM이 관여하는 4개 지점 (전사, 비전, 검색, QA)                  |
| **시간**   | 어디가 병목인가?                            | 모든 단계에 횡단적으로 계측 (독립 마디 아님)                    |
| **정합성** | 코드 수정 시 데이터가 조용히 깨지지 않는가? | 순수 로직 함수 (segment_transcript, combine_multimodal_context) |
| **재사용** | 비싼 결과를 다시 안 만들 수 있는가?         | 중간 산출물이 있는 단계                                         |

### 교차표 → 5개 마디

```
                    품질    시간    정합성   재사용
                   측정?   계측?   검증?   산출물?
────────────────────────────────────────────────
audio_extract       ─      계측     ─       ─      → 독립 마디 불필요
transcribe          WER    계측     ─      JSON    → ★ 마디 A
frame_extract       ─      계측     ─       ─      → vision과 묶임
vision_analyze      품질   계측     ─      JSON    → ★ 마디 B
segment_transcript  ─       ─      경계     ─      → ★ 마디 C (combine 포함)
embed+save          ─      계측    차원    DB행    → ★ 마디 D
search+QA           품질   계측     ─       ─      → ★ 마디 E
```

- **마디 A (전사)**: `whisper_model_size` 변경 시 WER + 소요시간 비교
- **마디 B (비전)**: `vision_model`, 프롬프트 변경 시 설명 품질 + 소요시간 비교
- **마디 C (청킹 로직)**: `segment_transcript`, `combine_multimodal_context`의 경계/포맷 정합성 (순수 함수, fixture 사용, <1초). 현재 embed 단계에 포함되어 실행되며, CLI에서 독립 실행은 미지원.
- **마디 D (임베딩+저장)**: `embedding_model` 변경 시 차원 정합성 + 소요시간
- **마디 E (검색+QA)**: `threshold`/`top_k`/프롬프트 변경 시 retrieval_precision + 답변 품질

ffmpeg, cv2는 독립 마디가 아니다. 마디 A나 B를 돌리면 자연스럽게 포함되고, 단독으로 측정할 품질 지표가 없다.

### 파이프라인 구조와 실행 모드의 관계

파이프라인은 선형이 아니라 **포크 구조**다. 전사와 비전이 독립적으로 갈라졌다가 embed에서 합류한다.

```
datasets/{영상}/source.mp4
       │
       ├──→ [audio 추출] ──→ [transcribe] ──→ segments
       │                                          │
       └──→ [frame 추출] ──→ [vision] ──→ frame_analyses
                                                  │
                              segments + frame_analyses
                                          │
                                    [chunk + embed] ──→ DB 저장
                                          │
                                        [qa] ──→ 메트릭
```

`--changed`와 `--target`은 이 그래프 위에서 동작한다:

```
예: --changed vision --target qa

datasets/{영상}/source.mp4
       │
       ├──→ [transcribe] ── fixture 재사용 (config 검증) ──→ segments
       │                                                        │
       └──→ [vision] ── 🔄 fresh 실행 ──→ frame_analyses
                                                  │
                              segments + frame_analyses
                                          │
                                    [embed] ── 🔄 fresh ──→ DB 저장
                                          │
                                      [qa] ── 🔄 fresh ──→ 메트릭
```

```
예: --target qa (baseline, --changed 없음)

datasets/{영상}/source.mp4
       │
       ├──→ [transcribe] ── 🔄 fresh ──→ segments
       │                                      │
       └──→ [vision] ── 🔄 fresh ──→ frame_analyses
                                              │
                              segments + frame_analyses
                                          │
                                    [embed] ── 🔄 fresh ──→ DB 저장
                                          │
                                      [qa] ── 🔄 fresh ──→ 메트릭
```

---

## 5. 실행 모드

두 가지 플래그로 실험을 제어한다:

- **`--target`** (필수): 어떤 결과물을 만들 것인가
- **`--changed`** (선택): 내가 뭘 바꿨는가

사용 가능한 단계: `transcribe` | `vision` | `embed` | `qa`

### target의 의미

target은 "어디까지 돌릴까"가 아니라 **"이 결과물을 만들기 위해 필요한 최소 단계만 실행한다"**는 뜻이다. 파이프라인이 포크 구조이므로, target에 불필요한 병렬 갈래는 실행하지 않는다.

```text
target이 필요로 하는 단계:
  transcribe → {transcribe}
  vision     → {vision}
  embed      → {transcribe, vision, embed}     ← 합류점이므로 양쪽 필요
  qa         → {transcribe, vision, embed, qa}
```

### baseline 모드: `--changed` 없이 실행

target에 필요한 단계를 전부 fresh 실행한다. 중간 산출물은 fixture로 자동 저장된다.

```bash
# 원본에서 QA까지 전부 새로 실행
pipenv run python evals/run_experiment.py --target qa --dataset galaxy-trifold

# 원본에서 embed까지만
pipenv run python evals/run_experiment.py --target embed --dataset galaxy-trifold
```

baseline 실행 시 새 media_id를 발급한다.

### compare 모드: `--changed` 지정

target에 필요한 단계 중, changed와 그 downstream만 fresh 실행한다. 나머지 필요한 단계는 기존 fixture를 config 검증 후 재사용한다.

```bash
# 비전 프롬프트만 바꾸고, 비전 결과만 확인
pipenv run python evals/run_experiment.py --changed vision --target vision --dataset galaxy-trifold

# 비전 프롬프트 바꾸고, QA까지 영향 확인
pipenv run python evals/run_experiment.py --changed vision --target qa --dataset galaxy-trifold
# → transcribe는 fixture 재사용 (config 검증), vision~qa는 fresh

# 전사만 바꾸고 embed까지 확인
pipenv run python evals/run_experiment.py --changed transcribe --target embed --dataset galaxy-trifold
# → vision은 fixture 재사용, transcribe~embed는 fresh

# 전사+비전 둘 다 바꿨고 embed까지 확인
pipenv run python evals/run_experiment.py --changed transcribe,vision --target embed --dataset galaxy-trifold

# QA 프롬프트만 비교 (DB 재사용)
pipenv run python evals/run_experiment.py --changed qa --target qa --media-id {media_id}
```

### fixture 재사용 규칙

compare 모드에서 범위 밖 upstream fixture가 필요할 때:

1. `fixtures/`에서 해당 dataset의 fixture를 자동 탐색한다
2. fixture의 config와 현재 config를 비교한다 (fingerprint 검증)
3. 일치하면 재사용, 불일치하거나 없으면 **에러** + 안내 메시지

```
segments fixture     → transcription_provider, whisper_model_size, openai_whisper_model 비교
frame_analyses fixture → vision_provider, vision_model, prompt_version, frames_per_minute 비교
```

### 입력원과 옵션

- `--dataset {이름}`: `datasets/{이름}/source.mp4`에서 시작. baseline과 compare 모두 사용.
- `--media-id {id}`: DB의 기존 세그먼트를 조회. QA 단독 실행용.
- `--label {이름}`: 결과 파일명에 포함 (`exp_{label}_{timestamp}.json`). 실험 목적을 식별할 때 사용.

### 실행 매트릭스

```text
명령                                          전사        비전       embed+qa
──────────────────────────────────────       ────────    ────────   ─────────
--target transcribe                           fresh       ─          ─
--target vision                               ─          fresh       ─
--target embed                                fresh       fresh      embed만
--target qa (--dataset)                       fresh       fresh      fresh
--target qa (--media-id)                      ─           ─         QA만 (DB)

--changed vision --target vision              ─          fresh       ─
--changed vision --target qa                  fixture     fresh      fresh
--changed transcribe --target qa              fresh       fixture    fresh
--changed transcribe,vision --target embed    fresh       fresh      embed만
--changed qa --target qa (--media-id)         ─           ─         QA만 (DB)
```

### 시나리오 예시

#### 시나리오 1: 처음 시작 — 기준선 측정

Whisper small + llava v2 + 기본 config로 전체 파이프라인의 현재 품질을 확인한다.

```bash
pipenv run python evals/run_experiment.py --target qa --dataset galaxy-trifold
```

- source.mp4에서 오디오 추출 → 전사 → 프레임 추출 → 비전 → 청킹 → 임베딩 → DB 저장 → QA
- fixture 2개 자동 생성 (`segments_galaxy-trifold.json`, `frame_analyses_galaxy-trifold.json`)
- 결과: `results/exp_{timestamp}.json`

#### 시나리오 2: QA 프롬프트만 바꿔서 빠르게 비교

시스템 프롬프트를 v2로 바꿨는데, 기존 DB 데이터로 QA 품질만 재측정하고 싶다.

```bash
pipenv run python evals/run_experiment.py --changed qa --target qa --media-id abc-123
```

- 전사, 비전, 임베딩은 건드리지 않는다 (DB의 기존 세그먼트 사용)
- QA만 새 프롬프트로 실행 → 메트릭 비교
- 소요: 질문당 ~5초

#### 시나리오 3: 비전 프롬프트를 바꾸고 QA까지 영향 확인

비전 프롬프트를 v3로 바꿨는데, 최종 답변 품질에 어떤 영향을 주는지 확인한다.

```bash
pipenv run python evals/run_experiment.py --changed vision --target qa --dataset galaxy-trifold
```

- transcribe: fixture 자동 탐색 → config 일치 확인 → 재사용 (수분 절약)
- vision~qa: source.mp4에서 프레임 재추출 → 새 프롬프트로 비전 분석 → 청킹 → 임베딩 → QA
- fixture가 없거나 config 불일치 시: 에러 + "baseline을 먼저 실행하세요" 안내

#### 시나리오 4: Whisper medium으로 바꾸고 전체 영향 확인

```bash
# config.py에서 whisper_model_size = "medium"으로 수정 후:
pipenv run python evals/run_experiment.py --changed transcribe --target qa --dataset galaxy-trifold
```

- transcribe: source.mp4에서 오디오 추출 → medium으로 재전사
- vision: fixture 재사용 (vision config는 안 바뀌었으므로)
- embed~qa: 새 전사 + 기존 비전으로 fresh 실행

---

## 6. 데이터셋

### 질문 세트 (questions.json)

질문은 영상에 종속적이므로 `datasets/{영상이름}/` 단위로 분리한다.

```json
[
  { "test_id": "T1", "test_type": "단순사실", "query": "..." },
  { "test_id": "T2", "test_type": "타임스탬프", "query": "..." },
  { "test_id": "T3", "test_type": "비전질문", "query": "..." },
  { "test_id": "T4", "test_type": "환각테스트", "query": "..." },
  { "test_id": "T5", "test_type": "추론질문", "query": "..." }
]
```

| test_type  | 목적                     | 측정 대상                             |
| ---------- | ------------------------ | ------------------------------------- |
| 단순사실   | 전사 + 검색 정확도       | Retrieval Precision, Answer Relevance |
| 타임스탬프 | 타임스탬프 인용 정확도   | AR, Groundedness                      |
| 비전질문   | frame_description 활용도 | Retrieval Precision                   |
| 환각테스트 | 할루시네이션 방지        | Groundedness                          |
| 추론질문   | 복합 컨텍스트 종합       | AR, Groundedness                      |

영상당 5~7개, 타입별 최소 1개를 구성한다.

### 참조 텍스트 (reference.txt)

WER 계산용 정답 전사 텍스트. 영상의 특정 구간(0:00~2:00 등)을 직접 받아쓰기하여 작성한다.

---

## 7. fixture

### fixture = 통제 변수

LLM 출력은 비결정적이다. 같은 모델, 같은 입력으로 돌려도 매번 조금씩 다른 결과가 나온다.

QA 프롬프트 v1 vs v2를 비교할 때, 비전도 매번 새로 돌리면 비전 설명이 달라져서 점수 차이의 원인을 특정할 수 없다. fixture로 비전 결과를 고정하면 차이는 순수하게 프롬프트 변경 효과만 반영한다.

|           | fixture 사용     | 풀 실행        |
| --------- | ---------------- | -------------- |
| 목적      | 변수 격리 비교   | 실제 품질 측정 |
| 비결정성  | 제거됨 (고정)    | 포함됨         |
| 쓰는 시점 | 설정 A vs B 비교 | 최종 성능 확인 |

### fixture JSON 구조

fixture에는 실험 조건(메타)과 실제 결과(데이터)를 함께 저장한다. 메타가 없으면 fixture를 갱신해야 하는지 판단할 수 없다.

```json
{
  "created_at": "2026-03-29T14:00:00",
  "dataset": "samsung-unboxing",
  "config": {
    "transcription_provider": "local",
    "whisper_model_size": "small"
  },
  "latency_ms": 45000,
  "data": [
    { "start": 0.0, "end": 3.2, "text": "안녕하세요" },
    { "start": 3.2, "end": 7.1, "text": "저는..." }
  ]
}
```

### 갱신 기준

- `transcription_provider`나 `whisper_model_size`를 바꿨다 → segments fixture 무효, 전사 재실행
- `vision_provider`, `vision_model`, 프롬프트를 바꿨다 → frame_analyses fixture 무효
- config 안 바꿨다 → 기존 fixture 그대로 사용

---

## 8. 프롬프트 관리

프롬프트는 **버전 단위**로 `app/prompts.py`에서 관리한다. 프롬프트 변형이 필요하면 새 버전을 등록한다.

생성·파이프라인용 프롬프트(`VISION_PROMPTS`, `QA_SYSTEM_PROMPTS`, `RERANK_DOC_TEMPLATES`)와 평가용 프롬프트(`EVAL_ANSWER_RELEVANCE_PROMPTS`, `EVAL_GROUNDEDNESS_PROMPTS`, `EVAL_RETRIEVAL_PRECISION_PROMPTS`, `EVAL_VISUAL_TEXT_ALIGNMENT_PROMPTS`) 모두 동일한 `{version: text}` dict + `CURRENT_*_VERSION` 포맷을 따른다.

```python
# app/prompts.py
VISION_PROMPTS = {
    "v1": "이 인터뷰 영상 프레임에서 무슨 일이 일어나고 있는지 한국어로 간결하게...",
    "v2": "This is a frame captured at {timestamp:.1f}s from an interview video. ...",
}
CURRENT_VISION_VERSION = "v2"

EVAL_ANSWER_RELEVANCE_PROMPTS = {
    "v1": "...",  # 수정 전 원본
    "v2": "...",  # 거부 답변 0.7, 동의어 규칙 추가
}
CURRENT_EVAL_ANSWER_RELEVANCE_VERSION = "v2"
```

호출부는 상수를 직접 참조하지 않고 getter(`get_vision_prompt`, `get_qa_system_prompt`, `get_eval_answer_relevance_prompt` 등)를 통한다. 버전 override가 필요하면 인자로 전달(`get_eval_groundedness_prompt("v1")`).

실험 결과 JSON에는 파이프라인 + 평가 프롬프트 7종의 버전 + 전문이 자동 기록된다:

```json
"prompts": {
  "vision": { "version": "v2", "text": "This is a frame captured at ..." },
  "qa_system": { "version": "v1", "text": "[역할] 너는 업로드된 ..." },
  "rerank_doc": { "version": "v1", "text": "[{start_time:.0f}s] {text}" },
  "eval_answer_relevance": { "version": "v2", "text": "당신은 답변 품질 평가자입니다 ..." },
  "eval_groundedness": { "version": "v2", "text": "당신은 근거성 평가자입니다 ..." },
  "eval_retrieval_precision": { "version": "v1", "text": "당신은 검색 품질 평가자입니다 ..." },
  "eval_visual_text_alignment": { "version": "v1", "text": "영상의 한 구간에서 ..." }
}
```

> **스키마 변경 주의**: 2026-04-12 이전 `evals/results/*.json`에서는 `eval_*` 항목이 `{version, text}` 형태가 아닌 flat string이었다. 결과 비교 스크립트를 작성할 때 두 스키마가 혼재할 수 있음을 고려한다.

---

## 9. 실험 결과 JSON

```json
{
  "label": "exp_baseline",
  "timestamp": "2026-03-29T14:00:00",
  "media_id": "abc-123",
  "dataset": "samsung-unboxing",
  "mode": "baseline",
  "changed": null,
  "target": "qa",
  "config": {
    "transcription_provider": "local",
    "whisper_model_size": "small",
    "openai_whisper_model": "whisper-1",
    "vision_provider": "local",
    "vision_model": "llava",
    "prompt_version": "v2",
    "frames_per_minute": 1,
    "embedding_provider": "local",
    "embed_model": "nomic-embed-text",
    "embedding_dim": 768,
    "chunk_window_seconds": 30.0,
    "chunk_overlap_seconds": 5.0,
    "chat_provider": "local",
    "chat_model": "llama3.1",
    "qa_prompt_version": "v1",
    "judge_provider": "local",
    "search_threshold": 0.5,
    "search_top_k": 5,
    "use_rerank": false,
    "rerank_model": "rerank-multilingual-v3.0",
    "rerank_top_n": 3,
    "search_pre_rerank_k": 15
  },
  "prompts": {
    "vision": { "version": "v2", "text": "..." },
    "qa_system": { "version": "v1", "text": "..." },
    "rerank_doc": { "version": "v1", "text": "..." },
    "eval_answer_relevance": { "version": "v2", "text": "..." },
    "eval_groundedness": { "version": "v2", "text": "..." },
    "eval_retrieval_precision": { "version": "v1", "text": "..." },
    "eval_visual_text_alignment": { "version": "v1", "text": "..." }
  },
  "latency_ms": {
    "transcribe": 39592,
    "vision_total": 18164,
    "embed_save": 3247,
    "qa_total": 94735
  },
  "qa_results": [
    {
      "test_id": "T1",
      "test_type": "단순사실",
      "query": "...",
      "answer": "...",
      "context_text": "...",
      "sources": [
        {
          "chunk_index": 4,
          "similarity": 0.892,
          "accepted": true,
          "text": "..."
        },
        {
          "chunk_index": 1,
          "similarity": 0.31,
          "accepted": false,
          "text": "..."
        }
      ],
      "metrics": {
        "answer_relevance": 0.5,
        "groundedness": 1.0,
        "retrieval_precision": 0.6
      },
      "latency_ms": 16410
    }
  ],
  "metrics": {
    "wer": null,
    "answer_relevance": 0.4917,
    "groundedness": 0.7333,
    "retrieval_precision": 0.6333
  }
}
```

---

## 10. 파일 구조

```text
evals/
├── CLAUDE.md                      # 이 문서
├── run_experiment.py              # CLI 엔트리포인트 — 파싱 → 계획 → 실행 → 저장
├── _common.py                     # 상수, config/prompt 스냅샷, fixture I/O, 타이밍
├── _planner.py                    # CLI 검증, 실행 계획 수립 (fresh/fixture/skip)
├── _stages.py                     # 단계별 실행 함수 (transcribe, vision, embed, qa)
├── datasets/
│   └── {영상이름}/
│       ├── source.mp4             # 원본 영상 (또는 심링크)
│       ├── questions.json         # 테스트 질문 세트 (타입별 5~7개)
│       └── reference.txt          # WER 비교용 정답 전사 텍스트
├── fixtures/                      # 중간 산출물 스냅샷 (자동 생성, config 메타 포함)
│   ├── segments_{dataset}.json
│   └── frame_analyses_{dataset}.json
└── results/                       # 실험 결과 JSON (자동 생성)
```

### 코드 구조 가이드

| 파일                | 역할                                                                | 수정 시점                         |
| ------------------- | ------------------------------------------------------------------- | --------------------------------- |
| `run_experiment.py` | 흐름만 담당. 단계 추가 시 여기에 분기 추가                          | 새 단계 추가, 결과 JSON 필드 변경 |
| `_planner.py`       | 실행 계획 로직. TARGET_REQUIREMENTS와 AFFECTS_DOWNSTREAM 참조       | 의존성 변경, 새 단계 추가         |
| `_stages.py`        | app/ 모듈을 호출하는 실행 함수. 각 함수는 `(결과, latency_ms)` 반환 | 파이프라인 단계의 입출력 변경     |
| `_common.py`        | 상수, 스냅샷, fixture/결과 I/O. 비즈니스 로직 없음                  | config 키 추가, fixture 포맷 변경 |

---

## 11. 버그 수정 이력

### evals → pipeline helper 재배선 (2026-04-19)

**배경**: `evals/_stages.py`가 app의 도메인 util(`transcribe_audio`, `analyze_frame_with_vision_model`, `chunk_segments`, `search_similar_segments` 등)을 직접 호출하면서 LangSmith에 `ingest.6_chunk`, `qa.2_vector_search` 같은 leaf run이 부모 없이 찍히는 고아 run 현상이 있었다. 또한 vision 분석이 evals에서는 직렬, pipeline에서는 4-worker 병렬로 돌아 latency 조건이 불일치했다.

**수정**:

- `evals/_stages.py`의 각 stage 함수를 `app/pipelines/ingest_pipeline._trace_transcribe` / `_trace_vision` / `_trace_embed` 및 `app/pipelines/qa_pipeline.run_qa` 호출로 교체.
- `_trace_*`는 원래 "pipeline 내부 private grouping helper"로 선언돼 있었는데, evals가 pipeline과 동일한 stage 경계를 쓰므로 예외 caller로 허용하도록 `.claude/rules/app-구조.md` §3과 `langsmith-관측.md` §4·§8 문구를 다듬었다. `_trace_*` 함수명은 유지 — prefix는 "자유롭게 재사용하지 말라"는 약한 경고로 계속 기능.
- correction과 `save_media_file`·`update_media_status` 호출은 evals 고유 metadata(`source="evals"`, config snapshot 포함)를 주입해야 해서 `run_embed_and_save` 안에 남겨 뒀다.
- audio/frames 임시 파일은 기존 `EVALS_DIR/temp_frames/{dataset}` 대신 `CONFIG.upload_dir`·`CONFIG.frames_dir` 아래 `eval_{uuid8}` 경로를 쓰고 finally 절에서 정리.

**결과물 JSON 변화**:

- `qa_results[].latency_ms` 유지.
- `qa_results[].latency_breakdown` 신규(`{embedding, retrieval, generation, total}`), `qa_results[].trace_id` 신규 — pipeline.run_qa가 반환하는 분해 latency와 LangSmith run id를 그대로 실어 준다.
- `frame_analyses` fixture의 각 항목에서 `latency_ms` 필드가 사라졌다(pipeline helper는 묶음 latency만 보고). fingerprint에는 영향 없음.

**남은 일**: `app/evaluation_utils.py:run_full_evaluation`은 아직 util을 직접 호출해서 `/evaluate` 엔드포인트의 고아 run은 그대로다. 별도 PR에서 같은 방식으로 `pipelines.qa_pipeline.run_qa`를 호출하도록 교체 예정.

### `--changed qa --dataset`에서 media_id=None 버그 (2026-04-04)

**증상**: `--changed qa --target qa --dataset interview`로 실행하면 QA가 sources=0, 컨텍스트 없이 돌아감.

**원인**: planner가 embed를 "fixture"로 잡는데, embed는 결과가 DB에만 존재하고 fixture 파일이 없었다. `run_experiment.py`에 embed fixture 분기가 없어서 media_id가 None인 채로 QA가 실행됨.

**수정**:

- `_common.py`: `FINGERPRINT_KEYS`에 `"media_id"` 추가 (upstream 전체 config 8개 키). `find_media_id_or_exit()` 함수 추가 — `results/`에서 동일 dataset + config fingerprint인 실험 결과를 찾아 media_id를 반환, 없으면 에러 + baseline 안내.
- `run_experiment.py`: `elif plan["embed"] == "fixture":` 분기 추가, `find_media_id_or_exit()` 호출.

**사용법 변화**: 기존에는 `--changed qa --target qa`를 쓰려면 반드시 `--media-id`를 직접 지정해야 했다. 이제 `--dataset`만 주면 이전 baseline 결과에서 media_id를 자동 탐색한다.

```bash
# 기존 (--media-id 직접 지정 필수)
pipenv run python evals/run_experiment.py --changed qa --target qa --media-id abc-123

# 수정 후 (--dataset으로도 가능 — results/에서 자동 탐색)
pipenv run python evals/run_experiment.py --changed qa --target qa --dataset samsung-unboxing
```
