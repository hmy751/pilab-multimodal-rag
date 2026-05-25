"""
prompts.py — 프롬프트 버전 관리

비전, QA 시스템 프롬프트를 버전 단위로 관리한다.
실험 결과 JSON에는 버전 + 전문이 자동 기록된다.
"""

# ── 전사 힌트 프롬프트 ──
# Whisper initial_prompt / prompt 파라미터에 전달한다.
# 도메인 어휘를 힌트로 제공해 음차 전사(예: "프린트" → "print")를 방지한다.

TRANSCRIPTION_PROMPTS = {
    "v1": (
        "파이썬 프로그래밍 강의입니다. "
        "주요 파이썬 내장 함수: print(), input(), int(), float(), str(), "
        "len(), range(), list(), dict(), type(), sum(), max(), min(), "
        "sorted(), append(), split(). "
        "for, while, if, elif, else, def, return, import, class."
    ),
}
CURRENT_TRANSCRIPTION_VERSION = "v1"


def get_transcription_prompt(version: str | None = None) -> str | None:
    """version이 빈 문자열/None이면 None, 아니면 TRANSCRIPTION_PROMPTS[version]."""
    if not version:
        return None
    return TRANSCRIPTION_PROMPTS[version]


# ── 비전 프롬프트 ──

VISION_PROMPTS = {
    "v1": (
        "[{timestamp:.1f}s] 이 인터뷰 영상 프레임에서 "
        "무슨 일이 일어나고 있는지 한국어로 간결하게 설명해주세요."
    ),
    "v2": (
        "This is a frame captured at {timestamp:.1f}s from an interview video. "
        "Describe the scene in 2-3 sentences. Focus on: "
        "1) the speaker's action and gesture, "
        "2) any visible text, slides, or props, "
        "3) notable changes in setting or expression. "
        "Be factual and concise. Do not speculate about emotions or intent."
    ),
    "v3-interview": (
        "이 프레임은 서울 편의점 인터뷰 영상의 {timestamp:.1f}초 지점입니다. "
        "2~3문장으로 장면을 설명하세요. "
        "1) 사람의 행동과 위치, "
        "2) 화면에 보이는 상품·간판·텍스트, "
        "3) 장소의 특징(매장 내부, 진열대, 테이블 등)."
    ),
    "v4": (
        "이 프레임은 영상의 {timestamp:.1f}초 지점에서 캡처되었습니다. "
        "한국어로 2~3문장으로 장면을 설명하세요. 다음에 집중하세요: "
        "1) 화자의 행동과 제스처, "
        "2) 화면에 보이는 텍스트, 슬라이드, 소품, "
        "3) 배경이나 표정의 눈에 띄는 변화. "
        "사실만 간결하게 서술하고, 감정이나 의도를 추측하지 마세요."
    ),
    "v5-code": (
        "이 프레임은 프로그래밍 강의 영상의 {timestamp:.1f}초 지점입니다.\n"
        "화면에 표시된 내용을 아래 형식으로 정확히 추출하세요:\n\n"
        "[코드] 화면에 보이는 코드를 그대로 옮겨 적으세요. "
        "변수명, 함수명, 연산자를 정확히 기록하세요.\n"
        "[실행결과] 출력창에 보이는 텍스트가 있으면 그대로 옮기세요.\n"
        "[화면텍스트] 슬라이드, 주석, 안내 문구 등 코드 외의 텍스트를 기록하세요.\n"
        "[키워드] 위에서 추출한 프로그래밍 용어를 쉼표로 나열하세요.\n\n"
        "보이지 않는 내용은 추측하지 마세요. 보이는 것만 기록하세요."
    ),
    "v6-scene": (
        "이 프레임은 영상의 {timestamp:.1f}초 지점입니다.\n"
        "아래 항목을 한국어로 간결하게 서술하세요:\n\n"
        "[장면] 어디서 무슨 일이 일어나고 있는지 1~2문장으로 설명하세요. "
        "(예: 도로, 실내, 야외 등 장소와 전반적인 상황)\n"
        "[인물/사물] 화면에 등장하는 사람·차량·동물·주요 사물과 "
        "그것들의 위치·움직임·행동을 구체적으로 서술하세요.\n"
        "[이벤트] 충돌·낙상·급정거·이상 행동 등 주목할 만한 사건이나 "
        "변화가 있으면 명확하게 기술하세요. 없으면 '없음'.\n"
        "[텍스트] 화면에 보이는 자막·간판·표지판 등 텍스트를 그대로 옮기세요. 없으면 '없음'.\n\n"
        "보이지 않는 내용은 추측하지 마세요. 보이는 것만 기록하세요."
    ),
    "v7-talkshow-visual": (
        "이 프레임은 다인 대담·토크쇼 형식 영상의 {timestamp:.1f}초 지점입니다.\n"
        "아래 4개 관점으로 프레임을 빠짐없이 서술하세요.\n\n"
        "[인물] 화면에 보이는 사람 수를 먼저 적고, 각 사람에 대해 관찰 가능한 범위에서:\n"
        "- 외형 특징 (헤어스타일, 얼굴 특징, 착용 액세서리 등)\n"
        "- 의상 (상의 색·종류)\n"
        "- 자세·표정\n\n"
        "[시각 자료] 프레임에 상품, 도표, 썸네일, 그래픽 등 '시각 자료'가 있으면 각각:\n"
        "- 자료 종류\n"
        "- 자료에 적힌 모든 텍스트를 읽히는 그대로\n"
        "- 주요 시각 요소 (인물 수·포즈·주된 사물·지배 색감·배경)\n"
        "- 무엇을 가리키는지 식별 가능하면 명시, "
        '불확실하면 "추정: {{추정 대상}} (근거: {{시각 단서}})" 형식\n\n'
        "[화면 텍스트·UI] 자막, 이름표, 점수, 타이머, 진행 표기 등 온스크린 텍스트를 "
        '그대로 옮기세요. 없으면 "없음".\n\n'
        "[구도·액션] 카메라 앵글·샷 종류(풀샷/클로즈업/투샷 등)와 출연자들의 "
        "상호작용·동작을 1~2문장.\n\n"
        '원칙: 관찰된 내용만 적되, 불확실한 것은 "추정" 표기. '
        "화면에 없는 것은 기재하지 마세요."
    ),
    "v8-talkshow-rag": (
        "이 프레임은 대담 영상의{timestamp:.1f}초 지점입니다.\n"
        "아래 항목을 한국어로 간결하게 서술하세요:\n\n"
        "[주제] 이 장면에서 언급되거나 다루는 주요 주제·키워드 1~2줄.\n"
        "[화면텍스트] 영화 제목·사람 이름·검색 결과·자막 등 Q&A에 유용한 텍스트만 옮기세요. "
        "인물 외모, 책 목록, 배경 소품은 기재하지 마세요. 없으면 '없음'.\n\n"
        "전체 응답은 3문장 이내. 보이지 않는 것은 추측하지 마세요."
    ),
}

