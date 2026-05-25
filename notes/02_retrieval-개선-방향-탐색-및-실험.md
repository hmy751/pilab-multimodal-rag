# Retrieval 개선 방향 탐색 및 실험 기록

> 꽁꽁이 영상(media_id: `e93b78a5-a663-4261-99a8-ccf141ed40f6`) 쿼리
> "꽁꽁이가 처음 발견된 연도와 상황은 무엇인가요?"를 기준 케이스로 삼아
> 여러 개선안을 순차 실험한 기록. 기대 답변: **"2021년 겨울, 한파로 꽁꽁
> 얼어붙은 한강 위를 걷고 있었음"** (정답 청크 = chunk 0)

---

## 1. 문제 재정의 — 3층 실패

Hybrid Retrieval 도입 후에도 꽁꽁이 쿼리 해결이 안 됐을 때, 실패 원인이 **검색 파이프라인의 세 층 모두에서 동시 발생**한다는 게 드러남.

| 층 | 실패 이유 |
|---|---|
| **Vector** | chunk 0에 "꽁꽁이" 토큰 없음. "고양이"로만 지칭 → semantic 유사도 낮음 (0.207) |
| **BM25** | 쿼리 "꽁꽁이가" ≠ 청크 "꽁꽁" (조사 "이가" 붙음). 쿼리에 "2021" 같은 희귀 키워드도 없음 → bm25_score 거의 0 |
| **Rerank (Cohere)** | "꽁꽁이 ↔ 고양이" alias를 cross-encoder도 해결 못함. rerank 점수 0.002~0.009로 수렴 |

세 층 공통 원인: **"쿼리의 고유명사(꽁꽁이)가 정답 청크의 지시어(고양이/녀석)와 같은 대상임을 알 방법이 없다"**

---

## 2. 개선 방향 선택지 정리

실패 원인별로 후보 나열하고 **답안 유출 여부 · 효과 범위 · 비용**으로 분류.

### 2.1 답안 유출 있음 (실험 제외)

- **영상 요약/제목을 쿼리 확장에 주입** — "이 영상은 한강 고양이 얘기"라고 알려주고 검색하는 건 정답을 알려주고 찾는 것. 평가 관점에서 부적절

### 2.2 답안 유출 없음 (쿼리만 보고 재구성 or 인덱싱 시점 작업)

1. **HyDE (Hypothetical Document Embeddings)** — 쿼리를 LLM에 넣어 영상 내용을 모르는 상태에서 상상한 가상 답변 생성, 그것을 임베딩해 검색. 쿼리-청크 간 어휘/문체 격차 줄이는 효과
2. **Chunk enrichment (인덱싱 시점)** — 인덱싱할 때 각 청크 앞에 video-level 메타(제목, 요약)를 prefix로 붙여 임베딩. 재인덱싱 비용 있지만 모든 쿼리에 구조적 혜택. 쿼리 시점 추가 비용 0
3. **BM25 hybrid** — 키워드 매칭으로 vector가 놓치는 고유 토큰 포착. 이미 Hybrid로 구현
4. **LLM re-rank over wide pool** — pool을 넓히고 top-N을 LLM이 판정. 의미 이해로 alias 해결. 쿼리당 LLM 추가 호출
5. **Query paraphrasing (context-free)** — 영상 본 적 없는 LLM이 쿼리만 바꾸기. recall 개선 폭 제한적
6. **조사 제거 토큰화 / 형태소 분석** — 한국어 BM25 recall 개선. 명사+조사 매칭만 조사 제거로도 가능, 동사/형용사 활용은 형태소 분석 필요. 의존성 vs 효과 trade-off

### 2.3 Cross-encoder rerank 대체 후보 (Cohere 대안)

쿼리에 직접 답이 되진 않지만 Cohere 탈출용 시스템 선택:

| 서비스/모델 | 성격 | 한국어 | 특징 |
|---|---|---|---|
| Jina Reranker v2 | API | ◎ | Cohere와 가장 유사한 교체 |
| Voyage AI rerank-2 | API | ○ | 품질 좋음, 비싸 |
| BGE-reranker-v2-m3 | 오픈소스 self-host | ◎ | 다국어 강함, ~2GB |
| Dongjin-kr/ko-reranker | 오픈소스 self-host | ◎ | 한국어 특화 |

