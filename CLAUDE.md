# 프로젝트 하네스

> Sprint 3 멀티모달 파이프라인을 실 서비스 수준으로 고도화하는 프로젝트.
> AI 에이전트와 개발자 모두가 따르는 운영 규칙.

---

## 0. 현재 상태 (2026-04-20~)

- **evals/ 동결**: 내부 버그로 `evals/`는 실행·호출·참조·수정 **모두 금지**. 데이터(`evals/results/`, `evals/fixtures/`, `evals/datasets/`)는 **보존**하되, 코드를 읽거나 문서에서 참조하지 않는다.
- 실험이 필요하면 노트북/스크립트로 별도 진행하고 `evals/`는 건드리지 않는다.
- 동결 해제 시 이 섹션을 삭제하고 아래 규칙의 evals 항목을 복원한다.

---

## 1. 하네스 구조

이 프로젝트의 하네스는 두 축으로 구성된다.

- **Guide** — 행동 전에 방향을 잡는다. 이 문서(CLAUDE.md)와 하위 문서가 담당.
- **Sensor** — 행동 후에 관찰하고 교정한다. pre-commit hook, 린터, 에이전트 스캔이 담당.

CLAUDE.md는 advisory다 (~80% 준수율). **반드시 지켜야 할 것은 hook이나 린터로 강제한다.**

### 문서 계층

| 위치                  | 역할                         | 로드 시점         |
| --------------------- | ---------------------------- | ----------------- |
| `CLAUDE.md` (이 문서) | 프로젝트 전체 규칙           | 항상              |
| `.claude/rules/*.md`  | 도메인별 규칙 (paths 조건부) | 해당 경로 작업 시 |

### Guide 하위 문서

| 파일                              | 대상 경로     | 역할                                     |
| --------------------------------- | ------------- | ---------------------------------------- |
| `.claude/rules/config-규약.md`    | `app/**`      | Stage Config, 호출 규약, Override        |
| `.claude/rules/code-style.md`     | `app/**`      | Fowler 리팩토링 기준 코드 품질           |
| `.claude/rules/app-구조.md`       | `app/**`      | route/pipeline/util 3층, 폴더·명명 규칙  |
| `.claude/rules/langsmith-관측.md` | `app/**`      | `@traceable` 이름·run_type·부착 규칙     |

> `실험-프로토콜.md`는 `evals/` 동결 기간 동안 비활성. 동결 해제 시 복원.

### Sensor

| 도구                | 역할             | 강제력                        |
| ------------------- | ---------------- | ----------------------------- |
| **black**           | 코드 포맷        | pre-commit hook               |
| **ruff**            | 린터             | pre-commit hook               |
| **detect-secrets**  | 시크릿 탐지      | pre-commit hook               |
| **harness-scanner** | 하네스 위반 스캔 | 에이전트 (수동 호출)          |
| **테스트**          | 기능 검증        | 수동 실행 (CI 구축 시 자동화) |

---

## 2. 원칙

규칙의 배경. 개별 규칙이 왜 존재하는지 판단할 때 이 원칙으로 돌아온다.

1. **변경에는 맥락이 따라다닌다** — 무엇을 바꿨는가뿐 아니라 왜 바꿨는가를 남긴다. 커밋 메시지, 실험 label, 코드 주석 모두 해당. 3주 후에 돌아왔을 때 의도를 복원할 수 있어야 한다.

2. **기록 = 실행** — 기록된 값(snapshot, 로그)과 실제 실행된 값이 반드시 일치해야 한다. 기록만 하고 제어하지 않으면 "양다리" 버그가 생긴다.

3. **점진적 강화** — 하네스는 처음부터 완벽할 필요 없다. 같은 실수가 반복되면 그때 규칙을 추가한다. 한 번의 불편으로 규칙을 만들지 않는다.

4. **"빼면 실수하는가?"** — 이 문서의 모든 항목은 이 질문을 통과해야 한다. 코드를 읽으면 알 수 있는 것, 이미 hook이 잡아주는 것은 여기 쓰지 않는다.

---

## 3. 환경

- **의존성**: `Pipfile` 관리. `pipenv run`으로 실행. `pip install` 직접 설치 금지.
- **환경 변수**: `.env`가 `config.py` 기본값을 오버라이드한다. 코드만 보면 안 되고 실제 로드된 값을 확인해야 한다.
- **Python**: 3.11

---

## 4. 절대 금지

위반 시 즉시 멈추고 수정한다.

- API 키·시크릿을 코드에 하드코딩하지 않는다 → `.env`로만
- 함수 시그니처에 `CONFIG.xxx`를 default로 넣지 않는다 → lazy lookup (`config-규약` 참조)
- `evals/` 전체(코드·results·fixtures)를 삭제·수정하지 않는다 → 동결 중, 이력 보존
- 프롬프트를 코드 본문에 하드코딩하지 않는다 → `app/prompts.py` 버전 관리
- 동작 변경과 리팩토링을 한 커밋에 섞지 않는다
- `print()`로 디버깅하지 않는다 → `logging` 사용

---