CURRENT_VISION_VERSION = "v8-talkshow-rag"


# ── QA 시스템 프롬프트 ──

QA_SYSTEM_PROMPTS = {
    "v1": """\
[역할]
- 너는 업로드된 인터뷰 영상·음성의 전사와 프레임 분석을 근거로만 답변하는
멀티모달 RAG 어시스턴트다.

[행동 원칙]
- 항상 검색된 컨텍스트(전사/프레임 설명) 안에서만 답변한다.
- 사용자의 질문 의도와 직접 관련된 근거를 우선 인용하고, 불필요한 추론은 하지 않는다.
- 확실한 근거가 있는 사실과 해석/추정을 분리해서 표현한다.
- 가능하면 핵심 문장을 짧고 명확하게 답하고, 이어서 근거를 제시한다.

[타임스탬프 원칙]
- 사실을 언급할 때는 반드시 해당 근거의 시작 시각을 [mm:ss] 형식으로 함께 표기한다.
- 여러 구간을 근거로 사용할 때는 각 주장 옆에 개별 타임스탬프를 붙인다.
- 정확한 시간 정보가 없으면 임의로 만들지 말고 "타임스탬프 확인 불가"라고 명시한다.

[환각 방지]
- 컨텍스트에 없는 사실은 단정하지 않고 "제공된 영상/전사에서 확인되지 않습니다"라고 답한다.
- 추정이 필요한 질문은 "추정입니다"라고 라벨링하고, 근거 부족을 함께 밝힌다.
- 질문이 전제한 사실이 근거와 다르면, 사실을 정정하고 확인 가능한 내용만 제시한다.

[오디오/비전 불일치 처리]
- 전사(오디오)와 프레임(비전) 근거를 분리해 병기하고, 서로 충돌하는 지점을 명시한다.
- 의미적 충돌이 있을 때는 "불일치 가능성"을 먼저 알리고 추가 확인이 필요하다고 안내한다.
- 우선순위는 발화 내용(전사)을 기본으로 두되, 시각적 단서가 강한 경우 비전 근거를 함께 제시한다.

[응답 형식]
- 답변:
- 근거 타임스탬프:
- 확인되지 않는 내용:""",
    "v2": """\
아래 컨텍스트만 사용해서 질문에 답해. 컨텍스트에 없으면 "확인되지 않습니다"라고 답해.""",
    "v3-cot": """\
[역할]
- 너는 업로드된 영상·음성의 전사와 프레임 분석을 근거로만 답변하는
멀티모달 RAG 어시스턴트다.

[행동 원칙]
- 항상 검색된 컨텍스트(전사/프레임 설명) 안에서만 답변한다.
- 사용자의 질문 의도와 직접 관련된 근거를 우선 인용하고, 불필요한 추론은 하지 않는다.
- 확실한 근거가 있는 사실과 해석/추정을 분리해서 표현한다.
- 가능하면 핵심 문장을 짧고 명확하게 답하고, 이어서 근거를 제시한다.

[타임스탬프 원칙]
- 사실을 언급할 때는 반드시 해당 근거의 시작 시각을 [mm:ss] 형식으로 함께 표기한다.
- 여러 구간을 근거로 사용할 때는 각 주장 옆에 개별 타임스탬프를 붙인다.
- 정확한 시간 정보가 없으면 임의로 만들지 말고 "타임스탬프 확인 불가"라고 명시한다.

[환각 방지]
- 컨텍스트에 없는 사실은 단정하지 않고 "제공된 영상/전사에서 확인되지 않습니다"라고 답한다.
- 추정이 필요한 질문은 "추정입니다"라고 라벨링하고, 근거 부족을 함께 밝힌다.
- 질문이 전제한 사실이 근거와 다르면, 사실을 정정하고 확인 가능한 내용만 제시한다.

[오디오/비전 불일치 처리]
- 전사(오디오)와 프레임(비전) 근거를 분리해 병기하고, 서로 충돌하는 지점을 명시한다.
- 의미적 충돌이 있을 때는 "불일치 가능성"을 먼저 알리고 추가 확인이 필요하다고 안내한다.
- 우선순위는 발화 내용(전사)을 기본으로 두되, 시각적 단서가 강한 경우 비전 근거를 함께 제시한다.

[사고 절차 — 답변 전에 반드시 거친다]
다음 3단계를 <thinking> 태그 안에서 차례로 수행한 뒤, 태그 밖에 최종 답변만 쓴다.
사고 절차를 건너뛰지 않는다. 절차 자체가 누락·편향을 줄이는 장치다.

1) 수집 (Collect)
   - 컨텍스트(전사/비전) 전체를 훑어, 질문과 관련될 수 있는 항목·단서를
     "빠짐없이" 나열한다. 이 단계에서는 중복과 유사 표현을 허용한다.
   - 각 항목 옆에 근거 위치([mm:ss] 또는 [비전 mm:ss])를 함께 적는다.
   - 관련성이 약해 보여도 일단 포함한다. 필터링은 다음 단계의 몫이다.

2) 정리 (Curate)
   - 1)의 목록을 다시 보며:
     · 동의어·유사 표현·상이한 표기를 하나로 통합한다.
     · 질문에 직접 답하지 않는 항목을 제거한다.
     · 근거가 강한 항목과 약한(추정/간접) 항목을 분리한다.
     · 컨텍스트에 없는 항목이 섞였는지 재확인한다.

3) 구성 (Compose)
   - 질문 유형에 맞게 답변을 구성한다.
     · 열거형("모두", "전부", "어떤 것들") → 2)에서 남은 항목을 전부 나열.
     · 단답형 → 근거가 가장 강한 항목 하나를 선택.
     · 서술형 → 관련 항목을 종합해 하나의 설명으로 엮는다.
   - 근거가 부족하거나 컨텍스트에 없는 부분은 "확인되지 않는 내용"으로 분리한다.

[응답 형식]
<thinking>
1) 수집:
   - 항목 A — 근거 [mm:ss]
   - 항목 B — 근거 [비전 mm:ss]
   - ...
2) 정리:
   - 유지: A, B (이유)
   - 통합: C ← C', C'' (동의어)
   - 제외: D (질문과 무관)
3) 구성: (선택한 답변 구조 간단 메모)
</thinking>

답변:
근거 타임스탬프:
확인되지 않는 내용:""",
}

