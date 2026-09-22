# -*- coding: utf-8 -*-
"""
MiniMax 声音克隆管线（国内站 platform.minimaxi.com）
流程图 03 工具链第 2 步：授权录音 → 快速复刻音色 → speech-2.8-hd 口播配音

用法（三步分离，花钱步骤全部带 --yes 闸门）：
  1) 免费连通性检查：  python 工具_MiniMax声音克隆_通用.py --check
  2) 克隆音色（约9.9元，首次合成时计费）：
       python 工具_MiniMax声音克隆_通用.py --clone --audio "句末收尾_69秒.m4a" --voice-id haifeng_v1 --yes
  3) TTS 试音：        python 工具_MiniMax声音克隆_通用.py --tts "你好，这是一段试音。" --voice-id haifeng_v1

密钥放置（二选一，不打印明文）：
  .secrets/minimax.key          -> 只放 API Key 一行
  .secrets/minimax_group.txt    -> 只放 GroupId 一行（控制台「账户管理」里可见）
"""
import argparse
import json
import sys
from pathlib import Path

import requests

BASE = "https://api.minimaxi.com"
WS = Path(__file__).resolve().parents[1]  # 仓库根（.secrets/ 放这里）
KEY_FILE = WS / ".secrets" / "minimax.key"
GROUP_FILE = WS / ".secrets" / "minimax_group.txt"
DEFAULT_AUDIO = WS / "voice_sample_69s.m4a"   # 30-90s、句末完整收尾的授权录音
TTS_MODEL = "speech-2.8-hd"          # HD 3.5 元/万字符；Turbo 2 元/万字符
HD_PRICE = 3.5 / 10000               # 元/字符


def load_key() -> str:
    if not KEY_FILE.exists():
        sys.exit(f"[缺密钥] 请把 MiniMax 开放平台 API Key 放入：{KEY_FILE}（仅一行）")
    key = KEY_FILE.read_text(encoding="utf-8").strip()
    if len(key) < 16:
        sys.exit("[密钥异常] minimax.key 内容过短，请核对")
    return key


def load_group(key: str, s: requests.Session) -> str:
    if GROUP_FILE.exists():
        return GROUP_FILE.read_text(encoding="utf-8").strip()
    sys.exit("[缺 GroupId] 请到控制台-账户管理复制 GroupId 存入：" + str(GROUP_FILE))


def ok(j: dict) -> bool:
    return isinstance(j, dict) and j.get("base_resp", {}).get("status_code") == 0


def show_err(j: dict):
    br = (j or {}).get("base_resp", {})
    print(f"  base_resp.status_code={br.get('status_code')} status_msg={br.get('status_msg')}")


def step_check():
    key = load_key()
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    gid = load_group(key, s)
    r = s.post(f"{BASE}/v1/get_voice", params={"GroupId": gid},
               json={"voice_type": "all"}, timeout=20)
    try:
        j = r.json()
    except ValueError:
        sys.exit(f"[FAIL] 非 JSON 响应 HTTP {r.status_code}: {r.text[:200]}")
    if ok(j):
        d = j.get("data", {})
        clones = d.get("voice_cloning") or []
        print(f"[OK] Key 有效，GroupId={gid}，已有克隆音色 {len(clones)} 个")
        for v in clones[:10]:
            print("   -", v.get("voice_id"), v.get("voice_name", ""))
    else:
        print("[FAIL] 鉴权或请求失败：")
        show_err(j)


