# 실험 05 리포트: Vision 모델 업그레이드 (gpt-4o-mini → gpt-5.4)

**날짜**: 2026-04-18
**데이터셋**: coding-tutorial (3분 13초, 파이썬 평균 계산기 강의)
**질문 수**: 5개 (비전 4 + 단순사실 1)
**선행 실험**: [실험 04](../03-whisper-prompt-correction-v2/exp-report-04.md)

> **표기 안내** — 이 리포트에서 `실험 NN`은 **실험 시리즈 라벨**이며 숫자는
> 실험 순서를 뜻한다. 예: "실험 04 A 조건", "실험 05 Run 2" 등은 실험 식별자다.

---

## 1. 실험 목적과 맥락

### 실험 04에서 이어지는 Critical 문제

실험 04의 T1("영상에서 사용된 파이썬 내장 함수를 모두 나열해줘")에서 `print()`가 답변에 포함되지 않는 문제가 모든 실험(A~E)에서 반복됐다. 원인은 화자가 한국어 음차 "프린트"로 발화 → Whisper가 그대로 전사 → embedding 시 `print()`와 매칭 실패 → **context에 애초에 `print()`가 들어가지 않는 구조**.

실험 04 §7.1에서 제시한 남은 방향 3가지:
1. Correction prompt v3 (코드-음차 대응 교정)
2. **Vision → Code glossary 추출 → correction 주입**
3. Embedding-time 음차 병기

이번 실험은 위 2번 방향을 **가장 단순한 형태**로 검증한다: **더 좋은 vision 모델이 코드 OCR을 더 정확히 해서 `print()`를 frame description에 직접 담아낸다면, 전사의 음차 문제를 우회할 수 있는가?**

### 사용자 측 관찰

서버에서 같은 질문을 반복 호출했을 때:
- **gpt-5.4 vision** 설정: T1 정답(`print, input, split, int, len`)이 **약 1/2 확률로 나옴/안 나옴**
- **gpt-4o-mini vision** 설정(실험 04 기준): 반복해도 정답이 **거의 안 나옴**

이 관찰이 정량적으로 재현되는지, 차이가 무엇에서 오는지를 이번 실험에서 검증한다.

---

## 2. 실험 조건

변수 격리 원칙에 따라 **VISION 모델만** 교체. 나머지는 실험 04 A(baseline, correction OFF) 조건 유지.

| 항목 | 실험 04 A (baseline) | 실험 05 (이번 실험) |
|------|----------------------|----------------------|
| TRANSCRIBE | openai/whisper-1 | openai/whisper-1 |
| WHISPER_PROMPT | (none) | (none) |
| **VISION** | **openai/gpt-4o-mini** | **openai/gpt-5.4** |
| EMBED | local/bge-m3 | local/bge-m3 |
| QA (Chat) | openai/gpt-4o-mini | openai/gpt-4o-mini |
| JUDGE | openai/gpt-4o-mini | openai/gpt-4o-mini |
| CORRECTION | OFF | OFF |
| RERANK | ON (cohere rerank-multilingual-v3.0) | 동일 |

### n 설계

실험 04는 각 조건 n=1로 측정했다. 이번 실험에서는 **같은 조건을 2회(full fresh)** 돌려 분산을 직접 관찰한다. 이는 evals/CLAUDE.md의 "n=1 문제" 경고가 **다른 조건 간 비교뿐 아니라 같은 조건 반복에도 적용됨**을 확인하기 위함이다.

- Run 1: `exp_vision-gpt5-4-fresh_20260418_011250.json`
- Run 2: `exp_vision-gpt5-4-fresh-run2_20260418_012037.json`

---

## 3. 결과 — T1 집중 비교

### T1 답변 변화

| 실험 | Vision | 답변 함수 수 | 포함 함수 | AR | GR | RP |
|------|--------|:---:|:---|:---:|:---:|:---:|
| 실험 04 A (baseline) | gpt-4o-mini | 4 | input, split, int, len | 1.0 | 1.0 | 0.0 |
| 실험 04 E (최고조합) | gpt-4o-mini | 2 | input, split | 0.7 | 1.0 | 0.0 |
| **실험 05 Run 1** | **gpt-5.4** | **2** | **`print`, split** | 0.7 | 1.0 | 0.0 |
| **실험 05 Run 2** | **gpt-5.4** | **5** ✅ | **`print`, input, split, int, len** | 0.7 | 1.0 | 0.0 |