**중요한 현실**: 위 옵션들은 전부 cross-encoder 계열이라 **"꽁꽁이 ↔ 고양이" alias를 해결하는 본질적 차이가 없다**. 이 케이스엔 **LLM rerank**가 맞는 방향.

---

## 3. Decision Tree (HyDE 후 실패 시 분기)

```
HyDE 적용
 │
 ├─ 해결됨 → 종료
 │
 └─ 실패 → chunk 0이 search pool에 들어왔나?
            │
            ├─ 들어왔는데 rerank가 못 뽑음 → rerank_top_k 증가 시도 → LLM rerank
            │
            ├─ 들어왔는데 rerank top-3 밖에 다른 게 우세 → LLM rerank
            │
            └─ 아예 pool 밖 → chunk enrichment (인덱싱 개선)
```

형태소 분석은 "꽁꽁이 쿼리가 아닌 다른 유형(쿼리-청크에 공통 단어 있는데 조사 때문에 BM25 miss)"에 효과 있음. 꽁꽁이 케이스 특화 해결책 아님.

---

## 4. 실험 기록

### 공통 Config (모든 실험에서 동일)

| 필드 | 값 |
|---|---|
| `transcription_provider` | openai |
| `openai_whisper_model` | whisper-1 |
| `vision_provider` | openai |
| `openai_vision_model` | gpt-4o-mini |
| `embedding_provider` | openai |
| `openai_embedding_model` | text-embedding-3-small |
| `embedding_dim` | 1536 |
| `chunk_window_seconds` | 20.0 |
| `chunk_overlap_seconds` | 5.0 |
| `chat_provider` | openai |
| `openai_chat_model` | gpt-4o-mini |
| `qa_prompt_version` | v3-cot |
| `top_k` (retrieval) | 3 |
| `search_threshold` | 0.3 |
| `use_rerank` | True |
| `rerank_pool_size` | 15 |

Media: 꽁꽁이 영상 (28개 청크)

---

### 실험 0 — Baseline (Hybrid 없음, Vector-only)

> 개선 전 기준선. 최초 진단 시 관측.

**Config (기준선 시점):**

| 필드 | 값 |
|---|---|
| `use_hybrid` | (미구현) |
| `use_hyde` | (미구현) |
| `rerank_provider` | cohere (당시 유일 옵션) |
| `rerank_model` | rerank-multilingual-v3.0 |
| `rerank_top_k` | 3 |

**결과:**

- **chunk 0 (정답) 상태**: vector sim = **0.2071**, 전체 랭킹 **19위**
- `rerank_pool_size`=15로 인해 chunk 0은 **pool에 진입조차 못함**
- Cohere rerank top-3: chunk 22, 8, 18 (rerank 점수 0.009, 0.005, 0.002)
- chunk 0 accepted: **False**
- 최종 답변: "제공된 영상/전사에서 확인되지 않습니다"

**배운 것:** 기본 vector search가 recall 단계에서 이미 실패. threshold 조정이나 rerank 튜닝으로 해결 불가 (pool 밖이라 건드릴 방법 없음).

---

### 실험 A — Hybrid Retrieval 도입 (BM25 + RRF)

> commit `c9863e3` 시점. Vector 단독에서 BM25 병렬 + RRF fusion 추가.

**Config:**

| 필드 | 값 |
|---|---|
| `use_hybrid` | **True** (신규) |
| `hybrid_rrf_k` | 60 |
| `hybrid_bm25_top_k` | 30 |
| `use_hyde` | (미구현) |
| `rerank_provider` | cohere |
| `rerank_model` | rerank-multilingual-v3.0 |
| `rerank_top_k` | 3 |
| `rerank_pool_size` | 15 |

**실행 로그:**

