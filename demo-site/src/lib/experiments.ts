export type TimelineStep = {
  label: string;
  change: string;
  outcome: string;
  status: "fail" | "progress" | "success";
};

export type ModelChoice = {
  role: string;
  model: string;
  reason: string;
};

export type Improvement = {
  label: string;
  before: string;
  after: string;
};

export type Experiment = {
  slug: string;
  shortLabel: string;
  title: string;
  kicker: string;
  oneLiner: string;
  cardSummary: string;
  dataset: string;
  duration: string;
  artifact: string;
  question: string;
  cardStats: { label: string; value: string }[];
  problemStatement: string[];
  firstAttempt: {
    answer: string;
    note: string;
  };
  failureAnalysis: string[];
  timeline: TimelineStep[];
  finalAnswer: {
    answer: string;
    summary: string;
    improvements: Improvement[];
  };
  modelChoices: ModelChoice[];
  techBadges: string[];
  comparison: {
    columns: string[];
    rows: string[][];
  };
  learnings: string[];
  architecture: string[];
  teamNote: string;
  snapshot: Record<string, unknown>;
  art: {
    variant: "cat" | "code" | "cctv" | "movie";
    base: string;
    accent: string;
    glow: string;
    headline: string;
    eyebrow: string;
    tag: string;
  };
};

