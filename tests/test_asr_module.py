"""测试 ASR 模块：生成一段 TTS 音频太麻烦，直接测 wav 转换 + 静音识别。"""

import sys

sys.path.insert(0, r"D:\桌面\city-agent")

from tools import asr

# ① 测 wav 转换（用静音 wav 当「已经是 wav」的输入）
import io
import wave


def make_silence(seconds=1.5, rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


wav = make_silence()
print(f"① 输入 wav: {len(wav)} 字节")

# ② 测识别
r = asr.transcribe(wav, src_format="wav")
print(f"② 识别结果: ok={r['ok']} text={r['text']!r} "
      f"duration={r['duration']:.1f}s error={r['error']!r}")

# ③ 测空音频
r2 = asr.transcribe(b"")
print(f"③ 空音频: ok={r2['ok']} error={r2['error']!r}")