```
[hybrid] use_hybrid=True use_rerank=True vec_limit=15 bm25_top_k=30
[hybrid] vector top-15 (first 5): [chunk=25 sim=0.483, chunk=13 sim=0.402,
         chunk=10 sim=0.393, chunk=22 sim=0.372, chunk=12 sim=0.367]
[bm25] corpus=28개 청크, query_tokens=['꽁꽁이가', '처음', '발견된',
       '연도와', '상황은', '무엇인가요']
[bm25] top-28 (first 5): [chunk=24 score=2.575, chunk=23 score=1.999,
       chunk=0 score=0.000, chunk=1 score=0.000, chunk=2 score=0.000]
[rerank] 28개 → 3개 선별 (scores: ['0.009', '0.005', '0.002'])
[retrieve] accepted=3개: ['chunk=22', 'chunk=8', 'chunk=18']
```

**결과:**

- chunk 0: vector sim **0.207 (동일)**, BM25 **0.000**, RRF rank **17** (rrf=0.0159)
- BM25가 0인 이유: "꽁꽁이가" ≠ "꽁꽁" (조사), 그리고 쿼리에 "2021"/"한강" 같은 희귀 토큰 없음
- chunk 0 **pool에는 진입**했지만 RRF 하위권 → Cohere rerank가 top-3에 안 뽑음
- chunk 0 accepted: **False** (여전)

**배운 것:** 구조는 정상 동작. Pool 확장 효과는 있지만 이 쿼리에선 BM25가 무력(조사 문제). 병목이 rerank 층으로 이동.

---

### 실험 B — HyDE 추가 (쿼리 임베딩 교체)

> commit `6452d5c` 시점. 쿼리 대신 "가상 답변"을 임베딩.

**Config:**

| 필드 | 값 |
|---|---|
| `use_hybrid` | True |
| `hybrid_rrf_k` | 60 |
| `hybrid_bm25_top_k` | 30 |
| `use_hyde` | **True** (신규) |
| `hyde_prompt_version` | **v1** (신규) |
| `rerank_provider` | cohere |
| `rerank_model` | rerank-multilingual-v3.0 |
| `rerank_top_k` | 3 |
| `rerank_pool_size` | 15 |

**HyDE 가상 답변 (LLM 생성, 영상 내용 모름):**

```
꽁꽁이는 1985년, 한 겨울밤 강원도 평창의 얼어붙은 호수에서 얼음 낚시를
하던 어부에 의해 우연히 발견되었습니다. 당시 그는 얼음 속에서 이상한
생명체를 발견하고 신기해하며 조심스럽게 꺼내봤던 것으로 전해집니다.
```

→ "겨울", "얼어붙은" 등 chunk 0과 공통되는 어휘 포함. 영상 실제 연도·장소는 모름.

**실행 로그:**

```
[hyde] query='꽁꽁이가 처음 발견된 연도와 상황은 무엇인가요?'
       prompt_version=v1
[hyde] hypothetical='꽁꽁이는 1985년, 한 겨울밤 강원도 평창의...'
[hybrid] vector top-15 (first 5): [chunk=13 sim=0.542, chunk=12 sim=0.508,
         chunk=9 sim=0.452, chunk=25 sim=0.437, chunk=18 sim=0.416]
[rrf] fused 28개 (first 5): [chunk=24 rrf=0.0305, chunk=0 rrf=0.0304,
      chunk=9 rrf=0.0298, chunk=13 rrf=0.0296, chunk=12 rrf=0.0295]
[rerank] 28개 → 3개 선별 (scores: ['0.009', '0.005', '0.002'])
[retrieve] accepted=3개: ['chunk=22', 'chunk=8', 'chunk=18']
```

**결과:**

| 지표 | Before HyDE (실험 A) | After HyDE (실험 B) |
|---|---|---|
| chunk 0 vector sim | 0.207 (rank 19) | **0.373 (rank 2)** |
| chunk 0 RRF 순위 | 17 (rrf=0.0159) | **1 (rrf=0.0304)** |
| chunk 0 pool 진입 | ✓ | ✓ |
| chunk 0 accepted | ✗ | ✗ (여전) |

- Vector recall 크게 개선. chunk 0이 RRF 최상위로
- 그러나 Cohere rerank는 여전히 top-3로 chunk 22, 8, 18 선택. 정답 제외
- 최종 답변: "발견 연도에 대한 정보는 확인되지 않습니다" (여전)