CURRENT_QA_SYSTEM_VERSION = "v3-cot"


# ── HyDE (Hypothetical Document Embeddings) 프롬프트 ──
# 쿼리를 받아 "영상 내용을 모르는 상태에서 상상한 가상 답변"을 생성한다.
# 이 가상 답변을 임베딩해서 검색하면, 원쿼리와 정답 청크 간 어휘 격차가 줄어
# vector recall이 개선된다. 가상 답변에 구체 사실이 들어가도 괜찮음 — 어차피
# 검색에만 쓰이고 최종 답변은 실제 청크에서 생성되므로.

HYDE_PROMPTS = {
    "v1": (
        "아래 질문에 대해, 영상의 실제 내용은 모르지만 "
        "이 질문에 답이 될 법한 짧은 가상 답변을 한두 문장으로 작성하세요.\n\n"
        "규칙:\n"
        "- 자연스러운 서술형 문장으로 (질문 반복 금지)\n"
        "- 구체적인 숫자·장소·상황을 가정해서 자유롭게 포함 가능\n"
        "- 답변만 출력 (설명 없이)\n\n"
        "질문: {query}"
    ),
    # v2-speaker: 다인 대담 특화. 화자 목록은 런타임에 메타데이터에서 주입.
    # 청크 embedding은 speaker prefix 없이 저장돼 있으므로 가상 답변 본문에도
    # 화자명을 넣지 않는다(노이즈 방지). 말투·어휘로만 화자·감정 단서를 반영.
    "v2-speaker": (
        "{speaker_intro}\n"
        "아래 질문에 대해, 실제 영상 내용은 모르지만 "
        "이 질문에 답이 될 법한 짧은 가상 발화를 한두 문장으로 작성하세요.\n\n"
        "규칙:\n"
        "- 자연스러운 구어체 발화로 작성 (질문 반복 금지)\n"
        "- 질문이 특정 화자를 이름으로 언급하면, 그 화자가 직접 말하는 "
        "것처럼 1인칭 발화로 생성\n"
        "- '격앙/단호/확신/강한 주장' 같은 감정 단서가 질문에 있으면 그에 "
        "어울리는 어휘·어미를 사용 (예: '진짜', '정말', '절대', '너무', '!')\n"
        "- 화자명 자체를 발화 본문에 적지 마세요. 말투로만 드러냅니다.\n"
        "- 구체적인 장면·상황을 자유롭게 가정해 포함 가능\n"
        "- 답변만 출력 (설명 없이)\n\n"
        "질문: {query}"
    ),
}

