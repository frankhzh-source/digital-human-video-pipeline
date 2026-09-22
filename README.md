# digital-human-video-pipeline

> **WorkBuddy Skill**：数字人知识口播视频端到端全自动制作管线。
> 口播音频进 → 带字幕 / 关键词卡动效 / 可视化图表 / BGM / 音效的成片出，全程可复现、可批量。
>
> 实测验证：74.8s 口播 → 15.6s 成片（HeyGen A7 形象 + MiniMax 声音克隆 + HyperFrames 包装），2026-09 全链跑通。

## 管线总览

```
[1] 母版音频（-16 LUFS、句末完整）
      ↓
[2] ASR 转写 + 切段表（faster-whisper 词级时间戳）
      ↓
[3] MiniMax 声音克隆 + 配音（speech-2.8-hd, speed 0.95，约 0.02 元/句）
      ↓
[4] HeyGen photo avatar + lipsync（~0.85 积分/秒，实测 13 积分 / 15.7s）
      ↓
[5] HyperFrames 透明叠加层（GSAP 时间线 → ProRes 4444 alpha，~5 分钟机时）
      ↓
[6] ffmpeg 合成（ASS 字幕 + 音效三件套 + BGM 床/人声闪避 + punch-in + -14 LUFS）
      → 成片 + 封面
```

## 目录结构

```
├── SKILL.md                                      # Skill 主文件：六步流程、参数、成本、验收清单
├── references/
│   └── knowledge-video-bgm-sfx-paradigm.md       # BGM/音效范式归纳（知识类视频为何用「信息陪伴型」）
├── scripts/
│   ├── minimax_voice_clone.py                    # MiniMax 克隆+TTS（--check/--clone/--tts，付费步骤带 --yes 闸门）
│   └── synthesize_packaged_video.py              # ffmpeg 最终合成（每期复制一份，只改顶部常量）
└── compositions/
    └── v2_testcard.html                          # HyperFrames 合成页模板（换文案只动文字+时间戳）
```

## 快速开始

1. **依赖**：Node ≥22 + `hyperframes`（npm）、ffmpeg + ffprobe（都在 PATH）、Python + `faster-whisper`/`numpy`/`requests`、HeyGen 账号（海外服务需代理）、MiniMax 开放平台 Key；
2. **密钥**：`<repo根>/.secrets/minimax.key`（API Key 一行）+ `.secrets/minimax_group.txt`（GroupId 一行），脚本运行时读取、零硬编码；
3. **克隆音色**（一次性）：
   ```bash
   python scripts/minimax_voice_clone.py --check
   python scripts/minimax_voice_clone.py --clone --audio voice_sample_69s.m4a --voice-id yourvoice1 --yes
   python scripts/minimax_voice_clone.py --tts "试音文本" --voice-id yourvoice1 --yes
   ```
4. **出片**：按 `SKILL.md` 六步走，第 [5] 步渲染：
   ```bash
   cd compositions && npx hyperframes render -c v2_testcard.html -f 25 --format mov -o ../overlay.mov
   ```
5. **合成**：复制 `scripts/synthesize_packaged_video.py`，改顶部 `SRC / OV / OUT / 字幕 / 音效点位` 常量，运行即出片 + 封面。

## 精华：知识类视频 BGM 范式

知识口播 ≠ 情绪渲染。**BGM 是教室里的灯光，不是舞台上的配乐**（范式 B「信息陪伴型」）：

1. 无旋律（pluck 拨弦，不"唱歌"）　2. C4+ 中高音区（**低音区长音 legato = 氛围片 drone = 压抑感**）　3. 跳音留白　4. BPM 88–104 贴语速　5. 频段避让人声 300Hz–3.4kHz；量级 -28~-32 LUFS + sidechain 人声闪避。
详见 `references/knowledge-video-bgm-sfx-paradigm.md`（含 v2.2「压抑版」翻车复盘与音效三铁律）。

## 踩坑清单（全部实测踩平）

- HyperFrames 根元素必须 `data-composition-id`，画幅必须 `data-width/data-height`（`data-composition-width` 不被读取 → 输出竖屏）；
- 渲染机 PATH 需 ffmpeg **和** ffprobe（缺 ffprobe：`npm i ffprobe-static --registry=https://registry.npmmirror.com` 一分钟解决；勿从 gyan.dev 下 114MB 包，国内 ~20KB/s 且断流）；
- ffmpeg `ass=` 滤镜路径必须正斜杠相对路径（反斜杠会被转义吞掉）；
- 渲染出的透明层（ProRes 4444）**保留至定版再删**——删一次重渲 5 分钟。

## 成本参考（2026-09 实测）

| 项 | 成本 |
|---|---|
| ASR / ffmpeg / HyperFrames / 合成 BGM | 0 |
| MiniMax 克隆 | 9.9 元/音色（首次合成时计费）；TTS HD ≈0.02 元/句 |
| HeyGen lipsync | 13 积分 / 15.7s（全长片提交前建议先拿 30s 片核价） |

## License

MIT