**Latency:** hyde 3232ms, embedding 1549ms, retrieval 2517ms, generation 4654ms, **total 11952ms**

**배운 것:** HyDE가 vector recall을 극적으로 올렸지만 병목이 **Cohere rerank**로 완전히 이동. Cohere cross-encoder 자체 한계가 드러남.

---

### 실험 C — rerank_top_k 증가 시도 (3 → 5 → 7)

> Cohere 탈출 전 "더 싼 방법"부터 시도. `rerank_top_k`를 늘려 chunk 0이 확장된 범위엔 들어오는지 확인.

**Config (실험 C-1 ~ C-3 공통, top_k만 변경):**

| 필드 | 값 |
|---|---|
| `use_hybrid` | True |
| `hybrid_rrf_k` | 60 |
| `hybrid_bm25_top_k` | 30 |
| `use_hyde` | True |
| `hyde_prompt_version` | v1 |
| `rerank_provider` | cohere |
| `rerank_model` | rerank-multilingual-v3.0 |
| `rerank_top_k` | **3 / 5 / 7** (실험 변수) |
| `rerank_pool_size` | 15 |

**결과:**

| rerank_top_k | Cohere가 뽑은 청크 | chunk 0 포함? |
|---|---|---|
| 3 | [22, 8, 18] | ✗ |
| 5 | [22, 8, 18, 6, 11] | ✗ |
| 7 | [22, 8, 18, 6, 11, 14, 21] | ✗ |

**Cohere rerank 점수 분포 (top_k=7 시):**

```
[0.009, 0.005, 0.002, 0.002, 0.002, 0.002, 0.002]
```

3번째부터 **0.002로 완전히 수렴**. Cohere 자신도 "3위 밖은 다 별 차이 없다"고 판단하고 있음. 그 "별 차이 없는 군" 안에서도 chunk 0은 아예 제외.

**배운 것:** rerank_top_k를 10, 20으로 올려도 같은 결과일 가능성 높음. **Cohere cross-encoder가 "꽁꽁이 ↔ 고양이" alias를 근본적으로 해결 못한다**는 게 확정. 다른 접근 필요.

부가 관찰: HyDE 가상 답변이 매 호출마다 달라서 vector ranking이 요동침 (chunk 0이 top-1이 될 때도 있고 rank 5일 때도 있음). HyDE 분산 이슈 존재.

---

### 실험 D — LLM rerank 도입 (rerank_provider 스위치)

> commit `61781c5` 시점. Cohere 대신 listwise LLM rerank 도입. `rerank_provider` env var로 "llm"/"cohere" 선택.

**Config:**

| 필드 | 값 |
|---|---|
| `use_hybrid` | True |
| `hybrid_rrf_k` | 60 |
| `hybrid_bm25_top_k` | 30 |
| `use_hyde` | True |
| `hyde_prompt_version` | v1 |
| `rerank_provider` | **llm** (신규, 기본값) |
| `llm_rerank_prompt_version` | **v1** (신규) |
| `rerank_top_k` | 3 |
| `rerank_pool_size` | 15 |

**LLM rerank 프롬프트 (v1):**

- listwise 방식. pool 내 모든 후보(28개)를 한 번에 LLM에 넣음
- 각 청크는 `[chunk_index] (start=Xs) 텍스트` 형태. 텍스트는 200자 cutoff
- 출력: `{"ranked_indices": [상위 top_k개 chunk_index]}` JSON
- OpenAI `response_format={"type": "json_object"}` 사용

**실행 로그:**