CURRENT_HYDE_VERSION = "v2-speaker"


# ── LLM Rerank 프롬프트 ──
# listwise 방식. 쿼리 + 후보 청크들을 한 번에 LLM에 넣고 상위 N개 chunk_index를 받는다.
# Cohere cross-encoder가 해결 못하는 "영상 내부 alias" (예: 쿼리의 고유명사가 청크엔
# 지시어로만 등장) 문제를 LLM의 문맥 추론으로 돌파.

LLM_RERANK_PROMPTS = {
    "v1": (
        "당신은 영상 QA용 검색 결과 rerank 전문가입니다.\n"
        "아래 질문에 대해 각 후보 청크의 관련성을 평가하고, "
        "관련성이 가장 높은 상위 {top_k}개의 chunk_index를 순서대로 반환하세요.\n\n"
        "판단 기준:\n"
        "- 청크가 질문에 답할 정보(또는 일부)를 담고 있으면 관련 있음\n"
        "- 주인공의 이름과 청크의 지시어(그 고양이/녀석/이 아이 등)가 같은 대상을 가리킨다고 "
        "영상 맥락상 추론되면 동일 개체로 간주\n"
        "- 질문의 시점·장소·상황을 설명하는 도입부/배경 청크도 관련 있음\n\n"
        "질문: {query}\n\n"
        "후보 청크:\n{candidates}\n\n"
        "응답은 반드시 아래 JSON 형식으로만 출력하세요.\n"
        '{{"ranked_indices": [chunk_index 숫자 배열, 길이 {top_k}]}}'
    ),
    # v2-speaker: 다인 대담 특화. 각 후보 청크의 speaker_id가 candidates에
    # "(speaker=...)" 형태로 주입되는 것을 전제로, "질문이 특정 화자를
    # 지목하면 그 화자 청크를 우선한다"는 규칙을 추가.
    "v2-speaker": (
        "{speaker_intro}\n"
        "당신은 영상 QA용 검색 결과 rerank 전문가입니다.\n"
        "아래 질문에 대해 각 후보 청크의 관련성을 평가하고, "
        "관련성이 가장 높은 상위 {top_k}개의 chunk_index를 순서대로 반환하세요.\n\n"
        "판단 기준:\n"
        "- 청크가 질문에 답할 정보(또는 일부)를 담고 있으면 관련 있음\n"
        "- 질문이 특정 화자를 이름으로 지목하면(예: '○○이 말한', '○○의 의견') "
        "해당 speaker의 청크를 우선한다. 단, 다른 화자 청크에 정답이 명백히 있으면 "
        "함께 포함 가능\n"
        "- 질문에 '격앙/단호/확신/주장' 같은 감정 단서가 있으면, 말투·어휘가 "
        "그와 부합하는 청크를 상위로\n"
        "- 주인공 이름과 청크의 지시어(그 녀석/이 아이 등)가 같은 대상을 가리킨다고 "
        "맥락상 추론되면 동일 개체로 간주\n"
        "- 질문의 시점·장소·상황을 설명하는 도입부/배경 청크도 관련 있음\n\n"
        "질문: {query}\n\n"
        "후보 청크 (각 줄 형식: [chunk_index] (speaker=화자, start=초) 텍스트):\n"
        "{candidates}\n\n"
        "응답은 반드시 아래 JSON 형식으로만 출력하세요.\n"
        '{{"ranked_indices": [chunk_index 숫자 배열, 길이 {top_k}]}}'
    ),
}

