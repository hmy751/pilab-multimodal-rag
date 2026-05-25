import json
import os
import subprocess
import time
import base64
import requests
from typing import List, Dict

from langsmith import traceable

from ..config import VisionCfg, get_stage_config
from ..prompts import get_vision_prompt


def _get_video_duration(video_path: str) -> float:
    """ffprobe로 비디오 재생 시간(초)을 가져옵니다."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            video_path,
        ],
        capture_output=True,
        text=True,
    )
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


@traceable(name="ingest.3_extract_frames", run_type="tool")
def extract_key_frames(
    video_path: str, output_dir: str, frames_per_minute: int = 1, min_frames: int = 3
) -> List[Dict]:
    result = []

    duration = _get_video_duration(video_path)
    print(f"[vision] Video duration: {duration:.1f}s")

    interval_sec = 60 / frames_per_minute
    # 영상이 짧아 min_frames보다 적게 추출될 경우 간격을 줄여 최소 프레임 수를 보장한다.
    if duration > 0 and duration / interval_sec < min_frames:
        interval_sec = duration / min_frames
        print(
            f"[vision] interval adjusted to {interval_sec:.1f}s "
            f"(min_frames={min_frames}, duration={duration:.1f}s)"
        )
    timestamp = 0.0

    while timestamp < duration:
        frame_path = os.path.join(output_dir, f"frame_{timestamp:.1f}.jpg")
        proc = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(timestamp),
                "-i",
                video_path,
                "-frames:v",
                "1",
                "-q:v",
                "2",
                frame_path,
            ],
            capture_output=True,
        )
        if proc.returncode == 0 and os.path.exists(frame_path):
            result.append({"timestamp": timestamp, "frame_path": frame_path})
        else:
            print(f"[vision] WARNING: Failed to extract frame at {timestamp:.1f}s")

        timestamp += interval_sec

    print(f"[vision] Extracted {len(result)} key frames")

    return result


@traceable(name="ingest.4_analyze_frame", run_type="llm")
def analyze_frame_with_vision_model(
    frame_path: str, timestamp: float, cfg: VisionCfg | None = None
) -> str:
    cfg = cfg or get_stage_config().vision
    with open(frame_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    prompt = get_vision_prompt(timestamp)

    if cfg.provider == "openai":
        from openai import OpenAI, RateLimitError

        client = OpenAI(api_key=cfg.openai_api_key)
        for attempt in range(5):
            try:
                resp = client.chat.completions.create(
                    model=cfg.openai_vision_model,
                    temperature=0,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_b64}",
                                    },
                                },
                            ],
                        }
                    ],
                )
                return resp.choices[0].message.content
            except RateLimitError:
                wait = min(2**attempt * 5, 60)
                print(
                    f"[vision] Rate limit hit, retrying in {wait}s... ({attempt + 1}/5)"
                )
                time.sleep(wait)
        raise RuntimeError("OpenAI vision rate limit: 5회 재시도 후에도 실패")
    else:
        response = requests.post(
            f"{cfg.ollama_base}/api/generate",
            json={
                "model": cfg.ollama_vision_model,
                "prompt": prompt,
                "images": [image_b64],
                "stream": False,
            },
        )
        return response.json()["response"]
