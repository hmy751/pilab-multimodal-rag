from typing import List, Dict
import ffmpeg

from faster_whisper import WhisperModel
from langsmith import traceable

from ..config import TranscriptionCfg, get_stage_config
from ..prompts import get_transcription_prompt


# Whisper는 mono 16kHz 내부 처리라 이 스펙에서 품질 손실이 거의 없고,
# 48kbps mp3면 1시간 영상이 약 23MB로 OpenAI 25MiB 리밋 안에 들어온다.
_AUDIO_SAMPLE_RATE = 16000
_AUDIO_CHANNELS = 1
_AUDIO_CODEC = "libmp3lame"
_AUDIO_BITRATE = "48k"


@traceable(name="ingest.1_audio_extract", run_type="tool")
def extract_audio_from_video(video_path: str, output_path: str) -> str:
    (
        ffmpeg.input(video_path)
        .output(
            output_path,
            ar=_AUDIO_SAMPLE_RATE,
            ac=_AUDIO_CHANNELS,
            acodec=_AUDIO_CODEC,
            audio_bitrate=_AUDIO_BITRATE,
        )
        .run(overwrite_output=True)
    )
    return output_path


@traceable(name="ingest.2_transcribe", run_type="tool")
def transcribe_audio(
    audio_path: str, cfg: TranscriptionCfg | None = None
) -> List[Dict]:
    cfg = cfg or get_stage_config().transcription
    initial_prompt = get_transcription_prompt(cfg.whisper_prompt_version)

    if cfg.provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=cfg.openai_api_key)
        with open(audio_path, "rb") as f:
            kwargs = dict(
                model=cfg.openai_whisper_model,
                file=f,
                response_format="verbose_json",
            )
            if initial_prompt:
                kwargs["prompt"] = initial_prompt
            resp = client.audio.transcriptions.create(**kwargs)
        return [
            {"start": seg.start, "end": seg.end, "text": seg.text}
            for seg in resp.segments
        ]
    else:
        model = WhisperModel(
            cfg.whisper_model_size, device="cpu", compute_type="int8"
        )
        transcribe_kwargs: dict = {"beam_size": 5}
        if initial_prompt:
            transcribe_kwargs["initial_prompt"] = initial_prompt
        segments, _ = model.transcribe(audio_path, **transcribe_kwargs)
        return [
            {"start": seg.start, "end": seg.end, "text": seg.text} for seg in segments
        ]