def step_clone(audio: Path, voice_id: str):
    key = load_key()
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {key}"})
    gid = load_group(key, s)
    if not audio.exists():
        sys.exit(f"[缺素材] 授权录音不存在：{audio}")
    size_mb = audio.stat().st_size / 1048576
    print(f"[1/2] 上传授权录音 {audio.name}（{size_mb:.2f} MB）purpose=voice_clone ...")
    with open(audio, "rb") as f:
        r = s.post(f"{BASE}/v1/files/upload",
                   params={"GroupId": gid},
                   data={"purpose": "voice_clone"},
                   files={"file": (audio.name, f)},
                   timeout=120)
    j = r.json()
    if not ok(j):
        print("[FAIL] 上传失败："); show_err(j); sys.exit(1)
    file_id = j.get("file", {}).get("file_id")
    print(f"      file_id = {file_id}")
    print(f"[2/2] 提交克隆 voice_id={voice_id} （快速复刻 9.9 元/音色，首次合成时计费）...")
    r = s.post(f"{BASE}/v1/voice_clone",
               params={"GroupId": gid},
               json={"file_id": file_id, "voice_id": voice_id},
               timeout=60)
    j = r.json()
    if not ok(j):
        print("[FAIL] 克隆提交失败："); show_err(j); sys.exit(1)
    print(f"[DONE] 音色已登记：{voice_id}\n       下一步试音：python {Path(sys.argv[0]).name} "
          f"--tts \"试音文本\" --voice-id {voice_id}")


def step_tts(text: str, voice_id: str, out: Path):
    key = load_key()
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {key}"})
    gid = load_group(key, s)
    est = len(text) * HD_PRICE
    print(f"[TTS] {TTS_MODEL}  {len(text)} 字符  预计 ≈{est:.4f} 元")
    payload = {
        "model": TTS_MODEL,
        "text": text,
        "stream": False,
        "voice_setting": {"voice_id": voice_id, "speed": 1.0, "vol": 1.0, "pitch": 0},
        "audio_setting": {"sample_rate": 32000, "bitrate": 128000,
                          "format": "mp3", "channel": 1},
        "aigc_watermark": True,
    }
    r = s.post(f"{BASE}/v1/t2a_v2", params={"GroupId": gid}, json=payload, timeout=120)
    j = r.json()
    if not ok(j):
        print("[FAIL] TTS 失败："); show_err(j); sys.exit(1)
    audio_hex = j.get("data", {}).get("audio", "")
    out.write_bytes(bytes.fromhex(audio_hex))
    extra = j.get("data", {}).get("extra_info", {}) or {}
    print(f"[DONE] {out}  {out.stat().st_size/1024:.0f} KB"
          + (f"  实耗字符={extra.get('audio_length') and len(text)}" if extra else ""))
    if j["data"].get("subtitle_file"):
        print("       附带句级字幕时间戳已返回（subtitle_file）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="免费连通性检查")
    ap.add_argument("--clone", action="store_true", help="上传授权录音并克隆音色（花钱）")
    ap.add_argument("--tts", metavar="TEXT", help="用克隆音色合成试音（花钱，按字符计费）")
    ap.add_argument("--audio", default=str(DEFAULT_AUDIO), help="授权录音路径")
    ap.add_argument("--voice-id", default="haifengv1",
                    help="自定义音色 ID（≥8 位，仅字母数字，字母开头，不能有下划线）")
    ap.add_argument("--out", default=None, help="TTS 输出路径")
    ap.add_argument("--yes", action="store_true", help="确认执行付费操作（不带则只打印计划）")
    a = ap.parse_args()

    if a.check:
        step_check()
        return
    if a.clone:
        print(f"[计划] 克隆音色：{a.voice_id}  素材：{a.audio}")
        if not a.yes:
            print("[闸门] 加 --yes 执行（克隆本身不扣费，首次用该音色合成时收 9.9 元/音色）")
            return
        step_clone(Path(a.audio), a.voice_id)
        return
    if a.tts:
        out = Path(a.out) if a.out else WS / f"音频_MiniMax克隆试音_{a.voice_id}.mp3"
        print(f"[计划] TTS {len(a.tts)} 字符 ≈{len(a.tts)*HD_PRICE:.4f} 元 → {out.name}")
        if not a.yes:
            print("[闸门] 加 --yes 执行")
            return
        step_tts(a.tts, a.voice_id, out)
        return
    ap.print_help()


if __name__ == "__main__":
    main()
