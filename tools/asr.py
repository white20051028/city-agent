"""语音识别：把浏览器录的音频转成文字（腾讯云一句话识别）。

为什么不用浏览器自带的 Web Speech API：
  它底层调 Google 的语音服务，国内 Android 手机大多连不上
  → 用户点了麦克风没反应（实测在手机上完全不可用）

链路：
  浏览器 MediaRecorder 录 webm
    → 后端用 ffmpeg 转成 16k 单声道 wav
    → base64 后调腾讯云 SentenceRecognition
    → 返回文字

限制（腾讯云的）：
  · 音频 ≤ 60 秒
  · 单次 ≤ 3MB
"""

from __future__ import annotations

import base64
import io
import os
import subprocess
import tempfile
import wave
from pathlib import Path

from tencentcloud.asr.v20190614 import asr_client, models
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
    TencentCloudSDKException,
)

ROOT = Path(__file__).resolve().parent.parent
REGION = "ap-shanghai"
ENGSVC = "16k_zh"          # 中文通用，16k 采样率
MAX_SECONDS = 60
MAX_BYTES = 3 * 1024 * 1024


def _read_env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if v:
        return v
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError(f"缺少 {name}")


def _ffmpeg_exe() -> str | None:
    """找 ffmpeg：优先 imageio-ffmpeg 自带的（pip 装的，跨平台）。"""
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


def to_wav16k(audio: bytes, src_format: str = "webm") -> bytes:
    """把任意格式音频转成 16k 单声道 wav。

    腾讯云要求 wav 且采样率 16k；浏览器 MediaRecorder 给的是 webm。
    没有 ffmpeg 时直接返回原数据（腾讯云会报格式错，但至少不崩）。
    """
    exe = _ffmpeg_exe()
    if not exe:
        return audio

    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / f"in.{src_format}"
        dst = Path(td) / "out.wav"
        src.write_bytes(audio)

        r = subprocess.run(
            [exe, "-y", "-i", str(src), "-ar", "16000", "-ac", "1",
             "-f", "wav", str(dst)],
            capture_output=True,
            timeout=30,
        )
        if r.returncode != 0 or not dst.exists():
            return audio
        return dst.read_bytes()


def _wav_duration(data: bytes) -> float:
    """读 wav 时长（秒）。读不出返回 0。"""
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:  # noqa: BLE001
        return 0.0


def transcribe(audio: bytes, src_format: str = "webm") -> dict:
    """音频 → 文字。

    返回 {"ok": bool, "text": str, "duration": float, "error": str}
    """
    if not audio:
        return {"ok": False, "text": "", "duration": 0, "error": "音频为空"}
    if len(audio) > MAX_BYTES * 3:      # 转换前先粗筛
        return {"ok": False, "text": "", "duration": 0,
                "error": "音频太大（超过 3MB）"}

    wav = to_wav16k(audio, src_format)
    dur = _wav_duration(wav)
    if dur > MAX_SECONDS:
        return {"ok": False, "text": "", "duration": dur,
                "error": f"音频 {dur:.0f} 秒，超过腾讯云 60 秒限制"}

    try:
        cred = credential.Credential(_read_env("TENCENT_ASR_SECRET_ID"),
                                     _read_env("TENCENT_ASR_SECRET_KEY"))
        client = asr_client.AsrClient(cred, REGION)

        req = models.SentenceRecognitionRequest()
        req.EngSerViceType = ENGSVC
        req.SourceType = 1
        req.VoiceFormat = "wav"
        req.Data = base64.b64encode(wav).decode()
        req.DataLen = len(wav)
        req.FilterDirty = 0
        req.FilterModal = 0
        req.FilterPunc = 0

        resp = client.SentenceRecognition(req)
        return {
            "ok": True,
            "text": resp.Result or "",
            "duration": dur,
            "error": "",
        }
    except TencentCloudSDKException as e:
        return {"ok": False, "text": "", "duration": dur,
                "error": f"{e.get_code()}: {e.get_message()}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "text": "", "duration": dur,
                "error": f"{type(e).__name__}: {e}"}
