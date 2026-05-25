# 실험 04 리포트: Whisper Prompt + Correction 조합 최적화

**날짜**: 2026-04-12  
**데이터셋**: coding-tutorial (3분 13초, 파이썬 강의 영상)  
**질문 수**: 5개 (비전질문 4 + 단순사실 1)

---

## 1. 실험 목적

Q1 ("영상에서 사용된 파이썬 내장 함수를 모두 나열해줘")에서 `print()` 함수가 답변에 포함되지 않는 critical 문제를 추적하고, 아래 두 가지 접근의 효과를 검증한다.

1. **Whisper `prompt` 파라미터**: 전사 시 Python 어휘 힌트를 주입해 음차 전사("프린트") 방지
2. **Correction prompt v1 → v2**: limiter guard reject 문제 해결 및 교정 품질 개선

---

## 2. 실험 조건 매트릭스

| # | 실험 ID | correction | correction prompt | whisper prompt | rerank |
|---|---------|-----------|-----------------|---------------|--------|
| A | `baseline_correction_off` | ✗ | — | ✗ | ✓ |
| B | `correction_v1_fresh` | ✓ | v1 | ✗ | ✓ |
| C | `correction_v2_fresh` | ✓ | v2 | ✗ | ✓ |
| D | `whisper_prompt_v1_correction_v1` | ✓ | v1 | v1 | ✓ |
| E | `whisper_prompt_v1_correction_v2` | ✓ | v2 | v1 | ✓ |

> 공통 고정 조건: TRANSCRIBE=openai/whisper-1, VISION=openai/gpt-4o-mini, EMBED=local/bge-m3, QA+JUDGE=openai/gpt-4o-mini

---

## 3. 전체 메트릭 비교

| 실험 | AR | GR | RP | 비고 |
|------|:---:|:---:|:---:|------|
| A. correction OFF | 0.94 | 0.82 | 0.40 | |
| B. correction v1 | 0.88 | 0.80 | 0.53 | guard reject 5건 발생 |
| C. correction v2 | 0.88 | 0.82 | 0.40 | |
| D. whisper v1 + correction v1 | 0.88 | 0.82 | 0.27 | guard reject 5건, 최저 RP |
| **E. whisper v1 + correction v2** | **0.88** | **0.94** | **0.53** | **guard reject 0건** |

> AR: Answer Relevance, GR: Groundedness, RP: Retrieval Precision

**최고 조합: E (whisper prompt v1 + correction v2)**  
GR +0.12 (0.82 → 0.94), RP +0.13 (0.40 → 0.53) — correction OFF 대비

---

## 4. 질문별 상세 비교

### T1 — 비전질문: "영상에서 사용된 파이썬 내장 함수를 모두 나열해줘"

| 실험 | AR | GR | RP | 답변 함수 수 |
|------|:---:|:---:|:---:|:---:|
| A. correction OFF | 1.0 | 1.0 | 0.0 | **4개** (input, split, int, len) |
| B. correction v1 | 0.7 | 1.0 | 0.0 | 2개 (input, split) |
| C. correction v2 | 0.7 | 0.7 | 0.0 | 2개 (input, split) |
| D. whisper v1 + correction v1 | 0.7 | 0.7 | 0.0 | 2개 (input, split) |
| E. whisper v1 + correction v2 | 0.7 | 1.0 | 0.0 | 2개 (input, split) |

**핵심 발견:**
- `print()`는 화자가 "프린트"로 발화 → Whisper가 한국어 음차로 정확 전사 → 모든 실험에서 context 미포함
- Whisper `prompt` 파라미터는 명확한 한국어 발화("프린트")는 override하지 못함 — 음차 전사 유지
- correction OFF(A)에서만 int, len이 답변에 포함됨. correction ON 전 실험에서 2개로 감소
- **correction이 int/len 관련 세그먼트를 trim하고 있을 가능성** — 교정 후 청킹 결과 확인 필요

### T2 — 비전질문: "total 변수의 초기값은 무엇인가?"

| 실험 | AR | GR | RP |
|------|:---:|:---:|:---:|
| A | 1.0 | 0.7 | 0.0 |
| B | 1.0 | 1.0 | 0.0 |
| C | 1.0 | 0.7 | 0.0 |
| D | 1.0 | 1.0 | 0.0 |
| **E** | **1.0** | **1.0** | **0.0** |

- AR/GR 안정적. RP=0.0은 rerank score가 낮아 관련 청크가 하위권으로 밀림.

### T3 — 비전질문: "영상 실행 화면에서 직접 입력한 숫자들은 무엇인가?"

| 실험 | AR | GR | RP |
|------|:---:|:---:|:---:|
| A | 0.7 | 0.4 | 1.0 |
| B | 0.7 | 0.7 | 1.0 |
| C | 0.7 | 0.7 | 0.67 |
| D | 0.7 | 0.7 | 0.67 |
| **E** | **0.7** | **0.7** | **1.0** |

