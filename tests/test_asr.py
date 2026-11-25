"""测腾讯云 ASR：先用一段静音 wav 验证 API 能通。

**密钥从 .env 读，不硬编码**（曾经硬编码导致被 GitHub push protection 拦截，
而且 Gitee 已经推上去泄露过一次）。
"""

import base64
import io
import sys
import wave
from pathlib import Path

from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
    TencentCloudSDKException,
)
from tencentcloud.asr.v20190614 import asr_client, models

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import asr  # noqa: E402 复用它的 _read_env

REGION = "ap-shanghai"


def make_silence_wav(seconds: float = 1.0, rate: int = 16000) -> bytes:
    """生成一段静音 wav（16k 单声道 16bit）。"""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


def main() -> None:
    secret_id = asr._read_env("TENCENT_ASR_SECRET_ID")
    secret_key = asr._read_env("TENCENT_ASR_SECRET_KEY")

    cred = credential.Credential(secret_id, secret_key)
    client = asr_client.AsrClient(cred, REGION)

    data = make_silence_wav()
    req = models.SentenceRecognitionRequest()
    req.EngSerViceType = "16k_zh"
    req.SourceType = 1
    req.VoiceFormat = "wav"
    req.Data = base64.b64encode(data).decode()
    req.DataLen = len(data)
    req.FilterDirty = 0
    req.FilterModal = 0
    req.FilterPunc = 0

    try:
        resp = client.SentenceRecognition(req)
        print("✅ API 调用成功")
        print(f"   RequestId: {resp.RequestId}")
        print(f"   Result:    {resp.Result!r}（静音，空是正常的）")
        print(f"   AudioDuration: {resp.AudioDuration} ms")
    except TencentCloudSDKException as e:
        print("❌ 调用失败")
        print(f"   code: {e.get_code()}")
        print(f"   message: {e.get_message()}")


if __name__ == "__main__":
    main()
