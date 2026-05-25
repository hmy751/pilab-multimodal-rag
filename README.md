# Multimodal RAG — 영상 질의응답 파이프라인 (공개용 정리본)

영상(음성 + 화면)을 입력받아 STT 전사와 화면 정보 추출을 결합하고, 하이브리드 검색·재순위로
질문에 답하는 멀티모달 RAG 파이프라인입니다.

> **공개 범위 고지**
> PI Lab 팀 스프린트(sprint-4, Track B 멀티모달 RAG)에서 진행한 작업을 기반으로 한 공개용 정리본입니다.
> 원본은 비공개 팀 레포라, 공개가 허가된 **코드만** 개인 레포로 옮겨 정리했습니다.
> 팀원 식별 정보·git 히스토리·제3자 영상/데이터는 포함하지 않습니다.
> 평가용 데이터셋은 제외되어 있어 `evals/`는 그대로 재현되지 않습니다(아래 "실행 방법" 참고).

---

## 1. 팀 프로젝트 맥락

- **과정**: PI Lab AI/ML 부트캠프 — Sprint 4 (Track B, 멀티모달 RAG), 2주 스프린트
- **팀**: 페어 프로그래밍 기반 팀 스프린트
- **미션 목표**: Sprint 3에서 만든 멀티모달 RAG 파이프라인을, 각 레이어(전사·화면 추출·청킹·검색·평가)의
  병목을 분리 검증하며 품질을 끌어올리는 것
- **베이스 파이프라인**(ingest → QA 전체 골격)은 팀 작업이며, 이 정리본은 그 위에서 진행한 Track B
  실험 기록과 공개 가능한 공통 코드 구조를 담습니다.

---

## 2. 담당 및 공개 정리 범위

팀 공통 파이프라인과 페어 실험 위에서, 실험 조건을 추적 가능하게 만들고 실패 원인을 레이어별로
분리해 읽을 수 있도록 정리하는 쪽을 주로 맡았습니다. 아래 표는 공개 코드 기준으로 남긴 담당 범위입니다.

| 영역 | 담당 / 정리한 일 | 남긴 결과 |
| --- | --- | --- |
| **실험 조건 / 재현성** | provider, model, chunk 설정을 분리하고 config snapshot에 남겨 결과 비교 기준을 정리 | 같은 결과가 어떤 조건에서 나왔는지 추적 가능 |
| **비전 실험 정리** | VLM 프롬프트·모델·샘플링 조건을 분리해 Before/After를 기록하고 비용 병목을 확인 | 비전 처리 비용이 주요 병목임을 확인, 모델 다운그레이드의 오답 failure mode 기록 |
| **시멘틱 청킹** | 고정 윈도우 청킹의 토픽 분절 문제를 확인하고, 임베딩 거리 기반 semantic chunking을 구현 | 일부 질문 개선과 함께 top_k 노이즈 유입 등 후퇴 조건도 기록 |
| **검색 / 평가 관측** | retrieval, LLM-as-Judge 결과를 실패 층 관점에서 해석하고 개선·후퇴 케이스를 분리 | 검색·평가 변경의 효과를 단일 점수가 아니라 원인 분석 단위로 정리 |
| **데모 / 하네스** | Next.js 데모 사이트와 ruff·black·detect-secrets pre-commit 구성 정리 | 실험 케이스 시각화 + 커밋 단계 자동 점검 |

> 실험에는 가설이 빗나간 사례도 포함됩니다(예: 비전 모델 다운그레이드 시 "확신 있는 오답" failure mode 발생,
> 시멘틱 청킹 도입 시 임베딩 토큰 한도 초과). 실패와 그 원인·교훈은 `docs/track-b/03-midweek/upgrade-report.md`에 정리돼 있습니다.
> 정량 수치는 페어/팀 실험 결과를 포함하며, 이 README는 그중 공개 가능한 코드와 담당한 정리·구현 범위를 중심으로 재구성했습니다.