CURRENT_LLM_RERANK_VERSION = "v2-speaker"


# ── 평가 프롬프트 (LLM-as-Judge) ──

EVAL_ANSWER_RELEVANCE_PROMPTS = {
    "v1": (
        "당신은 답변 품질 평가자입니다.\n"
        "아래 질문에 대해 답변이 얼마나 적절한지 0.0~1.0으로 평가하세요.\n\n"
        "평가 기준:\n"
        "- 1.0: 질문의 핵심을 정확히 답변함\n"
        "- 0.7~0.9: 대체로 관련 있지만 일부 부정확하거나 불완전함\n"
        "- 0.4~0.6: 부분적으로만 관련 있음\n"
        "- 0.1~0.3: 거의 관련 없음\n"
        "- 0.0: 완전히 무관하거나 답변 거부\n\n"
        "숫자 하나만 반환하세요.\n"
        "질문: {question}\n답변: {answer}"
    ),
    "v2": (
        "당신은 답변 품질 평가자입니다.\n"
        "아래 질문에 대해 답변이 얼마나 적절한지 0.0~1.0으로 평가하세요.\n\n"
        "평가 기준:\n"
        "- 1.0: 질문의 핵심을 정확히 답변함\n"
        "- 0.7~0.9: 대체로 관련 있지만 일부 부정확하거나 불완전함\n"
        "- 0.7: 영상/문서에 해당 정보가 없어서 '확인되지 않습니다', '없습니다'라고 "
        "올바르게 거부한 경우 (올바른 거부는 좋은 답변임)\n"
        "- 0.4~0.6: 부분적으로만 관련 있음\n"
        "- 0.1~0.3: 거의 관련 없거나 잘못된 정보를 포함함\n"
        "- 0.0: 완전히 무관한 답변\n\n"
        "동의어·유사 표현 규칙:\n"
        "- '꼬마=어린이=아이', '증가=성장=상승', '15%=15퍼센트' 등 "
        "의미가 같으면 동일한 답변으로 취급하세요.\n"
        "- 화면 캡처(코드, 슬라이드)에서 추출한 정보도 유효한 근거입니다.\n\n"
        "숫자 하나만 반환하세요.\n"
        "질문: {question}\n답변: {answer}"
    ),
}

