"""测 /api/asr 接口（用静音 wav 模拟）。"""

import io
import json
import urllib.request
import wave


def make_silence(seconds=1.5, rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


def main() -> None:
    wav = make_silence()
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/asr",
        data=wav,
        headers={"Content-Type": "audio/wav"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read().decode())
        print(f"ok={d.get('ok')} text={d.get('text')!r} "
              f"duration={d.get('duration')}s error={d.get('error')!r}")
    except Exception as e:
        print(f"请求失败: {type(e).__name__}: {e}")

    # 再测空 body
    req2 = urllib.request.Request(
        "http://127.0.0.1:8000/api/asr", data=b"",
        headers={"Content-Type": "audio/wav"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req2, timeout=60) as r:
            d = json.loads(r.read().decode())
        print(f"空 body: ok={d.get('ok')} error={d.get('error')!r}")
    except Exception as e:
        print(f"空 body 请求失败: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