```
[hyde] hypothetical='꽁꽁이는 1985년, 알프스 산맥의 한 빙하 속에서
       얼어붙은 상태로 발견되었으며...'
[hybrid] vector top-15 (first 5): [chunk=13 sim=0.474, chunk=10 sim=0.424,
         chunk=18 sim=0.421, chunk=12 sim=0.420, chunk=25 sim=0.401]
[bm25] top-28 (first 5): [chunk=24 score=2.575, chunk=23 score=1.999,
       chunk=0 score=0.000, chunk=1 score=0.000, chunk=2 score=0.000]
[rrf] fused 28개 (first 5): [chunk=10 rrf=0.0298, chunk=13 rrf=0.0296,
      chunk=0 rrf=0.0292, chunk=9 rrf=0.0290, chunk=12 rrf=0.0290]
[llm_rerank] candidates=28 top_k=3 prompt_version=v1
[llm_rerank] raw response='{"ranked_indices": [0, 1, 2]}'
[llm_rerank] 최종 3개: [0, 1, 2]
[retrieve] accepted=3개: ['chunk=0', 'chunk=1', 'chunk=2']
```

**결과:**

- LLM이 JSON을 깨끗하게 반환, 파싱 성공
- accepted: **chunk 0, 1, 2** ← **영상 도입부 전체**
- chunk 0 accepted: **✓**
- 최종 답변:
  ```
  꽁꽁이는 2021년 겨울에 발견되었다 — 근거 [0s]
  당시 한강이 얼어붙어 있었고, 취재 중 고양이를 보게 되었다 — 근거 [0s]
  한강 위를 걷고 있었던 이유는 마실 물이 없어서... — 근거 [15s]
  ```

**Latency:** hyde 3426ms, embedding 2007ms, retrieval 3917ms, generation 5354ms, **total 14704ms**

**Cohere 비교 (같은 세션에서 `rerank_provider=cohere`로 override_config 블록 실행):**

| 항목 | LLM rerank | Cohere rerank |
|---|---|---|
| 선택 chunk | **[0, 1, 2]** | [22, 8, 18] |
| chunk 0 accepted | ✓ | ✗ |
| 최종 답변 (발견 연도) | **"2021년 겨울"** ✓ | "확인되지 않음" ✗ |
| Latency | 14.7초 (+3초) | 10.7초 |

**배운 것:** LLM이 "꽁꽁이 = 이 영상 도입부의 한강 고양이"라는 alias를 맥락 추론으로 해결. Cohere가 못 풀던 의미 연결을 LLM 문맥 이해로 돌파. `rerank_provider` 스위치로 롤백 경로도 확보.

---

### 실험 E — use_rerank=False + threshold 모드 (대조 실험)

> LLM rerank를 제거하고 RRF top-k를 threshold 필터로만 선별.

**Config:**

| 필드 | 값 |
|---|---|
| `use_hybrid` | True |
| `use_hyde` | True |
| `use_rerank` | **False** (신규) |
| `search_threshold` | 0.3 |
| `top_k` | 3 |

**결과:**

- `vec_limit = top_k = 3` → chunk 0(sim ~0.37) vector top-3 진입 불가
- chunk 0 RRF rank: 6위 (rrf=0.0159), `similarity` 필드 없어 threshold 0 판정 → 탈락
- accepted: chunk 13, 12, 18
- 최종 답변: "얼어붙은 한강에서 물을 찾아 헤매던 고양이" — **연도 누락, 실패**
- **Latency:** total **6.6초** (실험 D 대비 -8초)

**실험 D와의 차이 3가지:**
1. **vec_limit**: rerank=True → 15개, rerank=False → 3개. pool 자체가 달라 chunk 0 진입 불가
2. **선별 기준**: LLM은 RRF 순위 + 의미 이해로 판단, threshold는 similarity 수치만 봄 (BM25 출신 chunk는 similarity=0)
3. **alias 해결**: LLM은 "꽁꽁이=한강 고양이" 맥락 추론 가능, threshold는 수치 필터라 불가

---

### 실험 F — Cohere rerank + kiwipiepy 형태소 분석 (BM25 토크나이저 교체)

> Cohere 환경에서 BM25 토크나이저를 공백 분리 → kiwipiepy 명사 추출로 교체했을 때 RRF rank 변화 확인.

**Config:**

| 필드 | 값 |
|---|---|
| `use_hybrid` | True |
| `use_hyde` | True |
| `rerank_provider` | **cohere** |
| `rerank_top_k` | 3 |
| `rerank_pool_size` | 15 |
| BM25 토크나이저 | **kiwipiepy** (명사/고유명사 추출, NNG·NNP·NNB·SL·SH·SN) |