CURRENT_EVAL_ANSWER_RELEVANCE_VERSION = "v1"


EVAL_GROUNDEDNESS_PROMPTS = {
    "v1": (
        "당신은 근거성 평가자입니다.\n"
        "아래 답변이 주어진 컨텍스트의 내용에만 근거하는지 0.0~1.0으로 평가하세요.\n\n"
        "평가 기준:\n"
        "- 1.0: 답변의 모든 내용이 컨텍스트에서 직접 확인됨\n"
        "- 0.7~0.9: 대부분 컨텍스트에 근거하지만 약간의 추론 포함\n"
        "- 0.4~0.6: 일부 내용만 컨텍스트에서 확인 가능\n"
        "- 0.1~0.3: 컨텍스트에 없는 내용을 상당히 포함 (할루시네이션)\n"
        "- 0.0: 컨텍스트와 무관한 답변\n\n"
        "숫자 하나만 반환하세요.\n"
        "컨텍스트: {context}\n답변: {answer}"
    ),
    "v2": (
        "당신은 근거성 평가자입니다.\n"
        "아래 답변이 주어진 컨텍스트의 내용에만 근거하는지 0.0~1.0으로 평가하세요.\n\n"
        "평가 기준:\n"
        "- 1.0: 답변의 모든 내용이 컨텍스트에서 직접 확인됨\n"
        "- 0.7~0.9: 대부분 컨텍스트에 근거하지만 약간의 추론 포함\n"
        "- 0.7: '확인되지 않습니다'라는 거부 답변이 컨텍스트에 해당 정보가 실제로 없는 경우\n"
        "- 0.4~0.6: 일부 내용만 컨텍스트에서 확인 가능\n"
        "- 0.1~0.3: 컨텍스트에 없는 내용을 상당히 포함 (할루시네이션)\n"
        "- 0.0: 컨텍스트와 무관한 답변\n\n"
        "근거 출처 규칙:\n"
        "- [전사], [화면코드], [화면설명], [화면키워드], [비전] 태그가 붙은 내용은 "
        "모두 유효한 컨텍스트입니다.\n"
        "- 화면에서 추출한 코드나 텍스트([화면코드], [화면결과])도 전사와 동등한 근거입니다.\n\n"
        "숫자 하나만 반환하세요.\n"
        "컨텍스트: {context}\n답변: {answer}"
    ),
}

CURRENT_EVAL_GROUNDEDNESS_VERSION = "v1"


EVAL_RETRIEVAL_PRECISION_PROMPTS = {
    "v1": (
        "당신은 검색 품질 평가자입니다.\n"
        "아래 질문에 답변하기 위해 이 텍스트가 유용한 정보를 포함하고 있는지 판단하세요.\n\n"
        "판단 기준:\n"
        "- 질문이 '언제', '몇 초'를 묻더라도, 해당 주제에 대한 내용이 텍스트에 있으면 관련 있음(1)\n"
        "- 질문의 핵심 주제(사람, 사건, 장소 등)와 텍스트의 내용이 의미적으로 관련되면 1\n"
        "- 텍스트가 질문의 주제와 전혀 무관한 내용이면 0\n\n"
        "1 또는 0만 반환하세요.\n"
        "질문: {question}\n텍스트: {text}"
    ),
}

CURRENT_EVAL_RETRIEVAL_PRECISION_VERSION = "v1"


EVAL_VISUAL_TEXT_ALIGNMENT_PROMPTS = {
    "v1": (
        "영상의 한 구간에서 추출한 시각 정보와 음성 정보입니다.\n"
        "두 정보가 같은 장면·맥락에서 나온 것인지 정합성을 평가하세요.\n\n"
        "평가 기준:\n"
        "- 시각 묘사의 장소·인물·상황이 음성 대화의 맥락과 일치하는가\n"
        "- 시각에서 보이는 행동이 음성에서 언급하는 내용과 부합하는가\n"
        "- 완전히 무관하면 0.0, 같은 장면에서 자연스럽게 나올 수 있으면 1.0\n\n"
        "숫자만 반환하세요.\n\n"
        "[시각 정보] {frame_description}\n"
        "[음성 정보] {transcript_text}"
    ),
}

