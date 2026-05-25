# Retrieval 진단 및 Hybrid Retrieval 설명

## 문제 상황

영상 `한강_고양이` (media_id: `e93b78a5-a663-4261-99a8-ccf141ed40f6`)

질문: "꽁꽁이가 처음 발견된 연도와 상황은 무엇인가요?"

기대 답변: **2021년 겨울, 한파로 꽁꽁 얼어붙은 한강 위를 걷고 있었음**

실제 답변: "제공된 영상/전사에서 확인되지 않습니다."

처음에는 동적 threshold 적용으로 해결하려 했음.

---

## 현재 구조 요약

- 고정 threshold: `search_threshold: float = 0.3` ([app/config.py:63](app/config.py#L63))
- 필터링: [app/qa/retrieval.py:105](app/qa/retrieval.py#L105) — `sim >= 0.3`만 통과
- 빈 accepted → [app/prompts.py:96](app/prompts.py#L96) 환각방지 지시 → "확인되지 않습니다"

---

## 왜 진단부터인가

"확인되지 않음" 응답의 원인은 여러 가지:

1. **Threshold 필터링 실패**: top-k는 잡았지만 score < 0.3 → 동적 threshold로 해결 가능
2. **Top-k 자체에서 누락**: 첫 청크(2021년 한파)가 top-3에 못 듦 → threshold 조정 무의미
3. **청킹 경계 문제**: window 20s / overlap 5s가 문맥을 쪼갬 → 청킹 파라미터 문제
4. **LLM이 있는데도 "확인 안됨"으로 답함**: 프롬프트 문제 → retrieval과 무관

꽁꽁이 영상의 "2021년 겨울 한파로 한강이 꽁꽁 얼어붙었던 날..."은 **영상 맨 앞 청크**일 가능성이 높음. 이 청크가 top-k에 들어왔는지, 들어왔다면 similarity가 얼마였는지를 먼저 봐야 방향이 잡힘.

---

## 진단 결과

### 첫 번째 관찰 (현재 설정, pool=15)

현재 설정:
- search_threshold: 0.3
- top_k: 3, use_rerank: True, rerank_pool_size: 15, rerank_top_k: 3

Top-15 결과:
- 모두 **chunk 9 이후** (중후반부, 집사/손님/캣타워 얘기)
- 정답이 있는 chunk 0~8 (2021 한강 이야기)은 pool에조차 없음
- accepted가 비연속적 (3위, 5위, 10위) → Cohere rerank로 재정렬된 결과

### 두 번째 관찰 (pool=100으로 확장)

**정답 청크 (chunk 0, "2021년, 겨울 한파로 한강이 꽁꽁 얼어붙었던 날...")의 실제 상태:**
- Similarity = **0.2071**
- 전체 랭킹 **19위**

**현재 설정 기준:**
- `search_threshold` = 0.3 → chunk 0 (0.2071)은 절대 통과 못함
- `rerank_pool_size` = 15 → chunk 0 (rank 19)은 pool에 **들어오지도 않음**

**왜 유사도가 낮은가 (핵심):**

| rank | chunk | sim | 내용 |
|------|-------|-----|------|
| 0 | 25 | 0.4828 | "꽁꽁아 왜 놀랬어..." |
| 1 | 13 | 0.4024 | "꽁꽁이에게 무슨 문제가..." |
| ... | ... | ... | (뒷부분 15개 모두 **"꽁꽁이"** 단어 포함) |
| **19** | **0** | **0.2071** | **"2021년 겨울 한파로 한강이..."** ← 정답 |

초반부 청크 0~8은 고양이를 **"꽁꽁이"라고 부르지 않음** (아직 이름 등장 전). "고양이", "녀석"으로 지칭. 쿼리의 "꽁꽁이"라는 고유어가 앞부분과 의미적으로 매칭되지 않는 구조적 문제.

### Threshold 문제가 아니라 Recall 문제

- 동적 threshold (relative, gap-based, percentile 어떤 방식이든) → **pool 내부에서 무엇을 자를지**를 정하는 장치. pool 밖 청크는 건드릴 수 없음.
- 문제: 정답이 pool (top-15) **밖**에 있음. pool을 20 이상으로 늘려도 rerank가 rank 19를 top-3로 끌어올릴 가능성은 낮음.

---

## 진짜 해결 방향 (초안)

1. **Hybrid retrieval (BM25 + vector)** — "2021년", "한강", "한파" 같은 **구체 어휘는 키워드가 더 강함**. BM25를 얹으면 chunk 0이 상위권으로. 이 영상에 가장 효과적.
2. **Query expansion / rewriting** — LLM이 "꽁꽁이" ↔ "한강 고양이", "이 영상의 주인공 고양이"로 alias 확장. 1회 호출 비용으로 recall 크게 개선.
3. **Chunk enrichment** — 청크 임베딩 전 "[영상 주제: 한강 고양이 꽁꽁이]" 같은 video-level 메타 문장을 prefix로 합쳐 임베딩. 인덱싱 비용은 드나 런타임 추가 비용 없음.
4. **Pool_size 확대 (15→30+)** — 가장 싸지만, rerank의 top-k 선택력이 강하지 않으면 효과 미지수. 단독으로는 부족.

---

## Query rewriting이 답안 유출인가? (사용자 지적)

사용자의 지적: "2번은 결국 답안을 제공하는 느낌이 드는데?"

맞는 지적. 제안한 2번은 **"이 영상은 한강 고양이 얘기"** 라는 영상 맥락을 쿼리 확장에 주입하자는 거였는데, 이건 평가 관점에서 답을 알려주고 찾는 셈.

### 답안 유출이 있는/없는 방법 구분

**유출 있음 (제외):**
- 영상 요약/제목을 쿼리 확장에 주입 (원래 말한 2번)
- 영상 내용을 참조한 rewriting

**유출 없음 (쿼리만 보고 재구성 or 인덱싱 시점 작업):**

1. **HyDE (Hypothetical Document Embeddings)** — LLM이 쿼리를 보고 *가상 답변*을 생성, 그 가상 답변을 임베딩해 검색. 예: "꽁꽁이가 처음 발견된 연도와 상황" → "이 고양이는 XXXX년 겨울 XX에서 발견되었다" 같은 템플릿형 가상 문장. LLM은 영상 내용을 모르고 **질문 패턴을 답변 패턴으로 변환**만 함. 정답 청크("2021년 겨울 한파로...")와 문체가 유사해져 유사도 상승.

2. **Chunk enrichment (인덱싱 시점)** — 인덱싱할 때 각 청크 앞에 video-level 메타("영상 제목: ...", "영상 요약: ...")를 prefix로 붙여 임베딩. 쿼리 시점엔 쿼리만 씀. 쿼리와 무관한 인덱싱 개선이라 유출 아님. 다만 제목에 "한강 고양이"가 들어있는지에 따라 효과가 갈림.

3. **BM25 hybrid** — 쿼리 본문만 키워드 매칭. 유출 없음. 하지만 이 쿼리엔 "2021"이 없어서 chunk 0 끌어올리기엔 약할 것.

4. **LLM re-rank over wide pool** — pool 30으로 넓히고, top-30을 LLM에게 "이 쿼리에 답이 될 청크?" 로 판정. 쿼리만 사용, 영상 맥락 주입 없음.

5. **Query paraphrasing (context-free)** — 쿼리 자체를 여러 버전으로 말 바꾸기. 영상 본 적 없는 LLM이 수행. "처음 발견된 연도와 상황" → "도입 장면, 초기 등장 배경" 등. 유출 없지만 recall 개선 폭은 제한적.

---

## Hybrid Retrieval 설명

**Dense(의미)** 검색과 **Sparse(키워드)** 검색을 **동시에 돌려 점수를 합치는** 방식. 둘이 서로의 약점을 메움.

### 두 검색의 성격 차이

| | Dense (vector) | Sparse (BM25/TF-IDF) |
|---|---|---|
| 매칭 기준 | 의미 유사도 | 단어 겹침 빈도 |
| 강점 | 동의어·의역 ("차량" ↔ "자동차") | 고유명사·숫자·코드 ("2021", "GPT-4o") |
| 약점 | 희귀/정확 토큰 ("2021년") 놓침 | 의역 놓침 ("발견" ↔ "찾았다") |
| 현재 프로젝트 | ✓ ([supabase_utils.py:147](app/supabase_utils.py#L147)) | ✗ (없음) |

### BM25 한 줄 정리

문서 내 단어 빈도(TF) × 전체 코퍼스에서의 희귀성(IDF) × 문서 길이 정규화. "한 문서에만 등장하는 드문 단어"일수록 점수가 폭발. "2021"처럼 다른 청크엔 거의 없는 토큰이 쿼리에 있으면 해당 청크 순위가 확 올라감.

### 점수 합치는 방법 (두 가지가 주류)

**A. 점수 정규화 + 가중합**
```
final = α·norm(dense) + (1-α)·norm(bm25)    # α ≈ 0.5~0.7
```
단점: 두 점수 분포 스케일이 달라 정규화 방식(min-max / z-score)에 민감.

**B. RRF (Reciprocal Rank Fusion)** — 업계에서 사실상 기본값
```
final(doc) = Σ 1 / (k + rank_i(doc))        # k = 60 관행
```
각 검색에서의 **순위**만 쓰고 점수 자체는 버림. 스케일 문제 없음. 튜닝 거의 불필요. Elasticsearch·Weaviate·Qdrant가 다 이걸 기본으로 제공.

### 이 프로젝트에 적용한다면

현재 꽁꽁이 케이스에 대입하면:

- 쿼리: "꽁꽁이가 처음 발견된 **연도**와 상황"
- BM25 관점: "연도", "처음", "발견" 토큰
  - chunk 0: "**2021년** 겨울 한파로..." → "2021년"이 코퍼스에서 유일 → IDF 폭발, 점수 높음
  - 하지만 쿼리에 "2021"이 **없어서** 이 매칭은 일어나지 않음
  - "처음", "발견"은 다른 청크에도 등장 → IDF 약함
- **솔직히 이 케이스에서 BM25 단독 효과는 제한적** — 쿼리 단어("꽁꽁이")가 여전히 뒷부분과 더 겹침

### 구현 위치 (하려면)

- **DB 레이어**: Postgres `tsvector` + `ts_rank_cd` 또는 `pg_trgm`. Supabase라 RPC 하나 추가하면 됨
- **코드 레이어**: [app/qa/retrieval.py](app/qa/retrieval.py) — `_rank_candidates`와 같은 위치에 fusion 로직 추가, vector search와 병렬 호출

### 결론

Hybrid는 **범용적으로** 매우 강한 개선책 (특히 고유명사·숫자·코드가 많은 도메인). 하지만 **이 꽁꽁이 쿼리 한 건**에 대해서는, 쿼리 자체에 고유 키워드("2021", "한강")가 없어서 큰 도움이 안 될 가능성이 높음. 쿼리가 **"한강에서 고양이를 처음 봤을 때 상황"** 이었다면 BM25가 즉시 chunk 0을 끌어올렸을 것.

이 케이스에 한정하면 **HyDE** 쪽이 더 유효해 보이지만, 프로젝트 전반을 보면 **Hybrid는 결국 도입해야 할 기반 기능**. 둘은 배타적이지 않음 — HyDE로 만든 가상 답변을 dense+BM25 양쪽에 넣으면 최강 조합.

---

# Hybrid Retrieval 구현 플랜 (A안 — media별 corpus)

## IDF와 corpus 결정 (A안 선택)

### BM25는 무엇을 계산하는가

BM25는 "문서 D가 쿼리 Q에 얼마나 관련 있는가"를 숫자로 매기는 공식:

```
BM25(D, Q) = Σ  IDF(q)  ×  TF(q, D) × (k1 + 1)
           q∈Q            ─────────────────────────────────────
                          TF(q, D) + k1 × (1 - b + b × |D|/avgdl)
```

쿼리의 각 단어 `q`에 대해 세 가지를 곱해서 다 더한다:

#### (a) TF (Term Frequency) — "이 문서 안에서 이 단어가 얼마나 자주 등장하는가"

문서 D 안에서 `q`가 몇 번 나오는지. 많이 나올수록 점수 상승. 단, 무한정 커지지 않게 포화 곡선으로 눌러줌 (위 식의 분수 구조가 그 역할).

#### (b) IDF (Inverse Document Frequency) — "이 단어가 전체 문서들 사이에서 얼마나 드문가"

**핵심.** 어떤 단어가 거의 모든 문서에 나오면 그 단어로 문서를 구별할 수 없다. 반대로 소수 문서에만 나오는 단어는 강력한 식별자.

공식:
```
IDF(q) = log( (N - n(q) + 0.5) / (n(q) + 0.5) + 1 )
```
- `N` = 전체 문서 수
- `n(q)` = 단어 `q`가 나온 문서 수

꽁꽁이 영상 예시 (청크 28개):

| 단어 | 등장 청크 수 | IDF (대략) | 의미 |
|---|---|---|---|
| "꽁꽁이" | 15개 | 낮음 (~0.2) | 영상 전반에 흔함 → 식별력 약함 |
| "고양이" | 10개 | 중간 (~0.7) | 어느 정도 구분력 |
| "2021년" | 1개 | 높음 (~3.3) | 이 청크만의 고유어 → 강한 식별자 |
| "한파" | 2개 | 높음 (~2.5) | 희귀 → 강한 식별자 |

**쿼리에 "2021"이 들어가면, "2021"이 있는 청크 하나의 점수가 폭발적으로 오른다.** Dense 검색이 놓치는 걸 BM25가 잡아주는 원리.

#### (c) 길이 보정 (`b`, `avgdl`)

긴 문서는 단어가 많이 나올 수밖에 없으니 TF를 문서 길이로 눌러줌. `avgdl`은 평균 문서 길이.

#### (d) 하이퍼파라미터 `k1`, `b`

- `k1` (보통 1.2~2.0): TF 포화 속도
- `b` (보통 0.75): 길이 보정 강도

관행: `k1=1.5, b=0.75`. `rank_bm25` 라이브러리 기본값. 튜닝 불필요.

### Corpus 선택 — A안 (media별)

"IDF 계산할 때 어떤 범위를 corpus로 삼을 것인가?"

**A안 (media별):** 현재 검색 대상 영상 한 건의 청크들만 corpus. 꽁꽁이 영상이면 N=28.
- 장점: 자연스러움 (검색 자체가 media_id로 필터링됨), 단순 (쿼리 시점 즉시 계산), 성능 (청크 수십 개는 ms 단위), 영상 고유 어휘 반영
- 단점: N이 작으면 통계 거칠 수 있음

**B안 (전역):** DB 모든 영상 청크 통합. N=수천.
- 장점: 통계적으로 안정, 영상 식별어에 가중치
- 단점: IDF 테이블 관리 필요, 인프라 복잡 (YAGNI)

**결정: A안.** 지금 검색이 영상 경계를 넘지 않으므로 A면 충분. B는 나중에 필요해지면 Postgres tsvector+ts_stat로 승격.

---

## 구현 9단계 상세 플랜

### 0. 전체 그림

현재 retrieval은 "Dense(vector) 단독 → rerank/threshold" 흐름. 여기에 BM25를 병렬로 추가하고 두 랭킹을 **RRF (Reciprocal Rank Fusion)** 로 합쳐서 rerank에 보내는 구조로 변경.

**핵심 변화:**
- 검색 단계가 "1개 검색 → 선별"에서 "2개 검색 → 융합 → 선별"로 확장
- `rank_bm25` 의존성 1개 추가. DB 스키마 변경 **없음**
- 관측 트리에 `qa.2_search` chain 신설, 그 밑에 vector/bm25/rrf 세 자식
- `use_hybrid=False`로 과거 동작으로 되돌릴 수 있음 (rollback 경로 보존)

### 1. 의존성 추가

**파일:** `Pipfile`

`rank-bm25 = "*"` 추가. 순수 Python 라이브러리, 외부 바이너리 없음. `BM25Okapi` 클래스 하나만 사용.

**대안 고려:** 직접 BM25 구현도 50줄이면 가능하지만, 검증된 라이브러리를 쓰는 편이 하이퍼파라미터 기본값(k1=1.5, b=0.75)과 수식 측면에서 안전.

### 2. Config 확장

**파일:** `app/config.py`

#### flat CONFIG에 3개 필드 추가 (Rerank 블록 뒤)

```python
# ── Hybrid Retrieval (BM25 + vector) ──
use_hybrid: bool = os.getenv("USE_HYBRID", "true").lower() == "true"
hybrid_rrf_k: int = 60          # RRF 상수 (원 논문 권장값)
hybrid_bm25_top_k: int = 30     # BM25가 RRF로 넘길 후보 수
```

**왜 기본 `true`:** recall 문제 해결이 동기이므로 개선 경로 기본 활성화. env var로 즉시 끌 수 있음.

**`hybrid_bm25_top_k = 30` 선택 근거:** vector pool_size=15와 union하면 중복 제거 후 20~40개 후보. Cohere rerank 감당 가능 범위.

#### RetrievalCfg에 3개 필드 추가

```python
class RetrievalCfg(BaseModel):
    # ...기존 필드...
    use_hybrid: bool = True
    hybrid_rrf_k: int = 60
    hybrid_bm25_top_k: int = 30
```

#### `_STAGE_FIELD_MAP["retrieval"]`에 매핑 추가

`override_config(retrieval={"use_hybrid": False})` 실험용 오버라이드 지원.

#### `get_stage_config()`의 RetrievalCfg 생성부 수정

flat CONFIG 값 주입.

#### 시작 시 config 출력 블록 확장

`─ Hybrid ─` 섹션 추가. `Use Hybrid`, `RRF k`, `BM25 top-k`. Rerank 블록 뒤에 배치.

### 3. BM25 util 신설

**파일:** `app/qa/bm25.py` (신규)

`app-구조.md` §2 기준 qa 도메인 util 파일이 이미 2개(`retrieval.py`, `chat.py`) 있으므로 새 파일 추가 자연스러움.

#### 구성

**(a) 토큰화 — `_tokenize(text: str) -> List[str]`**

```python
import re
_TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]+")

def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    return _TOKEN_RE.findall(text.lower())
```

**왜 이 방식:** 한국어 형태소 분석기(konlpy, mecab-ko)는 자바/C++ 의존성 폭발. whitespace+구두점 분리는 "2021년"이 하나의 토큰이 되는 약점 있지만, 대부분 질문이 완전 토큰을 포함하므로 실용적.

**`_tokenize`가 필요한 이유:**
1. BM25는 단어 단위 통계 → 단어로 쪼개진 입력 필수
2. `rank_bm25` 라이브러리는 pre-tokenized input 받음 (문자열 그대로 넘기면 글자 단위로 iterate해버림)
3. 언어마다 단어 경계가 달라 라이브러리가 알아서 못 쪼갬
4. 쿼리와 corpus가 같은 토크나이저 써야 매칭됨
5. 정규화(소문자화)도 여기서

**(b) BM25 검색 — `bm25_search`**

```python
@traceable(name="qa.2.2_bm25_search", run_type="retriever")
def bm25_search(query, media_id, cfg=None):
    cfg = cfg or get_stage_config().retrieval
    segments = get_media_segments(media_id)        # 영상 전체 청크
    if not segments:
        return []

    corpus_tokens = [_tokenize(s["text"] or "") for s in segments]
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    bm25 = BM25Okapi(corpus_tokens)                # 여기서 IDF 테이블 생성
    scores = bm25.get_scores(query_tokens)

    scored = [{**seg, "bm25_score": float(score)}
              for seg, score in zip(segments, scores)]
    scored.sort(key=lambda s: s["bm25_score"], reverse=True)
    return scored[: cfg.hybrid_bm25_top_k]
```

**설계 포인트:**
- Corpus = `get_media_segments(media_id)` — A안대로 영상 내부 청크만. DB에서 전체 청크 한 번 가져옴
- 매 쿼리마다 BM25 인덱스 재생성 — 청크 작아서 오버헤드 무시 가능
- 반환 포맷은 `search_similar_segments`와 호환 — `chunk_index`, `text`, `start_time`, `end_time` 유지. `similarity` 대신 `bm25_score` 필드

### 4. RRF fusion 함수

**파일:** `app/qa/retrieval.py`에 추가

```python
@traceable(name="qa.2.3_rrf_fuse", run_type="tool")
def _rrf_fuse(rankings, k):
    """
    공식: final(doc) = Σ  1 / (k + rank_i(doc) + 1)
    """
    scores = {}
    doc_map = {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking):
            key = doc.get("chunk_index")
            if key is None:
                continue
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            if key not in doc_map:
                doc_map[key] = doc
    fused_keys = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [{**doc_map[key], "rrf_score": scores[key]} for key in fused_keys]
```

**왜 RRF (가중합 안 쓰는 이유):**
- Vector similarity는 [0, 1], BM25 점수는 unbounded → 스케일 차이로 정규화·`α` 튜닝 두 축 추가됨
- RRF는 점수 버리고 순위만 씀 → 스케일 문제 원천 제거
- Elasticsearch, Weaviate, Qdrant 모두 기본 fusion으로 채택

**`k=60`의 의미:** 랭킹 상위권 영향 조절. 작으면 1위/2위가 극단적 중요, 크면 10~20위도 기여. 60이 중도.

**첫 등장 문서 보존:** 같은 chunk가 vector/bm25 양쪽에 있으면 vector 쪽 dict(similarity 포함)를 우선 저장 → rerank가 필요로 하는 필드 유지.

**구체 예시 (k=60):**
- Vector: [chunkA, chunkB, chunkC]
- BM25: [chunkC, chunkD, chunkA]
- chunkA: 1/61 + 1/63 = 0.03226
- chunkC: 1/63 + 1/61 = 0.03226
- chunkB: 1/62 = 0.01613 (vector만)
- chunkD: 1/62 = 0.01613 (bm25만)
- → 두 ranking에 모두 등장하는 문서가 자연스럽게 위로

### 5. Hybrid search orchestrator

**파일:** `app/qa/retrieval.py`에 추가

```python
@traceable(name="qa.2_search", run_type="chain")
def _hybrid_search(query, query_embedding, media_id, cfg):
    vec_limit = cfg.rerank_pool_size if cfg.use_rerank else cfg.top_k
    vec_cfg = cfg.model_copy(update={"top_k": vec_limit})
    vector_results = search_similar_segments(
        query_embedding, media_id, cfg=vec_cfg, skip_threshold=True)

    if not cfg.use_hybrid:
        return vector_results              # rollback 경로

    bm25_results = bm25_search(query, media_id, cfg=cfg)
    return _rrf_fuse([vector_results, bm25_results], k=cfg.hybrid_rrf_k)
```

**관측 관점:**
- `qa.2_search` chain. 자식: `qa.2.1_vector_search`(rename), `qa.2.2_bm25_search`(신규), `qa.2.3_rrf_fuse`(신규)
- `use_hybrid=False`일 땐 얕은 chain — rollback 전용 일시 상황

### 6. 기존 `retrieve_segments` 수정

**파일:** `app/qa/retrieval.py`

기존 "rerank 모드면 pool_size로 넓혀서 search" 로직을 `_hybrid_search` 안으로 이동. `retrieve_segments`는 "search → rank → accepted 마킹" 단일 흐름으로 정리:

```python
def retrieve_segments(query, query_embedding, media_id, cfg=None):
    cfg = cfg or get_stage_config().retrieval
    all_segments = _hybrid_search(query, query_embedding, media_id, cfg)
    accepted_segments = _rank_candidates(all_segments, query, cfg)
    accepted_indices = {s.get("chunk_index") for s in accepted_segments}
    for seg in all_segments:
        seg["accepted"] = seg.get("chunk_index") in accepted_indices
    return all_segments, accepted_segments
```

### 7. Traceable 이름 재구성

**파일:** `app/supabase_utils.py`

기존 `@traceable(name="qa.2_vector_search", ...)` → `name="qa.2.1_vector_search"` rename.

**변경 이유:** hybrid 도입 후 검색 단계에 자식이 여러 개 생김. 번호 체계상 vector_search는 2.1로 내려가야 계층 질서 맞음(langsmith-관측.md §2 계층 번호 예: `qa.3.1_rerank`).

### 8. Snapshot 확장

**파일:** `app/snapshot.py`

`get_config_snapshot()`의 Retrieval 블록에 3개 키 추가:
```python
"use_hybrid": retrieval.use_hybrid,
"hybrid_rrf_k": retrieval.hybrid_rrf_k,
"hybrid_bm25_top_k": retrieval.hybrid_bm25_top_k,
```

**왜 중요한가:** CLAUDE.md §2 "기록 = 실행" 원칙. snapshot이 실제 실행된 hybrid 여부를 못 담으면 실험 재현/비교 불가능. evals 스냅샷에도 자동 반영.

### 9. 관측 규칙 문서 갱신

**파일:** `.claude/rules/langsmith-관측.md` §6

세 가지 트리 스냅샷으로 확장:
- QA (hybrid + rerank 모드, 기본값)
- QA (hybrid + threshold 모드)
- QA (use_hybrid=False, rollback 경로)

각 트리에 `qa.2_search` chain과 그 아래 `qa.2.1_vector_search`, `qa.2.2_bm25_search`, `qa.2.3_rrf_fuse` 추가.

---

## 구현 결과 (순차 실행 완료)

### 변경 파일 목록

| # | 파일 | 작업 |
|---|------|------|
| 1 | `Pipfile` | `rank-bm25 = "*"` 추가 + `pipenv install` |
| 2 | `app/config.py` | flat CONFIG 3필드, RetrievalCfg, field_map, stage builder, 시작 로그 |
| 3 | `app/qa/bm25.py` | 신규 — `_tokenize` + `bm25_search` (print문 포함) |
| 4 | `app/qa/retrieval.py` | `_rrf_fuse`, `_hybrid_search` 추가, `retrieve_segments` 재정리 (print문 포함) |
| 5 | `app/supabase_utils.py` | `qa.2_vector_search` → `qa.2.1_vector_search` rename |
| 6 | `app/snapshot.py` | Hybrid 3필드 반영 |
| 7 | `.claude/rules/langsmith-관측.md` | §6 트리 스냅샷 3가지로 확장 |

### 서버 기동 확인

```
─ Hybrid ─
Use Hybrid           : True
RRF k                : 60
BM25 Top-K           : 30
```

---

## 실험 결과 (꽁꽁이 쿼리)

### 실행

```
query = "꽁꽁이가 처음 발견된 연도와 상황은 무엇인가요?"
media_id = "e93b78a5-a663-4261-99a8-ccf141ed40f6"
```

### 구조적 성공

- Hybrid 파이프라인 정상 동작: vector(15) + BM25(28) → RRF(28) → Cohere rerank(top-3)
- **chunk 0~8이 검색 풀에 진입함** (이전엔 pool 밖이었음)
- `sources` JSON에 `similarity` / `bm25_score` / `rrf_score` 모두 관측 가능
- Latency: embedding 1985ms, retrieval 2535ms, generation 6611ms, total 11131ms

### 핵심 문제 — BM25 점수가 거의 다 0

주요 청크별 점수:

| rank | chunk | sim | bm25 | rrf | accepted | 내용 |
|---|---|---|---|---|---|---|
| 0 | 24 | 0.258 | — | 0.0299 | False | "편안하게 살게 해줄 수 있으면..." |
| 1 | 10 | 0.393 | — | 0.0296 | False | "꽁꽁이는 어디에 있나요?..." |
| 2 | 13 | 0.402 | — | 0.0293 | False | "꽁꽁 얼어붙은 한강에서..." |
| 8 | 18 | 0.347 | — | 0.0275 | **True** | "꽁꽁 숨어서 나오지 않는 꽁꽁이를 위해..." |
| 9 | 22 | 0.372 | — | 0.0274 | **True** | "처음엔 집사를 굉장히 경계했던 꽁꽁이..." |
| 15 | 23 | — | 1.999 | 0.0161 | False | "고민이 좀 많이 되긴 했죠..." |
| **16** | **0** | — | **0.000** | 0.0159 | **False** | **"2021년, 겨울 한파로 한강이..." ← 정답** |
| 17~23 | 1~7 | — | 0.000 | ~0.015 | False | 도입부 청크들 |
| 24 | 8 | — | 0.000 | 0.0141 | **True** | "포획틀 안에 먹이..." (rerank가 포착) |

### 원인 분석 — 한국어 조사 문제

**쿼리 토큰화 결과:**
```
"꽁꽁이가 처음 발견된 연도와 상황은 무엇인가요"
→ ["꽁꽁이가", "처음", "발견된", "연도와", "상황은", "무엇인가요"]
```

**chunk 0 토큰화:**
```
"2021년, 겨울 한파로 한강이 꽁꽁 얼어붙었던 날..."
→ ["2021년", "겨울", "한파로", "한강이", "꽁꽁", ...]
```

**매칭되는 토큰이 0개.**
- `"꽁꽁이가"` ≠ `"꽁꽁"` (조사 "이가" 붙음)
- `"처음"` ≠ chunk 0에 없음
- `"발견된"` ≠ chunk 0에 없음

플랜 단계에서 "한국어 형태소 분석 없이 공백 분리만으로는 약할 수 있다"고 언급한 문제가 그대로 드러남.

### Rerank도 정답 못 잡음

Cohere가 top-3로 뽑은 건 **chunk 18, 22, 8**.
- chunk 8 ("포획틀 안에 먹이 주위...구조했습니다. 촬영 기자의 집으로 오게 된 꽁꽁이")까지는 포착
- 하지만 chunk 0의 "2021년" 정보는 여전히 미스
- Cohere 같은 cross-encoder도 "꽁꽁이 = 이 영상의 고양이" alias를 자동으로 해결 못함

### 최종 답변

```
꽁꽁이는 처음에 집사를 굉장히 경계하고 공포에 질려 구석에 숨어 있었으며,
포획틀에서 몇 번의 시도 끝에 구조되었습니다.
그러나 구체적으로 발견된 연도는 제공된 영상/전사에서 확인되지 않습니다.
```

**결론:** Hybrid는 구조적으로 작동하지만 이 쿼리엔 효과가 제한적.

### 원인 요약

1. **한국어 조사 때문에 BM25 토큰 매칭 거의 실패** — "꽁꽁이가" ≠ "꽁꽁"
2. **쿼리에 희귀 키워드("2021", "한강", "한파")가 없음** — BM25로 해결하기 어려운 쿼리 패턴
3. **Cohere rerank도 alias 해결 못함** — "꽁꽁이 ↔ 이 영상의 고양이"

---

## 다음 단계 선택지

1. **토큰화 개선** — 간단한 조사 제거 후처리 (`["은","는","이","가","을","를","의","와","로","과"]` 등). 의존성 없음, 5분 작업. "꽁꽁이가" → "꽁꽁이"로 정규화. 일부 쿼리엔 효과
2. **Character n-gram BM25** — "꽁꽁이가" → `["꽁꽁", "꽁이", "이가"]`. 한국어 subword 매칭에 강하지만 noise도 생김
3. **HyDE** — 이 쿼리엔 HyDE가 더 유효. 플랜 문서에 기록된 대안
4. **현 상태 유지** — Hybrid 인프라 확보한 것으로 만족. 다른 쿼리엔 여전히 도움 가능