**토큰 비교:**

| | 쿼리 토큰 | chunk 0 BM25 점수 | chunk 0 RRF rank |
|---|---|---|---|
| 기존 (공백 분리) | `['꽁꽁이가', '처음', '발견된', '해와', '상황은', '무엇인가요']` | 0.000 | **1위** (rrf=0.0317) |
| kiwipiepy | `['처음', '발견', '해', '상황']` | 0.000 | **4위** (rrf=0.0292) |

**결과:**

- 두 경우 모두 chunk 0 BM25 점수는 0.000 (공백 분리: 조사 불일치, kiwi: "꽁꽁이" 미등록 고유명사로 드롭)
- kiwipiepy 적용 시 BM25가 다른 청크(chunk 21, 26)를 상위로 올려 RRF에서 chunk 0이 **오히려 하락**
- 두 경우 모두 Cohere rerank 탈락 → chunk 0 accepted: **✗**
- 최종 답변: 상황 일부만, **연도 없음 — 실패**

**배운 것:** kiwipiepy가 일반 조사 분리에는 효과적이나, "꽁꽁이" 같은 미등록 고유명사는 토큰에서 아예 드롭되어 BM25 고유명사 매칭 강점을 잃는다. 이 케이스의 근본 병목은 Cohere의 alias 해결 불가로, 토크나이저 교체로는 해결 불가.

---

## 5. 전체 여정 요약

| 단계 | chunk 0 vector sim | chunk 0 RRF rank | chunk 0 accepted | 최종 답변 정확도 |
|---|---|---|---|---|
| 실험 0 — Baseline (vector only) | 0.207 | — (rank 19) | ✗ (pool 밖) | 실패 |
| 실험 A — Hybrid (BM25+RRF) | 0.207 | 17 | ✗ (rerank 탈락) | 실패 |
| 실험 B — + HyDE | **0.373** | **1** | ✗ (rerank 탈락) | 실패 |
| 실험 C — + rerank_top_k↑ | (동일) | (동일) | ✗ (top-7까지 없음) | 실패 |
| **실험 D — + LLM rerank** | (동일) | (동일) | **✓** | **성공 ("2021년 겨울")** |
| 실험 E — use_rerank=False | (동일) | 6위 | ✗ (vec pool 3개, threshold 탈락) | 실패 (연도 누락) |
| 실험 F — Cohere + kiwipiepy | sim=0.392 | 기존 1위 → kiwi 4위 | ✗ (Cohere 탈락 동일) | 실패 (연도 누락) |

---

## 6. 남긴 관찰·과제

### 6.1 HyDE 출력 분산
매 호출마다 가상 답변이 달라짐 (1985년/2015년/1952년 등 임의 숫자). vector ranking이 요동치는 원인. 개선 여지:
- 프롬프트에서 `temperature=0` 고정
- "숫자는 YYYY 같은 placeholder로" 지시 강화
- 프롬프트 v2로 구조 제약

### 6.2 BM25의 한국어 조사 문제
현 토큰화는 공백+구두점 분리뿐. "꽁꽁이가" ≠ "꽁꽁이"를 구별 못함. 다른 쿼리(쿼리-청크에 공통 단어가 있지만 조사 때문에 miss)에서 BM25 품질 손실 가능.
- 짧은 조사 suffix 제거 후처리
- 또는 본격 형태소 분석기(konlpy/mecab-ko) 도입 — 의존성 비용 큼

### 6.3 LLM rerank 비용
쿼리당 +3초, ~$0.0005 추가. pool 크기 증가 시 비용 선형 증가. 대량 트래픽 시나리오에서는 1차 필터(Cohere) + 2차 정밀 선별(LLM) 2단 구조 검토.

### 6.4 Chunk enrichment (인덱싱 개선)은 아직 미시도
인덱싱 시점에 video-level 요약을 각 청크 prefix로 붙이는 방향은 쿼리 시점 비용 0이고 모든 쿼리에 혜택. HyDE/LLM rerank가 해결 못하는 쿼리 유형이 나오면 다음 카드로.