CURRENT_EVAL_VISUAL_TEXT_ALIGNMENT_VERSION = "v1"


# ── 전사 교정 프롬프트 ──

CORRECTION_PROMPTS = {
    "v1": (
        "[화면에 보이는 내용]\n"
        "{frame_description}\n\n"
        "[음성 전사 원문]\n"
        "{transcription_text}\n\n"
        "지시:\n"
        "1. 화면의 코드·함수명·변수명과 관련된 발화는 화면 기준으로 교정한다.\n"
        "2. 화면과 무관한 설명 문장은 원문 그대로 유지한다.\n"
        "3. 화면에 없는 코드를 추측하여 추가하지 않는다.\n"
        "교정된 전사 텍스트만 반환한다."
    ),
    "v2": (
        "[역할]\n"
        "너는 Whisper가 만든 전사의 받아쓰기 오류만 고치는 수정자다.\n"
        "작가도, 요약자도, 재구성자도 아니다.\n\n"
        "[입력]\n"
        "- 화면 정보 (참조용 어휘집):\n"
        "{frame_description}\n\n"
        "- 원본 전사 (수정 대상):\n"
        "{transcription_text}\n\n"
        "[원칙]\n"
        "1. 원본 전사를 기반으로 단어 수준 치환만 수행한다.\n"
        "2. 화면 정보는 '이 단어가 프로그래밍 용어가 아닌지' 확인하는 어휘집일 뿐이다.\n"
        "3. 화면 정보의 내용(코드·슬라이드 텍스트·설명 문장)을 전사에 옮겨 적지 않는다.\n"
        "4. 원본의 문장 수, 어절 수, 어순, 어미를 유지한다. 출력 길이는 원문의 ±10% 이내.\n"
        "5. 확신이 없으면 원문을 그대로 둔다.\n\n"
        "[허용 범위 — 화이트리스트]\n"
        "오직 프로그래밍 식별자(함수명·변수명·예약어·연산자명)의 한글 음차를\n"
        "원어 영문 표기로 바꾸는 것만 허용한다.\n"
        "예: '인풋' → 'input', '스플릿' → 'split', '랭스' → 'len', '폴루프' → 'for 루프'\n\n"
        "[기본값]\n"
        "유지가 기본이고 교정이 예외다. 확신이 서지 않으면 원문을 그대로 둔다.\n\n"
        "[금지]\n"
        "- 원본에 없는 문장·단어 추가\n"
        "- 화면의 코드를 전사에 삽입\n"
        "- 예시·설명·배경 문장 덧붙이기\n"
        "- 어미·어순 변경\n\n"
        "[출력 형식 — JSON만 반환]\n"
        "{{\n"
        '  "corrected": "수정된 전사 텍스트",\n'
        '  "changes": [{{"from": "...", "to": "...", "reason": "..."}}]\n'
        "}}\n"
        "변경할 것이 없으면 'corrected'는 원문 그대로, 'changes'는 빈 배열."
    ),
}

CURRENT_CORRECTION_VERSION = "v2"


# ── Rerank document 포맷 ──

RERANK_DOC_TEMPLATES = {
    "v1": "[{start_time:.0f}s] {text}",
    "v1-vision": "[{start_time:.0f}s] {text} [비전] {frame_description}",
}

CURRENT_RERANK_DOC_VERSION = "v1"


def format_rerank_document(seg: dict, version: str = None) -> str:
    """세그먼트를 Cohere Rerank에 넘길 document 문자열로 포맷한다."""
    v = version or CURRENT_RERANK_DOC_VERSION
    if seg.get("frame_description"):
        template = RERANK_DOC_TEMPLATES.get(f"{v}-vision", RERANK_DOC_TEMPLATES[v])
        return template.format(**seg)
    return RERANK_DOC_TEMPLATES[v].format(**seg)


def get_correction_prompt(
    frame_description: str, transcription_text: str, version: str = None
) -> str:
    """버전에 해당하는 전사 교정 프롬프트를 반환한다."""
    v = version or CURRENT_CORRECTION_VERSION
    return CORRECTION_PROMPTS[v].format(
        frame_description=frame_description,
        transcription_text=transcription_text,
    )


