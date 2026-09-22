# -*- coding: utf-8 -*-
"""测试片 A7 包装 v2.2 合成器（音频丝滑版）
相对 v2.1 的音频改动：
  1) 音效软化：whoosh 更长 attack + 低通；tick 减冲；thump 减力——去掉"硬碰硬"的颗粒感
  2) 新增超低音量 BGM 床：numpy 合成暖色钢琴垫（C-G-Am-F 环进），首尾淡入淡出
  3) BGM 人声闪避（sidechaincompress）：开口时 BGM 自动压低，停顿处浮回来——人声永远在最前
  4) 全链 loudnorm -14 LUFS 不变
输入：成片(口播+数字人) + HyperFrames 透明叠加层(ProRes4444)
输出：成片_测试片A7_包装v2_2026-09-22.mp4 + 封面帧
"""
import math
import os
import struct
import subprocess
import sys
import wave

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
FF = r"D:\ffmpeg\ffmpeg.exe"
SRC = os.path.join(ROOT, "成片_播客测试片_A7_12s_2026-09-21.mp4")
OV = os.path.join(ROOT, "_v2", "overlay_v2.mov")
OUT = os.path.join(ROOT, "成片_测试片A7_包装v2_2026-09-22.mp4")
COVER = os.path.join(ROOT, "封面_测试片A7_包装v2_2026-09-22.jpg")
DUR = 15.62
SR = 48000

# ---------------- 1) 合成音效（软化版） ----------------
def env(t, a, r):
    """attack/release 包络（cosine 平滑，避免拐点）"""
    if t < a:
        return 0.5 - 0.5 * math.cos(math.pi * t / a)
    return max(0.0, 0.5 + 0.5 * math.cos(math.pi * min(1.0, (t - a) / r)))