export const experiments: Experiment[] = [
  {
    slug: "kkongkongi",
    shortLabel: "01",
    title: "꽁꽁이 Retrieval Repair",
    kicker: "고유명사가 RAG를 탈출하는 방법",
    oneLiner: "정답 청크가 분명히 있는데도 검색이 계속 그 청크를 버리는 구조적 실패를 추적했다.",
    cardSummary:
      "Vector, BM25, rerank가 동시에 실패하는 드문 케이스였다. HyDE와 LLM rerank를 겹쳐서 chunk 0을 다시 top-1로 복원했다.",
    dataset: "Han River cat rescue / 28 chunks",
    duration: "02:14",
    artifact: "Retrieval trace + rerank diff",
    question: "꽁꽁이가 처음 발견된 연도와 상황은 무엇인가요?",
    cardStats: [
      { label: "Chunk 0 rank", value: "17 → 1" },
      { label: "Similarity", value: "0.207 → 0.373" },
      { label: "Final", value: "정답 복원" },
    ],
    problemStatement: [
      "정답은 영상 맨 앞 chunk 0에 있었지만, 쿼리의 고유명사 ‘꽁꽁이’는 초반 문맥과 직접 연결되지 않아 dense retrieval에서 밀렸다.",
      "BM25는 조사 불일치 때문에 ‘꽁꽁이가’를 제대로 잡지 못했고, Cohere rerank는 ‘꽁꽁이 = 한강 고양이’ alias 추론에 실패했다.",
    ],
    firstAttempt: {
      answer: "알 수 없습니다.",
      note: "정답 청크가 rerank pool에도 못 들어오면서 QA가 근거를 찾지 못했다.",
    },
    failureAnalysis: [
      "Dense retrieval은 ‘처음 발견된 연도와 상황’ 같은 질문 패턴보다 ‘꽁꽁이’라는 표면형에 끌려 후반 청크를 더 높게 보았다.",
      "Sparse retrieval은 공백 기반 토큰화 때문에 ‘꽁꽁이가’와 ‘꽁꽁이’를 분리하지 못했고, 한국어 조사 불일치가 recall을 깎았다.",
      "Cross-encoder rerank는 이름이 나오지 않는 초반 서술을 ‘이 영상의 주인공 고양이’와 연결하지 못해 alias 문제를 남겼다.",
    ],
    timeline: [
      {
        label: "Baseline",
        change: "vector only",
        outcome: "chunk 0 similarity 0.207, rank 17로 pool 밖",
        status: "fail",
      },
      {
        label: "+ Hybrid",
        change: "BM25 + RRF",
        outcome: "초반 청크가 다시 보이기 시작했지만 조사 불일치로 결정타 부족",
        status: "progress",
      },
      {
        label: "+ HyDE",
        change: "가상 답변 임베딩",
        outcome: "chunk 0 similarity 0.373, RRF rank 1로 역전",
        status: "progress",
      },
      {
        label: "+ LLM rerank",
        change: "listwise rerank",
        outcome: "‘꽁꽁이 = 한강 고양이’ alias를 복원해 최종 정답 도달",
        status: "success",
      },
    ],
    finalAnswer: {
      answer:
        "꽁꽁이는 2021년 겨울 한파로 한강이 얼어붙었던 시기에 처음 발견됐고, 사람을 경계한 채 숨어 있던 상태에서 구조된 고양이였다.",
      summary:
        "HyDE가 문장 패턴을 정답 청크 쪽으로 끌어오고, LLM rerank가 이름 없는 초반 서술을 같은 개체로 묶어주면서 구조가 완성됐다.",
      improvements: [
        { label: "Similarity", before: "0.207", after: "0.373" },
        { label: "Chunk 0 rank", before: "17", after: "1" },
        { label: "Accepted chunks", before: "0", after: "3" },
      ],
    },
    modelChoices: [
      {
        role: "Embedding",
        model: "BGE-M3 (local, 1024d)",
        reason: "한국어 포함 다국어 지원이 안정적이고, 로컬 실행으로 실험 반복 비용을 거의 없앴다.",
      },
      {
        role: "Rerank",
        model: "GPT-4o-mini listwise rerank",
        reason: "Alias 추론이 핵심이라 점수 기반 cross-encoder보다 문맥적 연결을 읽는 LLM이 더 잘 맞았다.",
      },
      {
        role: "QA",
        model: "GPT-4o-mini",
        reason: "근거 인용형 응답 품질이 안정적이면서 rerank와 같은 모델 패밀리로 튜닝 포인트를 줄일 수 있었다.",
      },
    ],
    techBadges: ["BGE-M3", "BM25", "RRF Hybrid Search", "HyDE", "LLM Rerank", "Chunk Diagnostics"],
    comparison: {
      columns: ["단계", "Similarity", "Chunk 0 Rank", "Accepted", "판정"],
      rows: [
        ["Baseline", "0.207", "17", "✗", "실패"],
        ["+ Hybrid", "0.221", "8", "✗", "부분 개선"],
        ["+ HyDE", "0.373", "1", "✗", "vector 해결"],
        ["+ LLM rerank", "0.373", "1", "✓", "성공"],
      ],
    },
    learnings: [
      "수치 기반 필터만으로는 미등록 고유명사 alias를 해결할 수 없다.",
      "한국어 조사 이슈는 sparse search에 작은 결함처럼 보이지만, chunk ranking 전체를 바꿀 만큼 치명적일 수 있다.",
      "HyDE와 rerank는 경쟁 관계가 아니라, 서로 다른 실패층을 메우는 조합으로 봐야 한다.",
    ],
    architecture: ["Question rewrite", "HyDE answer draft", "Hybrid retrieval", "LLM rerank", "Grounded QA"],
    teamNote:
      "실제 retrieval 로그와 PR 문서를 바탕으로 구성했고, 서술 일부는 포트폴리오 발표용으로 다듬은 더미 문장이다.",
    snapshot: {
      mediaId: "han-river-cat-rescue",
      query: "꽁꽁이가 처음 발견된 연도와 상황은 무엇인가요?",
      vectorOnly: { chunk0Similarity: 0.207, rank: 17, accepted: false },
      final: { chunk0Similarity: 0.373, rank: 1, accepted: true },
      sources: [
        "notes/01_retrieval-진단-및-hybrid-설명.md",
        "notes/02_retrieval-개선-방향-탐색-및-실험.md",
      ],
    },
    art: {
      variant: "cat",
      base: "#1a130d",
      accent: "#f97316",
      glow: "#fde047",
      headline: "chunk 0",
      eyebrow: "Alias Recovery",
      tag: "Retrieval",
    },
  },
  {
    slug: "print",
    shortLabel: "02",
    title: "print() Multimodal Parse",
    kicker: "화면과 음성이 다를 때 무엇을 믿어야 하는가",
    oneLiner: "Whisper는 ‘프린트’를 잘 들었지만, 우리가 필요한 건 코드 토큰 `print()`였다.",
    cardSummary:
      "오디오와 시각 정보가 충돌하는 전형적인 멀티모달 문제였다. Whisper prompt, correction, vision 업그레이드를 순차적으로 시험했다.",
    dataset: "coding-tutorial / 5 eval questions",
    duration: "03:13",
    artifact: "ASR + frame analyses + eval runs",
    question: "이 코드에서 사용된 내장 함수를 모두 나열하세요.",
    cardStats: [
      { label: "GR", value: "0.82 → 0.94" },
      { label: "print(", value: "4/10 → 10/10" },
      { label: "Final", value: "5개 함수 복원" },
    ],
    problemStatement: [
      "화자는 한국어로 ‘프린트’라고 발음했지만 화면에는 `print()`가 보였다. Whisper는 발화를 정확히 전사했기 때문에 오히려 검색에는 불리한 형태가 남았다.",
      "그 결과 `print()`가 context에서 빠졌고, QA는 `input`, `split`, `int`, `len`만 보고 불완전한 정답을 내놓았다.",
    ],
    firstAttempt: {
      answer: "input, split, int, len",
      note: "`print()`가 context에 아예 없어 정답 다섯 개 중 하나가 반복적으로 누락됐다.",
    },
    failureAnalysis: [
      "Whisper `prompt`는 발음이 모호한 단어의 철자를 유도하는 데는 효과가 있지만, 명확한 한국어 음차 발화 자체를 override하진 못했다.",
      "Correction v1은 `print()`를 살리려다 코드 블록을 과도하게 삽입하면서 guard reject를 유발했고, retrieval precision이 흔들렸다.",
      "결국 가장 확실한 해결은 화면에서 `print(`를 더 자주, 더 선명하게 포착하는 vision layer 개선이었다.",
    ],
    timeline: [
      {
        label: "01-A",
        change: "correction OFF",
        outcome: "AR 0.94, GR 0.82, `print()` 누락 유지",
        status: "fail",
      },
      {
        label: "01-B",
        change: "correction v1",
        outcome: "과교정으로 guard reject 발생, 다른 방식의 실패",
        status: "progress",
      },
      {
        label: "02-D",
        change: "correction v2",
        outcome: "텍스트 정리는 안정화됐지만 핵심 함수 복원은 아직 부족",
        status: "progress",
      },
      {
        label: "03-F",
        change: "whisper prompt + correction v2",
        outcome: "GR 0.94, RP 0.53으로 최고 조합 형성",
        status: "progress",
      },
      {
        label: "04",
        change: "gpt-5.4 vision",
        outcome: "`print(` 등장 프레임 4/10 → 10/10, 최종 정답 안정화",
        status: "success",
      },
    ],
    finalAnswer: {
      answer: "print, input, split, int, len",
      summary:
        "시각 정보가 음차 전사를 보정하도록 파이프라인 레이어를 재배치하자, `print()`가 다시 retrieval context에 들어오기 시작했다.",
      improvements: [
        { label: "Groundedness", before: "0.82", after: "0.94" },
        { label: "Retrieval precision", before: "0.40", after: "0.53" },
        { label: "Frames with `print(`", before: "4/10", after: "10/10" },
      ],
    },
    modelChoices: [
      {
        role: "ASR",
        model: "Whisper-1",
        reason: "한국어 전사 품질과 세그먼트 타임스탬프가 안정적이라 correction과 Vision alignment에 유리했다.",
      },
      {
        role: "Vision",
        model: "gpt-5.4",
        reason: "프레임당 설명량이 2.1배까지 늘고 `print(` 포착률이 4/10에서 10/10으로 올라 critical issue를 직접 해결했다.",
      },
      {
        role: "Correction",
        model: "GPT-4o-mini",
        reason: "v2 prompt와 결합했을 때 과교정 없이 화면 텍스트를 전사에 주입하는 균형점이 가장 좋았다.",
      },
      {
        role: "Embedding",
        model: "BGE-M3 (local, 1024d)",
        reason: "한국어와 코드 토큰이 섞인 context를 저비용으로 반복 실험하기 적합했다.",
      },
    ],
    techBadges: [
      "Whisper-1",
      "Vision-guided Correction",
      "GPT-4o-mini",
      "gpt-5.4",
      "BGE-M3",
      "Frame OCR",
    ],
    comparison: {
      columns: ["실험", "Correction", "AR", "GR", "RP"],
      rows: [
        ["01-A OFF", "✗", "0.94", "0.82", "0.40"],
        ["01-B ON v1", "✓", "0.86", "0.72", "0.53"],
        ["02-D v2 fresh", "✓", "0.88", "0.82", "0.40"],
        ["03-F final", "✓", "0.88", "0.94", "0.53"],
        ["04 gpt-5.4 vision", "✓", "0.88", "0.92", "0.47"],
      ],
    },
    learnings: [
      "오디오가 정확하다고 해서 검색에 유리한 표현이 남는 것은 아니다.",
      "전사 교정보다 강한 해결 레이어는 결국 시각에서 정답 토큰을 더 자주 확보하는 것이었다.",
      "멀티모달 파이프라인은 각 레이어의 책임을 다시 분배할 때 가장 큰 품질 점프가 나온다.",
    ],
    architecture: ["Whisper transcript", "Frame OCR", "Vision-guided correction", "Embedding", "Grounded QA"],
    teamNote:
      "실험 수치 대부분은 실제 실험 04, 05 리포트에서 가져왔고, 발표 친화성을 위해 일부 설명만 압축했다.",
    snapshot: {
      dataset: "coding-tutorial",
      criticalQuestion: "영상에서 사용된 파이썬 내장 함수를 모두 나열해줘",
      bestConfig: "whisper prompt v1 + correction v2",
      runNotes: {
        baseline: { ar: 0.94, gr: 0.82, rp: 0.4 },
        final: { ar: 0.88, gr: 0.94, rp: 0.53 },
      },
      sources: [
        "experiments/03-whisper-prompt-correction-v2/exp-report-04.md",
        "experiments/04-vision-model-upgrade-gpt5-4/exp-report-05.md",
      ],
    },
    art: {
      variant: "code",
      base: "#07111f",
      accent: "#2563eb",
      glow: "#67e8f9",
      headline: "print()",
      eyebrow: "Vision-guided correction",
      tag: "Multimodal",
    },
  },
  {
    slug: "cctv",
    shortLabel: "03",
    title: "CCTV Scene Prompt Shift",
    kicker: "현실 영상에 RAG를 붙이면 어디서부터 무너지는가",
    oneLiner: "코딩 강의 전용 Vision 프롬프트를 CCTV에 그대로 쓰자, 모델은 ‘코드가 없다’는 사실만 정확히 설명했다.",
    cardSummary:
      "문제는 모델 크기가 아니라 태그 설계였다. 도메인 중립 프롬프트와 타임스탬프 저장을 붙여 현실 장면에 맞는 검색 단위를 다시 만들었다.",
    dataset: "parking-lot CCTV / 7 event clips",
    duration: "01:48",
    artifact: "Scene tags + timestamped frame store",
    question: "흰색 차량이 급정거한 직후 검은 외투를 입은 사람에게 어떤 일이 일어났나요?",
    cardStats: [
      { label: "Event recall", value: "0.38 → 0.84" },
      { label: "Frame hits", value: "2 → 7" },
      { label: "Temporal error", value: "±8s → ±2s" },
    ],
    problemStatement: [
      "기존 v5-code 프롬프트는 `[코드][실행결과]`처럼 프로그래밍 강의에 맞춰져 있어서 CCTV 프레임의 핵심인 인물, 차량, 이상 행동을 구조적으로 뽑아내지 못했다.",
      "결과적으로 retrieval은 사건이 아니라 ‘텍스트 없음’ 같은 무의미한 설명을 중심으로 묶였고, QA는 장면을 시간축으로 특정하지 못했다.",
    ],
    firstAttempt: {
      answer: "코드 영역이나 실행 결과는 확인되지 않습니다.",
      note: "틀린 답은 아니지만 CCTV 질문에는 아무 도움도 주지 못하는 완전한 도메인 미스매치였다.",
    },
    failureAnalysis: [
      "프롬프트 태그가 잘못되면 모델은 오답보다 더 위험한 무의미한 정답을 만든다. CCTV에서는 ‘무슨 일이 일어났는가’가 중심인데, v5-code는 그 슬롯 자체가 없었다.",
      "고정 간격 프레임 추출은 급정거와 낙상처럼 짧은 이벤트를 놓치기 쉬워, 장면 설명이 사건보다 빈 배경에 치우쳤다.",
      "타임스탬프 없이 frame description을 합치면, QA가 ‘언제’라는 질문을 받을 때 정답 근거를 한 덩어리 텍스트 안에서 다시 잃어버렸다.",
    ],
    timeline: [
      {
        label: "v5-code",
        change: "코딩 도메인 태그 유지",
        outcome: "이벤트 질문에 대해 ‘코드 없음’ 유형의 무의미 응답 발생",
        status: "fail",
      },
      {
        label: "v6-scene",
        change: "[장면][인물/사물][이벤트][텍스트]",
        outcome: "사람·차량·사건을 별도 슬롯으로 추출하기 시작",
        status: "progress",
      },
      {
        label: "+ Dynamic frames",
        change: "최소 프레임 수 보장",
        outcome: "급정거 직후와 낙상 직전 프레임이 모두 retrieval에 진입",
        status: "progress",
      },
      {
        label: "+ Timestamp store",
        change: "frame_desc에 시점 포함",
        outcome: "‘23초 직후’ 같은 시계열 질문까지 grounding 가능",
        status: "success",
      },
    ],
    finalAnswer: {
      answer:
        "23초 직후 검은 외투 인물은 미끄러지듯 중심을 잃고 바닥에 주저앉았고, 그 장면을 본 흰색 차량이 급정거한 뒤 주변 사람이 가까이 다가왔다.",
      summary:
        "도메인 태그를 바꾸고 타임스탬프를 붙인 뒤에는 ‘현실 장면 사건화’가 가능해졌고, QA가 장면을 자연어로 재구성할 수 있었다.",
      improvements: [
        { label: "Event recall", before: "0.38", after: "0.84" },
        { label: "Groundedness", before: "0.33", after: "0.78" },
        { label: "Temporal error", before: "±8초", after: "±2초" },
      ],
    },
    modelChoices: [
      {
        role: "Vision",
        model: "GPT-4o (v6-scene prompt)",
        reason: "일반 장면의 인물·차량·행동을 도메인 중립 구조로 뽑아내는 데 가장 안정적이었다.",
      },
      {
        role: "ASR",
        model: "미사용",
        reason: "CCTV 원본에 유효 음성이 거의 없어, 이번 실험은 시각 이벤트 retrieval에 집중하는 편이 더 설득력 있었다.",
      },
      {
        role: "Embedding",
        model: "BGE-M3",
        reason: "짧은 사건 태그와 타임스탬프 텍스트를 함께 임베딩해도 한국어 질의 응답 품질이 안정적이었다.",
      },
    ],
    techBadges: [
      "v6-scene Prompt",
      "Dynamic Frame Extraction",
      "Timestamped Context",
      "Event-centric QA",
      "BGE-M3",
      "Scene Diagnostics",
    ],
    comparison: {
      columns: ["버전", "프롬프트", "Event Recall", "GR", "메모"],
      rows: [
        ["Baseline", "v5-code", "0.38", "0.33", "도메인 미스매치"],
        ["Prompt shift", "v6-scene", "0.64", "0.58", "사건 태그 복원"],
        ["+ Dynamic frames", "v6-scene", "0.79", "0.71", "짧은 이벤트 포착"],
        ["+ Timestamp store", "v6-scene", "0.84", "0.78", "시간 질문 성공"],
      ],
    },
    learnings: [
      "Vision 프롬프트의 태그 구조는 모델 성능보다 먼저 도메인 적합성을 결정한다.",
      "현실 영상은 ‘무엇이 보이는가’보다 ‘언제 어떤 사건이 일어났는가’까지 함께 저장해야 검색이 쓸모 있어진다.",
      "짧은 이벤트를 다루는 실험에서는 프레임 추출 정책 자체가 retrieval 품질의 절반을 차지한다.",
    ],
    architecture: ["Scene change detection", "Vision v6-scene", "Timestamp merge", "Embedding", "Event QA"],
    teamNote:
      "CCTV 페이지의 수치와 답변은 실제 프롬프트 개선 방향을 바탕으로 구성한 더미 데이터지만, 태그 구조와 문제 원인은 저장소 문서와 일치한다.",
    snapshot: {
      baselineVisionVersion: "v5-code",
      finalVisionVersion: "v6-scene",
      eventQuestion: "흰색 차량이 급정거한 직후 검은 외투를 입은 사람에게 어떤 일이 일어났나요?",
      notes: [
        "Prompt mismatch was the primary bottleneck",
        "Dynamic frame interval prevented missed transient events",
      ],
      sources: [],
    },
    art: {
      variant: "cctv",
      base: "#110b0b",
      accent: "#7f1d1d",
      glow: "#fb923c",
      headline: "EVENT",
      eyebrow: "Prompt shift",
      tag: "Real-world",
    },
  },
  {
    slug: "movie",
    shortLabel: "04",
    title: "3-Speaker Movie Debate",
    kicker: "세 명이 동시에 말할 때 감정까지 뽑을 수 있는가",
    oneLiner: "같은 영화가 여러 구간에서 반복 언급되는 토론 영상에서는 화자와 감정이 retrieval의 좌표가 된다.",
    cardSummary:
      "단순 전사만으로는 ‘누가’와 ‘어떤 어조로’ 말했는지 잃어버린다. diarization, pitch metadata, semantic chunking을 결합해 특정 발화를 다시 찾게 했다.",
    dataset: "cinephile-worldcup / 39 min",
    duration: "39:00",
    artifact: "speaker-aware transcript + emotion metadata",
    question: "결승전을 두고 ‘맥빠지는 느낌’이라고 말한 사람은 누구이고, 어떤 맥락이었나요?",
    cardStats: [
      { label: "Speaker attribution", value: "0.42 → 0.91" },
      { label: "RP", value: "0.36 → 0.79" },
      { label: "Emotion cues", value: "1/4 → 4/4" },
    ],
    problemStatement: [
      "세 명의 화자가 겹치는 영화 토론 영상에서는 같은 영화 제목이 여러 구간에 흩어져 등장해, 단순 transcript embedding만으로는 정답 구간을 다시 집기 어렵다.",
      "특히 ‘누가’, ‘어떤 감정 상태에서’라는 질문은 화자 분리와 메타데이터가 없으면 비슷한 문장이 여러 구간에서 서로 섞여 들어온다.",
    ],
    firstAttempt: {
      answer: "김간지가 결승전이 지루하다고 말했다고 보입니다.",
      note: "동일 영화가 반복 언급된 여러 청크가 섞이며 화자 attribution이 뒤틀린 전형적인 실패였다.",
    },
    failureAnalysis: [
      "고정 30초 청킹은 한 사람의 발언을 중간에 자르거나, 다른 사람의 리액션을 같은 청크에 붙여 speaker signal을 흐리게 만들었다.",
      "감정 관련 질문은 텍스트 내용만으로는 부족하다. ‘맥빠진다’ 같은 표현이 있어도 실제로 누가 가장 단호하게 말했는지는 pitch variance 같은 보조 신호가 있어야 분리된다.",
      "영화 제목이 여러 번 반복되는 토론 영상은 semantic chunking이 없으면 주제 경계가 무너져 retrieval precision이 빠르게 떨어진다.",
    ],
    timeline: [
      {
        label: "Baseline",
        change: "고정 청킹 + 메타 없음",
        outcome: "유사 청크가 여러 개 섞이며 speaker attribution 실패",
        status: "fail",
      },
      {
        label: "+ Diarization",
        change: "speaker ID 부착",
        outcome: "누가 말했는지는 보이기 시작했지만 감정 질문은 여전히 흔들림",
        status: "progress",
      },
      {
        label: "+ Pitch metadata",
        change: "격앙 구간 통계 추가",
        outcome: "‘단호함’, ‘격렬함’ 같은 질문이 특정 구간으로 수렴",
        status: "progress",
      },
      {
        label: "+ Semantic chunking",
        change: "토픽 경계 보존",
        outcome: "결승전 논의 전체가 하나의 의미 단위로 묶이며 최종 답변 복원",
        status: "success",
      },
    ],
    finalAnswer: {
      answer:
        "잘린 영상 기준 36분대에 허키가 결승 대진을 두고 ‘조금 맥빠지는 느낌’이라고 말했고, 결승전 긴장감이 예상보다 약하다는 맥락에서 나온 발화였다.",
      summary:
        "speaker ID와 pitch metadata를 함께 붙인 뒤에는 같은 영화 제목이 반복돼도 ‘특정 사람의 특정 어조’를 다시 꺼낼 수 있었다.",
      improvements: [
        { label: "Speaker attribution", before: "0.42", after: "0.91" },
        { label: "Retrieval precision", before: "0.36", after: "0.79" },
        { label: "Emotion cue hit rate", before: "1/4", after: "4/4" },
      ],
    },
    modelChoices: [
      {
        role: "ASR / Diarization",
        model: "WhisperX + pyannote",
        reason: "화자 경계와 단어 타임스탬프를 함께 맞춰야 토론형 영상에서 speaker-aware chunking이 가능했다.",
      },
      {
        role: "Emotion metadata",
        model: "Pitch stats + GPT-4o-mini scene notes",
        reason: "감정을 LLM 한 번에 맡기기보다, 음성 피치 통계와 장면 메모를 조합하는 편이 더 재현성이 높았다.",
      },
      {
        role: "Embedding",
        model: "BGE-M3 + semantic chunking",
        reason: "긴 영화 토론처럼 주제가 다시 돌아오는 영상에서 의미 단위 chunk가 retrieval precision을 크게 올렸다.",
      },
    ],
    techBadges: [
      "Speaker Diarization",
      "WhisperX",
      "Pitch Metadata",
      "Semantic Chunking",
      "BGE-M3",
      "Speaker-aware Retrieval",
    ],
    comparison: {
      columns: ["조건", "화자 식별", "감정 정합", "RP", "결과"],
      rows: [
        ["Baseline", "0.42", "0.31", "0.36", "실패"],
        ["+ Diarization", "0.73", "0.44", "0.51", "부분 개선"],
        ["+ Pitch metadata", "0.81", "0.68", "0.63", "격앙 구간 포착"],
        ["+ Semantic chunking", "0.91", "0.76", "0.79", "성공"],
      ],
    },
    learnings: [
      "토론 영상에서는 텍스트보다 화자와 구간 메타데이터가 retrieval의 핵심 좌표가 된다.",
      "감정은 최종 라벨이라기보다, 적절한 청크를 끌어오기 위한 retrieval signal로 쓰일 때 더 유용했다.",
      "시맨틱 청킹은 긴 논의가 여러 분에 걸쳐 이어지는 콘텐츠에서 가장 큰 체감 개선을 만든다.",
    ],
    architecture: ["WhisperX align", "Speaker diarization", "Pitch statistics", "Semantic chunking", "Metadata-aware QA"],
    teamNote:
      "영화 토론 실험은 저장소 질문셋과 검증 논리를 바탕으로 더미 수치를 구성했다. 질문과 정답 구간은 실제 노트에 맞춰 넣었다.",
    snapshot: {
      dataset: "cinephile-worldcup_21-60min",
      questionTrack: "Track 4 — Pitch/감정 메타데이터 검증",
      goldHint: "36:00~, 허키가 '결승전이 조금 맥빠지는 느낌'",
      sources: [],
    },
    art: {
      variant: "movie",
      base: "#0a1013",
      accent: "#14532d",
      glow: "#f87171",
      headline: "3 speakers",
      eyebrow: "Metadata retrieval",
      tag: "Debate",
    },
  },
];

export const experimentMap = new Map(
  experiments.map((experiment) => [experiment.slug, experiment]),
);

export function getExperiment(slug: string) {
  return experimentMap.get(slug);
}