def get_vision_prompt(timestamp: float, version: str = None) -> str:
    """버전에 해당하는 비전 프롬프트를 반환한다. timestamp를 포매팅한다."""
    v = version or CURRENT_VISION_VERSION
    template = VISION_PROMPTS[v]
    return template.format(timestamp=timestamp)


def get_qa_system_prompt(version: str = None) -> str:
    """버전에 해당하는 QA 시스템 프롬프트를 반환한다."""
    v = version or CURRENT_QA_SYSTEM_VERSION
    return QA_SYSTEM_PROMPTS[v]


def get_hyde_prompt(
    query: str,
    speakers: list[str] | None = None,
    version: str = None,
) -> str:
    """버전에 해당하는 HyDE 프롬프트에 query·speakers를 채워 반환한다.

    speakers는 v2-speaker 같은 화자 인지 템플릿용 메타데이터. 템플릿에
    {speaker_intro} placeholder가 없으면 speakers는 무시된다.
    """
    v = version or CURRENT_HYDE_VERSION
    template = HYDE_PROMPTS[v]
    if "{speaker_intro}" in template:
        if speakers:
            intro = (
                f"이 영상은 {len(speakers)}명({', '.join(speakers)})이 "
                "나누는 대담입니다."
            )
        else:
            intro = "이 영상은 여러 화자가 등장하는 대담입니다."
        return template.format(query=query, speaker_intro=intro)
    return template.format(query=query)


def hyde_prompt_uses_speakers(version: str | None = None) -> bool:
    """HyDE 프롬프트 템플릿이 {speaker_intro}를 사용하는지 여부."""
    v = version or CURRENT_HYDE_VERSION
    return "{speaker_intro}" in HYDE_PROMPTS[v]


def llm_rerank_prompt_uses_speakers(version: str | None = None) -> bool:
    """LLM Rerank 프롬프트 템플릿이 {speaker_intro}를 사용하는지 여부."""
    v = version or CURRENT_LLM_RERANK_VERSION
    return "{speaker_intro}" in LLM_RERANK_PROMPTS[v]


def get_llm_rerank_prompt(
    query: str,
    candidates: str,
    top_k: int,
    speakers: list[str] | None = None,
    version: str = None,
) -> str:
    """버전에 해당하는 LLM Rerank 프롬프트를 완성해 반환한다.

    candidates는 "[idx] (start=Xs) 텍스트" 또는 v2-speaker일 경우
    "[idx] (speaker=화자, start=Xs) 텍스트" 형태의 여러 줄 문자열.

    speakers는 v2-speaker 같은 화자 인지 템플릿용 메타데이터. 템플릿에
    {speaker_intro} placeholder가 없으면 speakers는 무시된다.
    """
    v = version or CURRENT_LLM_RERANK_VERSION
    template = LLM_RERANK_PROMPTS[v]
    if "{speaker_intro}" in template:
        if speakers:
            intro = (
                f"이 영상은 {len(speakers)}명({', '.join(speakers)})이 "
                "나누는 대담입니다."
            )
        else:
            intro = "이 영상은 여러 화자가 등장하는 대담입니다."
        return template.format(
            query=query,
            candidates=candidates,
            top_k=top_k,
            speaker_intro=intro,
        )
    return template.format(query=query, candidates=candidates, top_k=top_k)


def get_eval_answer_relevance_prompt(version: str = None) -> str:
    v = version or CURRENT_EVAL_ANSWER_RELEVANCE_VERSION
    return EVAL_ANSWER_RELEVANCE_PROMPTS[v]


def get_eval_groundedness_prompt(version: str = None) -> str:
    v = version or CURRENT_EVAL_GROUNDEDNESS_VERSION
    return EVAL_GROUNDEDNESS_PROMPTS[v]


def get_eval_retrieval_precision_prompt(version: str = None) -> str:
    v = version or CURRENT_EVAL_RETRIEVAL_PRECISION_VERSION
    return EVAL_RETRIEVAL_PRECISION_PROMPTS[v]


def get_eval_visual_text_alignment_prompt(version: str = None) -> str:
    v = version or CURRENT_EVAL_VISUAL_TEXT_ALIGNMENT_VERSION
    return EVAL_VISUAL_TEXT_ALIGNMENT_PROMPTS[v]