def whoosh(path, dur=0.8, f0=300, f1=2400, amp=0.38):
    n = int(SR * dur)
    import random
    random.seed(7)
    phase = 0.0
    frames = bytearray()
    for i in range(n):
        t = i / SR
        f = f0 + (f1 - f0) * (t / dur) ** 1.5
        phase += 2 * math.pi * f / SR
        noise = (random.random() * 2 - 1)
        v = (0.6 * noise * math.sin(phase) + 0.4 * noise) * env(t, 0.42, dur - 0.42) * amp
        frames += struct.pack("<h", int(max(-1, min(1, v)) * 32767))
    w = wave.open(path, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(bytes(frames)); w.close()

def tick(path, f=1250, dur=0.12, amp=0.30):
    n = int(SR * dur)
    frames = bytearray()
    for i in range(n):
        t = i / SR
        v = math.sin(2 * math.pi * f * t) * math.exp(-t * 34) * amp  # 34←55：衰减更绵
        frames += struct.pack("<h", int(v * 32767))
    w = wave.open(path, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(bytes(frames)); w.close()

def thump(path, f=90, dur=0.7, amp=0.55):
    n = int(SR * dur)
    frames = bytearray()
    for i in range(n):
        t = i / SR
        v = math.sin(2 * math.pi * (f * (1 - 0.4 * t / dur)) * t) * math.exp(-t * 6.5) * amp
        v += 0.10 * math.sin(2 * math.pi * 180 * t) * math.exp(-t * 14)
        frames += struct.pack("<h", int(max(-1, min(1, v)) * 32767))
    w = wave.open(path, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(bytes(frames)); w.close()

SFX = os.path.join(ROOT, "_v2", "sfx")
os.makedirs(SFX, exist_ok=True)
whoosh(os.path.join(SFX, "whoosh.wav"))          # 0.05s 片头
whoosh(os.path.join(SFX, "whoosh2.wav"), dur=0.7, f0=500, f1=2800)  # 4.5s 图表滑入
tick(os.path.join(SFX, "tick1.wav"))
tick(os.path.join(SFX, "tick2.wav"), f=1400)
tick(os.path.join(SFX, "tick3.wav"), f=1550)
thump(os.path.join(SFX, "thump.wav"))            # 13.25s 结论

# ---------------- 1.5) BGM 床 ----------------
# v2.2 判「压抑」→ 范式归纳见《整理_知识类视频BGM与音效范式_2026-09-22.md》。
# 知识口播 = 范式 B「信息陪伴型」：无旋律、中高音区、pluck 跳音、BPM 贴语速。
# v3 默认 = pluck 拨弦版；v2.2 pad 长音版保留做 A/B（BGM_STYLE 可切）。
BGM_STYLE = "pluck"

def make_bgm_pluck(path, dur):
    """范式 B：马林巴/拨弦琶音 + 轻长音垫。C4 起步、BPM92、大调明亮 voicing。"""
    n = int(SR * dur)
    t = np.arange(n) / SR
    out = np.zeros(n)
    bpm = 92.0
    beat = 60.0 / bpm                      # 0.652s
    bar = 4 * beat                         # 每和弦一小节
    # C add9 / G / Am7 / Fmaj7——音区 C4–C5，大调为主
    chords = [
        (261.63, 392.00, 523.25, 587.33),  # C4 G4 C5 D5(add9)
        (196.00, 293.66, 392.00, 493.88),  # G3 D4 G4 B4
        (220.00, 329.63, 392.00, 523.25),  # A3 E4 G4 C5(Am7)
        (349.23, 440.00, 523.25, 659.26),  # F4 A4 C5 E5(Fmaj7)
    ]
    # 琶音模式：每拍一个音（根-五-三高-九），第 4 拍后半休止 = 留白
    seq = [(0.0, 0), (1.0, 1), (2.0, 2), (3.0, 3), (3.5, None)]

    def pluck(freq, t0, amp):
        i0 = int(t0 * SR)
        pd = 0.55                                   # 拨弦余响
        m = min(int(pd * SR), n - i0)
        if m <= 0:
            return
        tt = np.arange(m) / SR
        envp = np.exp(-tt * 8.0) * (1 - np.exp(-tt * 2000))  # 2ms 起音 + 指数衰减
        out[i0:i0 + m] += amp * envp * (
            np.sin(2 * np.pi * freq * tt)
            + 0.35 * np.sin(2 * np.pi * 2 * freq * tt)
            + 0.12 * np.sin(2 * np.pi * 3 * freq * tt)
        )

    def pad(freq, t0, d, amp):
        i0 = int(t0 * SR)
        m = min(int(d * SR), n - i0)
        if m <= 0:
            return
        tt = np.arange(m) / SR
        e = np.minimum(tt / 0.3, 1.0) * np.minimum((d - tt) / 0.4, 1.0)
        out[i0:i0 + m] += amp * e * np.sin(2 * np.pi * freq * tt)

    k, start = 0, 0.0
    while start < dur:
        c = chords[k % 4]
        pad(c[0] / 2, start, min(bar + 0.4, dur - start), 0.05)   # 低八度轻垫，只补连续性
        for off, idx in seq:
            t0 = start + off * beat
            if t0 >= dur:
                break
            if idx is not None:
                pluck(c[idx], t0, 0.5)
                pluck(c[idx] * 1.001, t0, 0.18)                    # 轻失谐加宽
        k += 1
        start += bar
    out *= 0.30
    fi, fo = int(1.2 * SR), int(2.0 * SR)
    out[:fi] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(fi) / fi)
    out[-fo:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(fo) / fo)
    peak = np.abs(out).max()
    out = out / peak * 0.5
    w = wave.open(path, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((out * 32767).astype("<i2").tobytes()); w.close()

def make_bgm_pad(path, dur):
    """v2.2 pad 长音版（范式 A 暗色调）——被判压抑，仅作 A/B 对照保留。"""
    n = int(SR * dur)
    t = np.arange(n) / SR
    out = np.zeros(n)
    chords = [
        (130.81, 164.81, 196.00, 261.63),
        (98.00, 123.47, 146.83, 246.94),
        (110.00, 130.81, 164.81, 220.00),
        (87.31, 110.00, 130.81, 174.61),
    ]
    chord_len, rel = 2.0, 0.9
    k = 0
    start = 0.0
    while start < dur:
        c = chords[k % 4]
        i0 = int(start * SR)
        i1 = min(int((start + chord_len + rel) * SR), n)
        seg = t[i0:i1] - start
        e = np.ones(i1 - i0)
        a_n = int(0.45 * SR)
        e[:a_n] = 0.5 - 0.5 * np.cos(np.pi * seg[:a_n] / 0.45)
        r0 = chord_len
        r_mask = seg > r0
        e[r_mask] = np.maximum(0.0, 0.5 + 0.5 * np.cos(np.pi * (seg[r_mask] - r0) / rel))
        for j, f in enumerate(c):
            det = 1.0 + (0.0011 if j % 2 else -0.0011)
            wgt = 1.0 if j < 3 else 0.28
            out[i0:i1] += wgt * e * (
                0.50 * np.sin(2 * np.pi * f * seg)
                + 0.16 * np.sin(2 * np.pi * 2 * f * seg)
                + 0.06 * np.sin(2 * np.pi * 3 * f * seg)
                + 0.50 * np.sin(2 * np.pi * f * det * seg)
            )
        k += 1
        start += chord_len
    out *= 0.20
    fi, fo = int(1.2 * SR), int(2.0 * SR)
    out[:fi] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(fi) / fi)
    out[-fo:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(fo) / fo)
    peak = np.abs(out).max()
    out = out / peak * 0.5
    w = wave.open(path, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((out * 32767).astype("<i2").tobytes()); w.close()

BGM = os.path.join(SFX, f"bgm_{BGM_STYLE}.wav")
if BGM_STYLE == "pluck":
    make_bgm_pluck(BGM, DUR)
else:
    make_bgm_pad(BGM, DUR)
print("bgm ok:", BGM_STYLE)

# ---------------- 2) ASS 字幕（词级时间轴 + 金色高亮） ----------------
ASS = r"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1072

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Microsoft YaHei,56,&H00FFFFFF,&H00FFFFFF,&H00181008,&H96000000,1,0,0,0,100,100,2,0,1,4,2,2,80,80,52,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.05,0:00:03.96,Sub,,0,0,0,,我做的工作，是帮企业{\c&H6ABEE9&}想清楚一件事{\r}。
Dialogue: 0,0:00:04.40,0:00:08.40,Sub,,0,0,0,,当越来越多的人开始用{\c&H6ABEE9&}AI{\r}问问题的时候
Dialogue: 0,0:00:08.40,0:00:10.06,Sub,,0,0,0,,{\c&H6ABEE9&}你的产品{\r}
Dialogue: 0,0:00:10.06,0:00:11.30,Sub,,0,0,0,,{\c&H6ABEE9&}你的服务{\r}
Dialogue: 0,0:00:11.86,0:00:13.14,Sub,,0,0,0,,{\c&H6ABEE9&}你的名字{\r}
Dialogue: 0,0:00:13.14,0:00:15.45,Sub,,0,0,0,,会不会出现在那个{\c&H6ABEE9&}答案{\r}里
"""
ass_path = os.path.join(ROOT, "_v2", "subs_v2.ass")
with open(ass_path, "w", encoding="utf-8-sig") as f:
    f.write(ASS)

# ---------------- 3) ffmpeg 合成 ----------------
# punch-in：8.45s 与 13.25s 各推近 5%，0.25s 推进 / 1.2s 后 0.5s 拉回
def bump(ts):
    x = f"(in/25-{ts})"
    rise = f"min(max({x}/0.25,0),1)"
    fall = f"min(max(({x}-1.2)/0.5,0),1)"
    return f"({rise}*(1-{fall}))"

ZOOM = ("1+0.05*(" + bump(8.45) + "+" + bump(13.25) + ")")
PANX = "iw/2-(iw/zoom)/2"
PANY = "ih/2-(ih/zoom)/2"

# 音效量：整体比 v2.1 低一档（0.32 → 0.22 基准），whoosh 再降并低通
sfx_vol = 0.22
fc = (
    # 视频：punch-in → 叠加透明层 → 字幕
    f"[0:v]zoompan=z='{ZOOM}':x='{PANX}':y='{PANY}':d=1:s=1920x1072:fps=25,format=yuv420p[base];"
    f"[1:v]scale=1920:1072,format=yuva444p10le[ov];"
    f"[base][ov]overlay=0:0:format=auto[vsub];"
    f"[vsub]ass={os.path.relpath(ass_path, ROOT).replace(os.sep, '/')}[vout];"
    # 音频：人声 → BGM 闪避 → 与软化音效混音 → 响度归一
    f"[0:a]aresample={SR},pan=stereo|c0=c0|c1=c0[va];"
    # BGM：淡入淡出 → 人声侧链闪避 → 固定极低音量
    f"[8:a]afade=t=in:st=0:d=1.2:curve=tri,afade=t=out:st={DUR - 2.0:.2f}:d=2.0:curve=tri[bgm0];"
    f"[bgm0][va]sidechaincompress=threshold=0.028:ratio=7:attack=180:release=1000[bgmd];"
    f"[bgmd]volume=0.16[bgmv];"
    # 音效：whoosh 低通去毛刺，全部降量
    f"[2:a]adelay=50:all=1,volume={sfx_vol},lowpass=f=2000[s1];"
    f"[3:a]adelay=4500:all=1,volume={sfx_vol * 0.8},lowpass=f=2400[s2];"
    f"[4:a]adelay=8500:all=1,volume={sfx_vol * 0.75}[s3];"
    f"[5:a]adelay=10120:all=1,volume={sfx_vol * 0.75}[s4];"
    f"[6:a]adelay=11920:all=1,volume={sfx_vol * 0.75}[s5];"
    f"[7:a]adelay=13250:all=1,volume={sfx_vol * 1.1}[s6];"
    f"[va][bgmv][s1][s2][s3][s4][s5][s6]amix=inputs=8:duration=first:normalize=0,"
    f"loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
)

cmd = [
    FF, "-y",
    "-i", SRC, "-i", OV,
    "-i", os.path.join(SFX, "whoosh.wav"),
    "-i", os.path.join(SFX, "whoosh2.wav"),
    "-i", os.path.join(SFX, "tick1.wav"),
    "-i", os.path.join(SFX, "tick2.wav"),
    "-i", os.path.join(SFX, "tick3.wav"),
    "-i", os.path.join(SFX, "thump.wav"),
    "-i", BGM,
    # 音效点位：0.05 / 4.50 / 8.50 / 10.12 / 11.92 / 13.25（adelay 已对位）
    "-filter_complex", fc,
    "-map", "[vout]", "-map", "[aout]",
    "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "192k",
    "-t", str(DUR), "-movflags", "+faststart",
    OUT,
]
print(">>", " ".join(cmd[:8]), "...")
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(r.stderr[-3000:]); sys.exit(1)
print("成片 OK:", OUT)

# 封面帧（13.8s：结论卡+关键词卡同框）
r = subprocess.run([FF, "-y", "-ss", "13.8", "-i", OUT, "-frames:v", "1", "-q:v", "2", COVER],
                   capture_output=True, text=True)
print("封面 OK" if r.returncode == 0 else r.stderr[-800:])
