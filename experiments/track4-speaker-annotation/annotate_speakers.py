"""Track 4 Step 2 — Phase 2: LLM 기반 화자 라벨링 스크립트.

사용법:
    pipenv run python experiments/track4-speaker-annotation/annotate_speakers.py \
        --media-id <uuid> [--model gpt-4o] [--dry-run]

동작:
    1) get_media_segments(media_id)로 청크 조회.
    2) 청크 리스트를 GPT(JSON 모드)에 전달, chunk_index → speaker 매핑 수신.
    3) update_segment_speaker로 DB에 저장 (--dry-run 시 출력만).

전제:
    - 화자는 3인 고정: 김간지 / 김민경 / 허키.
    - Phase 1 ALTER TABLE 완료 상태.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# experiments/ 하위 스크립트는 `python <path>` 직접 실행 시 프로젝트 루트가
# sys.path에 없으므로 app.* import가 실패한다. 루트를 명시적으로 주입.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from openai import OpenAI  # noqa: E402

from app.config import CONFIG  # noqa: E402
from app.supabase_utils import (  # noqa: E402
    get_media_segments,
    update_media_metadata,
    update_segment_speaker,
)

SPEAKERS: List[str] = ["김간지", "김민경", "허키"]

SYSTEM_PROMPT = """당신은 한국어 3인 대화 분석 전문가입니다.

화자는 김간지, 김민경, 허키 3명이며, 영화에 관한 자유로운 토크입니다.
각 발화 청크의 화자를 판단해 chunk_index → speaker 매핑을 만드세요.

판단 단서:
- 각 화자 말투·관심사의 연속성
- 앞뒤 청크 흐름 (같은 주제를 이어받거나 반박하는 패턴)
- 특정 화자를 부르거나 대답하는 구조

규칙:
- 반드시 주어진 모든 chunk_index에 speaker를 지정.
- speaker 값은 반드시 "김간지" | "김민경" | "허키" 중 하나.
- 판단이 애매한 청크는 직전 청크와 같은 화자를 택함.

응답 형식 (JSON):
{"labels": [{"chunk_index": 0, "speaker": "김민경"}, ...]}
"""


def _build_user_payload(segments: List[Dict[str, Any]]) -> str:
    rows = [
        {
            "chunk_index": s["chunk_index"],
            "start": round(s["start_time"], 1),
            "end": round(s["end_time"], 1),
            "text": s["text"],
        }
        for s in segments
    ]
    return (
        f"화자 후보: {SPEAKERS}\n"
        f"청크 개수: {len(rows)}\n\n"
        f"청크 리스트:\n{json.dumps(rows, ensure_ascii=False, indent=2)}"
    )


def label_speakers(
    segments: List[Dict[str, Any]],
    client: OpenAI,
    model: str,
) -> Dict[int, str]:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_payload(segments)},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )
    raw = response.choices[0].message.content or "{}"
    data = json.loads(raw)
    labels = data.get("labels", [])

    mapping: Dict[int, str] = {}
    for row in labels:
        idx = row.get("chunk_index")
        spk = row.get("speaker")
        if idx is None or spk not in SPEAKERS:
            continue
        mapping[int(idx)] = spk
    return mapping


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM 기반 청크 화자 라벨링")
    parser.add_argument("--media-id", required=True, help="대상 media_id (uuid)")
    parser.add_argument("--model", default="gpt-4o", help="OpenAI 모델명")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB update 없이 결과만 출력",
    )
    parser.add_argument(
        "--sync-metadata",
        action="store_true",
        help=(
            "GPT 호출 스킵. 기존 청크 speaker_id에서 DISTINCT를 집계해 "
            "media_files.metadata.speakers만 업데이트한다."
        ),
    )
    args = parser.parse_args()

    if args.sync_metadata:
        segments = get_media_segments(args.media_id)
        if not segments:
            print(
                f"ERROR: media_id={args.media_id}에 해당하는 청크가 없습니다.",
                file=sys.stderr,
            )
            return 1
        speakers = sorted(
            {s["speaker_id"] for s in segments if s.get("speaker_id")}
        )
        if not speakers:
            print(
                "ERROR: 청크에 speaker_id가 없습니다. 먼저 라벨링을 실행하세요.",
                file=sys.stderr,
            )
            return 1
        update_media_metadata(args.media_id, {"speakers": speakers})
        print(f"[meta] media_files.metadata.speakers = {speakers}")
        return 0

    if not CONFIG.openai_api_key:
        print("ERROR: OPENAI_API_KEY가 설정되지 않았습니다.", file=sys.stderr)
        return 1

    segments = get_media_segments(args.media_id)
    if not segments:
        print(
            f"ERROR: media_id={args.media_id}에 해당하는 청크가 없습니다.",
            file=sys.stderr,
        )
        return 1
    print(f"[fetch] 청크 {len(segments)}개 로드")

    client = OpenAI(api_key=CONFIG.openai_api_key)
    print(f"[label] {args.model}로 화자 라벨링 요청...")
    mapping = label_speakers(segments, client, model=args.model)
    print(f"[label] 응답 {len(mapping)}개 매핑 수신")

    missing = [
        s["chunk_index"] for s in segments if s["chunk_index"] not in mapping
    ]
    if missing:
        preview = missing[:10]
        print(
            f"WARN: {len(missing)}개 청크 라벨링 누락 — chunk_index={preview}...",
            file=sys.stderr,
        )

    counts: Dict[str, int] = {spk: 0 for spk in SPEAKERS}
    for spk in mapping.values():
        counts[spk] = counts.get(spk, 0) + 1
    print(f"[summary] 화자별 청크 수: {counts}")

    if args.dry_run:
        print("[dry-run] DB update 생략. 처음 5개:")
        for idx in sorted(mapping.keys())[:5]:
            print(f"  chunk_{idx} → {mapping[idx]}")
        return 0

    print("[update] DB에 speaker_id 저장 중...")
    for chunk_index, speaker in sorted(mapping.items()):
        update_segment_speaker(args.media_id, chunk_index, speaker)
    print(f"[done] {len(mapping)}개 청크 speaker_id 업데이트 완료")

    # 문서 레벨 메타데이터에도 집계된 화자 리스트를 저장 (SSoT = metadata).
    distinct_speakers = sorted({v for v in mapping.values()})
    update_media_metadata(args.media_id, {"speakers": distinct_speakers})
    print(f"[meta] media_files.metadata.speakers = {distinct_speakers}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