- RP는 E에서 1.0 회복. GR 0.4(A)에서 0.7로 개선 — correction이 근거 충실도 기여.

### T4 — 단순사실: "점수를 입력받을 때 사용한 구분자는 무엇인가?"

| 실험 | AR | GR | RP |
|------|:---:|:---:|:---:|
| A | 1.0 | 1.0 | 0.67 |
| B | 1.0 | 0.9 | 1.0 |
| C | 1.0 | 1.0 | 1.0 |
| D | 1.0 | 0.7 | 0.67 |
| **E** | **1.0** | **1.0** | **1.0** |

- E에서 AR/GR/RP 모두 1.0. correction v2의 효과가 가장 명확한 질문.

### T5 — 비전질문: "평균을 계산하는 코드는 어떻게 작성되어 있는가?"

| 실험 | AR | GR | RP |
|------|:---:|:---:|:---:|
| A | 1.0 | 1.0 | 0.33 |
| B | 1.0 | 0.4 | 0.67 |
| C | 1.0 | 1.0 | 0.33 |
| D | 1.0 | 1.0 | 0.0 |
| **E** | **1.0** | **1.0** | **0.67** |

- GR 0.4(B, correction v1)에서 1.0으로 회복. correction v2가 코드 인용 정확도 개선.

---

## 5. Correction Guard 동작 분석

| 실험 | correction prompt | guard reject 수 | 영향 |
|------|-----------------|:--------------:|------|
| B | v1 | 5건 | 교정이 원문 대비 1.3배 초과 → 원문 유지. 교정 무력화. |
| C | v2 | 0건 | 전 세그먼트 교정 적용 |
| D | v1 | 5건 | B와 동일 문제 반복 |
| E | v2 | 0건 | 전 세그먼트 교정 적용 |

correction v1은 교정 결과가 지나치게 팽창(33자 → 85자, 22자 → 81자 등)해 limiter guard에 반복 reject됨. v2는 receive 비율 제한을 지키며 교정 적용.

---

## 6. Whisper `prompt` 파라미터 효과

**결론: 이 케이스에서는 효과 없음.**

| 항목 | 결과 |
|------|------|
| 파라미터 전달 | ✓ 정상 (결과 JSON `prompts.transcription.text` 확인) |
| 전사 변화 | ✗ "프린트" → "print" 미발생 |
| 원인 | 화자가 명확히 한국어 음차 "프린트"로 발화 → Whisper가 정확하게 전사 |

Whisper `prompt`는 발음이 모호한 전문 용어의 철자를 유도하는 용도다. 발화 자체가 한국어 음차인 경우에는 작동하지 않는다.

---

## 7. 미해결 과제

### 과제 1: `print()` context 미포함 (Critical)

- **원인**: "프린트" 음차 전사 → embedding 시 `print()`로 매칭 안 됨
- **시도**: Whisper prompt → 효과 없음
- **남은 방향**:
  - Correction prompt v3: 코드-음차 대응 명시 교정 지시
  - Vision → Code glossary 추출 → correction 주입
  - Embedding-time 음차 병기 ("프린트(print)")

### 과제 2: Correction ON 시 T1 답변 함수 수 감소 (4개 → 2개)

- correction OFF(A)에서만 int, len이 답변에 포함됨
- correction이 관련 세그먼트를 trim하거나 청킹 경계를 바꾸고 있을 가능성
- 교정 전/후 세그먼트 텍스트 diff 분석 필요

### 과제 3: T1/T2 RP=0.0 고착

- rerank score가 0.001~0.003 수준으로 낮아 관련 청크가 선별되지 않음
- search_threshold 조정 또는 rerank 없이 similarity-only 검색 실험 필요

---

## 8. 다음 실험 후보

| 우선순위 | 실험 | 목적 |
|:--------:|------|------|
| 1 | correction 전/후 세그먼트 diff 분석 | T1 함수 수 감소 원인 특정 |
| 2 | correction prompt v3 (코드-음차 교정 특화) | print() context 포함 시도 |
| 3 | rerank OFF + similarity-only | T1/T2 RP=0.0 원인 분리 |

---

## 부록: 소요 시간

| 실험 | transcribe | vision | embed | qa | 합계 |
|------|:----------:|:------:|:-----:|:--:|:----:|
| A (correction OFF) | 14.7s | 51.6s | 7.1s | 28.2s | ~102s |
| B (correction v1) | 13.5s | 53.4s | 5.8s | 26.7s | ~99s |
| C (correction v2) | 9.5s | 45.5s | 6.2s | 27.5s | ~89s |
| D (whisper+correction v1) | 10.2s | 47.7s | 6.3s | 31.5s | ~96s |
| E (whisper+correction v2) | 10.3s | 44.1s | 6.0s | 25.8s | **~86s** |

E가 전체 소요 시간도 가장 짧음 (correction v2가 v1 대비 교정 속도도 빠름).