### 핵심 관찰

- **`print()` 누락 문제는 해결됐다.** 실험 04 A~E 모든 실험에서 답변에 없던 `print()`가 실험 05에서는 두 Run 모두 포함됨.
- **Run 2는 gold answer 5개를 정확히 열거**했다. 이는 실험 04가 해결하지 못한 Critical 문제의 첫 해결 사례.
- **T1 judge metric은 두 Run에서 동일(AR=0.7, GR=1.0, RP=0.0)**했다. 답변이 2개에서 5개로 확장됐음에도 채점이 바뀌지 않음. judge 자체의 enumeration 감도 이슈가 드러남(개선 대상).

### 분산 = 1/2

두 Run의 결과(2개 vs 5개)가 사용자가 서버에서 관찰한 "약 1/2 확률"과 정확히 일치한다. n=2로도 분산의 크기가 확인됨.

---

## 4. Vision 출력 구조 분석

### 4.1 양적 차이

frame_analyses fixture(10개 프레임) 비교:

| 지표 | gpt-4o-mini (실험 04) | gpt-5.4 (실험 05) | 배수 |
|------|:---:|:---:|:---:|
| 총 글자수 | 4,705 | 9,872 | **2.10×** |
| 평균 프레임당 | 471자 | 987자 | **2.10×** |
| 코드블록(```) 포함 프레임 | 10/10 | 10/10 | — |

### 4.2 내장함수 등장 일관성

프레임 10개 중 각 함수 호출이 description에 등장한 횟수:

| 함수 | gpt-4o-mini | gpt-5.4 | Δ |
|------|:---:|:---:|:---:|
| `print(` | 4/10 | **10/10** | **+6** |
| `int(` | 7/10 | **10/10** | +3 |
| `split(` | 7/10 | 9/10 | +2 |
| `input(` | 7/10 | 7/10 | 0 |
| `len(` | 6/10 | 6/10 | 0 |

- 가장 극적인 변화는 `print(`. gpt-4o-mini는 **중간 프레임(t=40s~120s)에서 `print` 언급이 전혀 없었으나**, gpt-5.4는 **모든 프레임에 일관되게 포함**.
- 청킹이 시간축(30초 window × 5초 overlap)으로 동작하므로, **어느 청크가 retrieve되더라도 `print`가 따라오는 상태**가 gpt-5.4에서 구조적으로 보장된다.

### 4.3 질적 차이 — 동일 시점(t=60s) 프레임 비교

**gpt-4o-mini (315자)** — 화면에 강조된 현재 코드만 캡처
```
[코드]
user_input_scores = input(...)
score_list = user_input_scores.split(",")
[키워드] input, split, 리스트, 구분, 함수
```

**gpt-5.4 (1,066자)** — 페이지 히어로 예시 + 본문 + 키워드 확장
```
[코드]
print("안녕하세요!")           ← OLD엔 없던 히어로 예시 코드
for i in range(5):
    print(f"숫자 {i}")
...
user_input_scores = input(...)
[키워드] print, for, i, range, f-string, split, input,
         user_input_scores, score_list, 리스트, 문자열, 함수, Python
```

gpt-5.4에서 새로 관찰된 3가지 행동:
- **페이지 맥락 스크랩**: 현재 뷰포트 밖 영역(스크롤 가능/사이드/헤더)까지 OCR로 가져옴.
- **히어로 예시 지속 캡처**: 페이지 상단의 `print("안녕하세요!")` 같은 기본 예시가 거의 모든 프레임에 반복 등장 → retrieval 보장성의 핵심.
- **식별자 보존 키워드 리스트**: 내장함수뿐 아니라 `user_input_scores`, `score_list` 같은 변수명까지 키워드 섹션에 포함 → embedding 유사도 계산에서 신호가 더 풍부해짐.

---

## 5. 전체 메트릭

| 실험 | AR | GR | RP |
|------|:---:|:---:|:---:|
| 실험 04 A | 0.94 | 0.82 | 0.40 |
| 실험 04 E (최고조합) | 0.88 | 0.94 | 0.53 |
| 실험 05 Run 1 | 0.88 | 0.92 | 0.33 |
| 실험 05 Run 2 | 0.88 | 0.78 | 0.47 |

- 전체 AR은 실험 04 A 대비 소폭 하락(0.94 → 0.88)했으나 **이는 T1 답변 길이 증가로 judge가 "필요 이상의 열거"로 판정한 것**으로 보인다(두 Run 모두 T1 AR=0.7).
- GR은 두 Run에서 0.78~0.92로 분산. RP도 0.33~0.47로 Run 간 차이가 큼 → **전체 메트릭도 n=1 비교가 어려움**을 재확인.

---

## 6. 해석 — 병목은 Vision → QA로 이동했다

### context에는 5개 함수가 전부 존재

Run 1의 T1 답변이 2개로 나왔을 때, QA가 실제로 본 `context_text`를 직접 점검:

```
'print'  → True   (코드 블록 `print("안녕하세요!")`)
'input'  → True   (코드 블록 `input("점수를...")`)
'split'  → True   (여러 곳)
'int('   → True   (코드 블록 `total += int(score)`)
'len('   → True   (코드 블록 `average = total / len(score_list)`)
```

vision이 만든 **키워드 리스트 자체**도 `print, for, i, range, f-string, input, ..., split, ..., int, ..., len`으로 5개 함수를 모두 명시하고 있었다.

### 즉, Run 1의 답변 누락은 retrieval/vision 책임이 아니다

- retrieval ✅ (13개 청크 중 accepted 3개 안에 관련 코드 다 존재)
- vision ✅ (gpt-5.4가 코드 OCR로 input/int/len 전부 description에 기록)
- **QA ✗** (context에 있는 함수를 "확인되지 않는 내용: ..."으로 버림)

### 병목 이동의 의미

실험 04까지 병목은 **"context에 `print()`가 들어오지 않는다"**는 **재료 공급 문제**였다. 실험 05에서 vision을 올리자 재료는 매번 충분히 공급된다. 남은 분산은:

- retrieval의 일부 흔들림(rerank score 0.001~0.003 수준)
- **QA 모델(gpt-4o-mini)의 열거 태스크 분산** — 같은 context에서도 "몇 개를 열거할지"가 실행마다 다름

이는 실험 전에는 "모델이 부족하다"로 해석하기 쉽지만, **시스템이 매 회 모델에게 동일한 추출 작업을 시키고 있다는 설계 문제**로 재정의된다.

---

## 7. 개선 방향 — 모델 올리지 않고 규칙성 확보

사용자가 "모델은 충분히 좋아졌다"고 판단한 전제에서, **같은 모델로 결정성을 끌어내는 레버** 4가지:

| # | 레버 | 예상 효과 | 비용 | 작업 위치 |
|:--:|------|:---:|:---:|------|
| 1 | `temperature=0` + `seed` 고정 | 중간 | 5분 | `app/chat_utils.py` OpenAI 호출부 |
| 2 | QA 프롬프트 **열거 전용 버전** + **JSON structured output** | 큼 | 30분 | `app/prompts.py`에 `v_enum` 등록 |
| 3 | Context에 **`[호출 목록]` 파생 섹션** 주입 (regex `\w+\(` 추출) | 가장 큼 | 1~2시간 | chunk 생성부 또는 QA 전처리 |
| 4 | Self-consistency (3회 sampling → 합집합/다수결) | 큼 | 지연 3배 | QA 호출부 |

### 레버별 상세

**레버 1 — temperature=0 + seed**
"규칙적"의 전제 조건. OpenAI는 `temperature=0, seed=42`로 95%+ 재현성 달성. 단, **결정성과 정답률은 별개** — 한 번의 답이 2개면 매번 2개가 반복될 수 있음.

**레버 2 — 열거 전용 프롬프트 + structured output**
현재 QA 시스템 프롬프트는 범용. 열거 쿼리에 다음 같은 지시를 추가:
```
context의 코드 블록에서 `name(...)` 패턴 호출을 모두 찾아라.
1) `\w+\(` 패턴 추출
2) Python 내장함수만 필터
3) 중복 제거 후 열거
출력: {"functions": [...], "evidence": [...]}
```
JSON structured output(`response_format={"type": "json_schema", ...}`)으로 "확인되지 않는 내용: ..." 꼬리로 답을 버리는 행동을 원천 차단.

**레버 3 — `[호출 목록]` 파생 필드 (가장 본질적)**
QA에게 **"추출까지 끝난 리스트"**를 주는 방법:
```python
calls_in_chunk = re.findall(r'([A-Za-z_]\w*)\s*\(', code_blocks)
```
청크 메타데이터에 `call_list: [print, input, split, int, len]`를 붙여 QA context에 `[이 청크에 등장한 함수 호출: ...]` 섹션 추가. QA의 작업이 **"열거"에서 "리스트에서 내장함수만 필터"로 단순화** → 열거 분산이 거의 0에 수렴. 병목을 **QA → 전처리**로 한 번 더 이동시키는 구조.

**레버 4 — Self-consistency**
비용은 크지만 **정답률 자체가 올라감** (Run 1 ∪ Run 2 = 5개 현상이 합집합 효과의 증거). 구현은 단순.

### 권장 조합

**레버 1 + 레버 3**을 우선 조합으로 제안:
- 레버 1은 기본 위생(무조건 먼저).
- 레버 3은 본질적 해결. vision이 만들어 준 풍부한 context에서 **열거 원재료를 QA 이전 단계에서 추출**해 버리면 QA 모델이 흔들릴 여지 자체가 사라짐.
- 레버 2는 레버 3과 효과가 일부 겹치므로, 3을 먼저 한 뒤 부족하면 2로 보완.

---

## 8. 다음 실험 후보

| 우선순위 | 실험 | 목적 |
|:--:|------|------|
| 1 | **레버 1 (temperature=0+seed) 적용 후 n=3 반복** | "규칙성"의 기준선 설정. 같은 답이 몇 %로 재현되는가 |
| 2 | **레버 3 (`[호출 목록]` 파생 섹션) + n=3 반복** | 열거 분산이 0에 수렴하는지 확인 |
| 3 | 레버 3 적용 상태에서 **gpt-4o-mini vision으로 롤백** | gpt-5.4 없이도 동등한 결과가 나오는지 (= vision 업그레이드 효과를 전처리가 대체할 수 있는가) |
| 4 | **Judge enumeration 감도 개선** — 답변 2개와 5개가 동일 score인 문제 | judge 프롬프트 또는 모델 교체 |

---

## 9. 프로세스 메타 — 이번 실험에서 배운 것

### n=1 경계는 "같은 조건 반복"에도 적용된다

첫 단일 실행에서 Run 1 결과(2개)를 보고 **"구조적 누락이니 재실행은 무의미하다"**고 단정하는 분석을 냈었다. 사용자의 "그래도 다시 돌려봐 달라"는 요청으로 Run 2를 돌려 5개가 나왔다. 이는:

- **evals/CLAUDE.md §3의 "n=1 문제"가 *조건 간* 비교뿐 아니라 *같은 조건 반복*에도 확장 적용되어야 함**
- LLM 열거 태스크는 **단일 실행으로 "할 수 있다/없다"를 판단하면 안 됨**
- 프롬프트·모델의 능력 평가는 항상 **n≥3 sampling 기반**으로 이뤄져야 함

### 실수 로그(이번 건)

- **단일 실행 과잉 해석** (실험 05): Run 1의 2개 답변을 보고 "QA 모델이 구조적으로 누락한다"로 성급히 결론. Run 2에서 5개가 나오면서 "분산이 클 뿐 능력은 있음"으로 수정됨. → 앞으로 같은 조건 최소 n=2, 가능하면 n=3 반복 후 결론.

---

## 10. 후속 실험: v3-cot QA 프롬프트 (n=1)

### 10.1 동기

§7의 권장 조합(레버 1+3)을 설계하던 중 "레버 3(regex로 코드 호출 추출해 context에 주입)은 코딩 튜토리얼 도메인에만 통하는 너무 specific한 해결이다"라는 피드백이 있었다.

이에 따라 **레버 2(열거 전용 프롬프트)의 원리**를 도메인 중립적 CoT로 일반화:

- **Collect → Curate → Compose** 3단계를 `<thinking>` 태그 안에서 수행하게 지시.
- "함수 호출" 같은 코딩 어휘 대신 "관련 항목"이라는 추상 레이어만 사용 → 인터뷰·제품 리뷰·요리 영상 등 모든 도메인에 일관 적용 가능.

`app/prompts.py`에 `QA_SYSTEM_PROMPTS["v3-cot"]` 신규 버전 등록 후 `CURRENT_QA_SYSTEM_VERSION = "v3-cot"`으로 갱신.

### 10.2 조건

| 항목 | 실험 05 Run 1/2 | v3-cot (이번) |
|------|:---:|:---:|
| VISION | openai/gpt-5.4 | 동일 |
| QA 프롬프트 | v1 | **v3-cot (신규)** |
| CORRECTION | OFF | OFF |
| RERANK | ON | ON |
| QA / JUDGE 모델 | gpt-4o-mini | gpt-4o-mini |

**실험 모드**: full fresh (`--target qa --dataset coding-tutorial --label qa-cot-v3-fresh`). media_id: `810b80cc-b30d-4386-b104-8f0c05575640`.

**엄밀성 한계 (명시)**: `--changed qa --media-id` 경로가 아니라 full fresh로 돌렸으므로 vision이 재실행되어 context가 실험 05 Run 2와 완전히 동일하지 않다. 따라서 "QA 프롬프트만 다른 순수 A/B"가 아니며, vision 비결정성이 섞여 있다.

### 10.3 결과 — 전체 메트릭

| 실험 | AR | GR | RP |
|------|:---:|:---:|:---:|
| 실험 04 A | 0.94 | 0.82 | 0.40 |
| 실험 05 Run 1 | 0.88 | 0.92 | 0.33 |
| 실험 05 Run 2 | 0.88 | 0.78 | 0.47 |
| **v3-cot (이번)** | **1.00** | **0.94** | **0.47** |

- **AR은 전 질문(T1~T5) 1.0 달성** — 실험 04/05 통틀어 처음.
- GR 0.94도 실험 05 최고치(Run 1의 0.92) 대비 상승.
- QA 소요 37.7s (실험 05 27~34s 대비 10% 증가) — `<thinking>` 블록 추가 생성에 의한 출력 토큰 증가로 추정.

### 10.4 T1 상세 — gold 기준 부분 불일치

| 실험 | T1 답변 |
|------|------|
| 실험 05 Run 2 (gold) | `print, input, split, int, len` |
| **v3-cot (이번)** | `split, print, range, int, len` |

5개를 열거했다는 점에서 judge는 AR=1.0 매겼지만 **`input` 누락 + `range` 오추가** 상태. `<thinking>` 블록을 보면 모델이 **수집(Collect) 단계에서 이미 `input`을 놓치고 있었다**.

**원인 추정**: coding-tutorial 영상에는 두 종류 코드가 함께 등장.
- **교육용 히어로 예시**: `for i in range(5): print(f"숫자 {i}")`
- **실제 평균 계산 코드**: `input(...)`, `total += int(score)`, `len(score_list)`

v3-cot은 수집 범위를 넓게 잡는 편향을 가지는데, 그 결과 히어로 예시의 `range`는 포착했지만 **실제 코드의 `input`을 다른 수집 항목으로 덮어버렸다**. "영상에 쓰인"의 해석 모호성이 CoT에서도 해결되지 않는다는 증거.

### 10.5 `<thinking>` 블록의 judge 오염 가능성 (Critical)

v3-cot 설계상 답변은 `<thinking>...</thinking>\n\n답변: ...` 구조로 생성된다. 이 블록이 후처리 없이 `qa_results[i].answer`에 그대로 저장됐고, judge는 이 답변 전체를 받아 채점했다.

즉 AR=1.00 상승의 원인이 다음 둘 중 어느 쪽인지 **현재 메트릭으로는 구분 불가**:

- (a) 실제 답변 본문 품질이 좋아진 것
- (b) `<thinking>` 안의 수집·정리 과정이 judge를 "근거가 명확함"으로 설득한 것

§9의 "같은 조건 반복 n=1 금지" 교훈에 이어, 본 실험은 **judge 입력 오염**이라는 별개의 리스크를 노출했다.

### 10.6 분산 미관측 (n=1)

현재 1회 실행 결과만으로 "안정적 1.00"인지 "우연히 1.00"인지 구분 불가. §9 교훈에 따라 n≥2 반복 필요하지만 후속 작업으로 미뤄둠.

### 10.7 다음 단계 (우선순위)

| # | 작업 | 목적 |
|:--:|------|------|
| 1 | **`<thinking>` 블록 후처리** — `app/qa/chat.py`에서 regex로 제거 후 본문만 저장 | judge 입력 오염 차단. AR=1.00이 (a)인지 (b)인지 분리 측정 가능해짐 |
| 2 | 후처리 적용 상태로 **n=3 반복** | 열거 분산 잡혔는지 확인. 실험 05의 "같은 조건 1/2 확률"이 v3-cot으로 해결됐는지 |
| 3 | T1 gold answer의 **"영상에 쓰인" 정의 명시** (`questions.json` 주석) | 히어로 예시 vs 실제 코드 경계를 문제 정의에서 해결 |
| 4 | 실험 05 권장 조합(레버 1: temperature=0+seed) 병행 | 남은 디코딩 분산 제거 |

---

## 11. 관련 파일

이 폴더(`experiments/04-vision-model-upgrade-gpt5-4/`):

| 파일 | 설명 |
|------|------|
| `exp-report-05.md` | 이 리포트 |
| `exp_vision-gpt5-4-fresh_20260418_011250.json` | 실험 05 Run 1 결과 JSON |
| `exp_vision-gpt5-4-fresh-run2_20260418_012037.json` | 실험 05 Run 2 결과 JSON |
| `exp_qa-cot-v3-fresh_20260418_041910.json` | **§10 v3-cot 실험 결과 JSON** |
| `frame_analyses_gpt4o-mini_04.json` | OLD vision fixture 스냅샷 (실험 04 기준) |
| `frame_analyses_gpt5-4_run2.json` | NEW vision fixture 스냅샷 (실험 05 Run 2 기준) |

외부 참조:
- 실험 04 리포트: [../03-whisper-prompt-correction-v2/exp-report-04.md](../03-whisper-prompt-correction-v2/exp-report-04.md)
- 실험 프로토콜: `.claude/rules/실험-프로토콜.md`
- evals 파이프라인: `evals/CLAUDE.md`
- v3-cot 프롬프트 원본: `app/prompts.py` `QA_SYSTEM_PROMPTS["v3-cot"]`

---

## 부록 — 소요 시간

| 실행 | transcribe | vision | embed | qa | 합계 |
|------|:---:|:---:|:---:|:---:|:---:|
| 실험 04 A (gpt-4o-mini vision) | 14.7s | 51.6s | 7.1s | 28.2s | ~102s |
| **실험 05 Run 1 (gpt-5.4 vision)** | 10.1s | **57.6s** | 6.8s | 34.0s | ~109s |
| **실험 05 Run 2 (gpt-5.4 vision)** | 14.3s | **61.3s** | 4.5s | 27.2s | ~107s |

gpt-5.4 vision은 프레임당 평균 5~6초로 gpt-4o-mini의 ~5초 대비 10~20% 느림. description이 2배 이상 길어진 점을 감안하면 토큰당 처리 속도는 오히려 빨라진 셈.

---

## 부록 — baseline 복원 상태

### 실험 05 vision 업그레이드 실험 (§1~§9)

실험 후 복원 완료 (실험-프로토콜 §3):

- `.env`의 `OPENAI_VISION_MODEL` → 일시적으로 `gpt-4o-mini`로 복원 후, 후속 §10 실험을 위해 다시 `gpt-5.4`로 재설정.
- `evals/fixtures/*.backup-pre-gpt54.json` 2개는 실험 04 fixture 보호 목적으로 남겨둠. 이후 실험 04 조건 재현 실험에서 필요시 복원 사용.

### 후속 §10 실험 (v3-cot) — 복원 지연

다음 항목은 **본 리포트 작성 시점 기준 baseline으로 복원되지 않은 상태**다. 후속 실험(§10.7 다음 단계)을 이어서 돌리기 위해 의도적으로 유지.

- `.env`의 `OPENAI_VISION_MODEL = "gpt-5.4"` (실험 04 baseline은 `gpt-4o-mini`)
- `app/prompts.py`의 `CURRENT_QA_SYSTEM_VERSION = "v3-cot"` (실험 04 baseline은 `v1`)

§10.7 작업을 마무리한 뒤 두 항목을 일괄 복원하여 실험 04 baseline 재현 가능한 상태로 되돌린다.