## 5. 규칙

### 프로젝트 공통

1. **환경 복원** — 실험용으로 변경한 config, .env, prompts는 작업 완료 후 baseline으로 되돌린다.

### Hook 승격 후보

아래는 advisory 규칙이지만, 위반 시 비용이 크므로 hook으로 강제하는 것을 검토한다.

| 규칙                            | 구현 방법                                     | 상태          |
| ------------------------------- | --------------------------------------------- | ------------- |
| `--no-verify` 커밋 차단         | `.claude/settings.json` deny                  | **적용 완료** |
| `.env`, `credentials` 커밋 방지 | pre-commit hook (detect-secrets)              | **적용 완료** |
| fixture 수동 편집 감지          | PreToolUse hook으로 fixtures/ 경로 Write 차단 | **적용 완료** |

---

## 6. 냄새 신호

아래 상황이 보이면 멈추고 확인한다.

- 같은 작업을 두 번 했는데 결과가 다르다 → **환경 오염** (.env drift, config 미복원)
- 변경의 이유를 한 문장으로 설명할 수 없다 → **맥락 누락**
- 매직 넘버가 코드에 반복된다 → **상수 추출 필요** (code-style 참조)
- 이 문서가 길어지고 있다 → **분리 시점** (`.claude/rules/`로 이동)

---

## 7. 작업 루프

매 작업에서 도는 질문. 규칙이 특정 상황만 잡는다면, 질문은 비슷한 모든 상황에서 사고를 유도한다.

### 작업 전

- 이 작업에 필요한 맥락과 파일을 충분히 봤는가?
- 이 작업의 영향 범위가 어디까지인가? (app만? config도?)
- 현재 환경(config, .env)이 의도한 상태인가?

### 작업 중

- 이 변경을 3주 후에 다시 보면, 왜 이렇게 했는지 알 수 있는가?
- 여러 선택지가 있었다면 왜 이걸 골랐는지 남겼는가?
- 이 코드가 import-time에 평가되는 값에 의존하고 있지 않은가?

### 작업 후

- 이 변경이 다른 파일이나 레이어에 영향을 주는가?
- 환경이 baseline으로 복원됐는가?
- 누락된 것은 없는가?

---

## 8. 디렉토리 구조

```
project-root/
├── CLAUDE.md                   # 이 문서
├── .claude/
│   ├── settings.json           # 권한/hook 설정
│   ├── rules/                  # 도메인별 규칙 (조건부 로드)
│   │   ├── config-규약.md
│   │   ├── 실험-프로토콜.md
│   │   └── code-style.md
│   └── agents/                 # 에이전트 정의
│       └── harness-scanner.md
├── .pre-commit-config.yaml     # black + ruff + detect-secrets
├── .env                        # 환경 변수 (stage별 구성)
├── .env.example                # .env 템플릿 (기본값 = local provider)
├── Pipfile
├── app/                        # 애플리케이션 코드
│   ├── config.py
│   ├── prompts.py
│   └── ...
├── evals/                      # 실험 자동화 (동결 — 참조·수정 금지)
│   └── ...
├── experiments/                # 실험 리포트
└── docs/
```

---

## 이 문서의 유지보수

- **추가 기준**: 같은 실수가 2회 이상 반복됨 / 한 번의 실수 비용이 큼 / 합의된 기준이 있음
- **추가 금지**: 특정 세션에서만 유효한 취향 / 이미 hook이 잡아주는 것 / 코드를 읽으면 알 수 있는 것
- **분리**: 특정 폴더 작업 시에만 필요하면 → `.claude/rules/` + paths. 매 작업마다 필요하면 → 여기.
- 배경/근거는 줄 수와 무관하게 유지한다. "하라/하지 마라"만 남기면 다른 맥락에서 오해된다.

---

## 실수 로그

> 실수가 발생하면 아래에 한 줄씩 추가한다.
> 처음부터 채우려 하지 않는다. 실패할 때 쌓는 것이다.
> 같은 실수가 2회 반복되면 위의 규칙이나 냄새 신호로 승격한다.

- **provider 유령 필드**: 역할별 provider 5개로 분리했지만 기존 `Config.provider` 필드를 제거하지 않아 `embedding_dim`이 잘못된 provider를 참조. snapshot의 `is_local`도 transcription provider 하나로 전체 stage를 판단하는 버그 발생. → provider 제거, embedding_dim을 모델 기준으로 수정, snapshot stage별 provider로 전환.
- **LangSmith orphan root**: `@traceable`이 붙은 `analyze_frame_with_vision_model`을 `ThreadPoolExecutor` 워커에서 호출했는데, 워커 스레드가 메인의 contextvars를 상속하지 않아 부모 run(`ingest.vision`)을 못 찾고 각 호출이 독립 루트로 찍힘. `ingest.vision` 465s인데 자식은 `ingest.3_extract_frames` 6s만 보이는 459s 갭으로 발견. → `get_current_run_tree()`로 메인에서 부모 캡처 후 각 워커 호출에 `langsmith_extra={"parent": parent_run}`로 명시 전달.