---

## 3. 아키텍처 / 기술 스택

### 파이프라인

```text
[영상 입력]
   │
   ├─ ingest ──────────────────────────────────────────────
   │   transcription   STT 전사 (faster-whisper / OpenAI Whisper)
   │   vision          프레임 추출 + VLM 화면 정보 추출
   │   correction      화면 정보 기반 전사 후처리(선택)
   │   chunking        fixed window / semantic chunking
   │   multimodal      전사 + 화면 컨텍스트 결합·구조화
   │   embedding       임베딩 (Ollama 로컬 / OpenAI)
   │        │
   │        └─▶ Supabase (pgvector) 저장
   │
   └─ QA ──────────────────────────────────────────────────
       retrieval       벡터 검색 + 동적 threshold 폴백
       bm25            BM25 키워드 검색 (하이브리드)
       hyde            HyDE (가설 문서 임베딩)
       llm_rerank      LLM 기반 재순위
       chat            답변 생성
            │
            └─ evaluation_utils  LLM-as-Judge: AR / GR / RP + WER
```

- **AR** Answer Relevance · **GR** Groundedness · **RP** Retrieval Precision · **WER** Word Error Rate(전사 품질)

### 스택

- **백엔드**: Python 3.11, FastAPI, pipenv
- **검색/저장**: Supabase (pgvector), BM25 + 벡터 하이브리드, HyDE, LLM rerank
- **모델**(프로바이더 역할별 분리: 전사·비전·임베딩·채팅·평가 독립 설정)
  - 전사: faster-whisper(local) / OpenAI Whisper
  - 비전·채팅·평가: Ollama(local) / OpenAI
  - 임베딩: Ollama(local) / OpenAI
- **데모**: `demo-site/` — Next.js 정적 사이트(실험 케이스 시각화)
- **품질 게이트**: ruff, black, detect-secrets (pre-commit)

---

## 4. 실행 방법

### 백엔드

```bash
# 1) 의존성 설치
pipenv install

# 2) 환경 변수 준비 — .env.example을 복사해 키를 채웁니다
cp .env.example .env
#   기본값은 로컬 프로바이더(Ollama / faster-whisper) 기준이며,
#   OpenAI·Supabase·Cohere 등을 쓰려면 해당 키를 채웁니다.

# 3) 서버 실행
pipenv run uvicorn app.main:app --reload
```

### 데모 사이트

```bash
cd demo-site
pnpm install
pnpm dev
```

> **평가(`evals/`) 재현 안내**: 평가에 쓰던 데이터셋(원본 영상·전사·질문셋)은 제3자 저작물이라 공개 대상에서
> 제외했습니다. 따라서 `evals/`는 코드 구조 참고용으로만 두었고, 그대로는 재현되지 않습니다.
> 직접 확보한 영상과 질문셋으로 데이터셋을 구성하면 동일 흐름으로 실험을 돌릴 수 있습니다.

---

## 5. 결과 / 지표

- **Track B 대표 실험(비전 프롬프트 교체)**: 화면에만 표시되는 정보(코드·함수명 등)를 묻는 질문에서
  페어 실험 기준 통과율 **0/3 → 2/3**. 비전 프롬프트가 병목이었음을 변수 격리 실험으로 확인.
- **담당 정리/구현 범위**: config snapshot, provider 분리, semantic chunking 구현, 데모/하네스 정비를 통해
  실험 조건과 결과 해석 경로를 남겼습니다.
- 시멘틱 청킹·검색·Judge 관련 변경은 일부 질문에서 개선, 일부는 후퇴/유지로 혼재 —
  각 변경의 Before/After와 원인 분석은 `docs/track-b/03-midweek/upgrade-report.md` 참고.

> 수치는 스프린트 기간 내 수동/자동 측정 기록 범위에 한합니다. LLM 비결정성 때문에 일부 지표는 정성 판정과 함께 해석해야 합니다.
