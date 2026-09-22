---
name: digital-human-video-pipeline
description: >
  数字人知识口播视频端到端制作管线（播客/口播音频 → 包装成片）。
  当用户要「把播客做成视频」「出数字人口播视频」「给口播加包装（字幕/关键词卡/图表/BGM/音效）」
  「HyperFrames 渲染卡片动效」「MiniMax 声音克隆配音」「HeyGen 数字人」时使用。
  覆盖：六步全流程（ASR 定轴 → 切段 → MiniMax 克隆/TTS → HeyGen lipsync →
  HyperFrames 透明叠加层 → ffmpeg 合成交付）、BGM/音效范式、积分成本、踩坑清单。
---

# 数字人视频制作管线（本机已全链验证 ✅）

> 2026-09-21/22 实测打通：74.8s 口播 → 15.6s 测试片（A7 形象 + MiniMax 克隆配音 + HyperFrames 包装）全流程 0 失败。
> 所有脚本在 `D:\workbuddy\Claw\Claw`，用 `D:/Anaconda3/envs/ai/python.exe -X utf8` 运行（faster_whisper 在这个环境）。

## 流程总览（六步）

```
[1] 母版音频 → [2] ASR转写+切段表 → [3] MiniMax克隆配音(B2配方)
    → [4] HeyGen photo avatar + lipsync → [5] HyperFrames 透明叠加层(ProRes4444)
    → [6] ffmpeg 合成(字幕/音效/BGM/响度) → 成片 + 封面
```

## [1] 母版要求
- 句末完整收尾（勿用截断版）；响度 -16 LUFS 口径；30–90s 干净录音可兼做克隆注册素材。
- 注册克隆用 `音频_口播原声_092211_句末收尾_69秒.m4a`（勿用 74.8s 半句版）。

## [2] ASR 转写 + 切段表
```bash
D:/Anaconda3/envs/ai/python.exe -X utf8 工具_播客ASR转写.py <音频> --md 转写_xxx.md
```
- 输出词级时间戳（`.asr_cache/*.json` 有缓存，重跑秒回）；依据转写切 5 段左右，标记 S1–S5 与信息点；
- **测试段选 18–30s**：含中英混读、停顿的段落最有代表性。

## [3] MiniMax 声音克隆 + 配音
工具：`工具_MiniMax声音克隆_通用.py`（密钥 `.secrets/minimax.key` + `minimax_group.txt`，国内站直连不需代理）。
- `--check` 免费 → `--clone --yes` 克隆（voice_id 规则：≥8位字母数字、字母开头，用 `haifengv1`）→ `--t2a` 配音；
- **配音配方定版「B2」：`speech-2.8-hd` + `speed:0.95`，不加情绪标签**（用户验收：音色可以，B2 语气可接受）；
- 语气僵的调法优先级：改文案口语化 > speed 0.95 > emotion=happy > 更长素材重克隆；
- 成本参考：HD 3.5 元/万字符，一句话 <1 分钱。

## [4] HeyGen 数字人
前置：**代理必须开**（`127.0.0.1:7890` 监听检查 + `mcp.heygen.com` 连通测试）。
- 工具：`工具_播客测试片A7_准备_2026-09-21.py`（免费：额度/schema/形象核对/传音频）→ `工具_播客测试片A7_提交_2026-09-21.py`（`--yes` 闸门）；
- 形象 A7 + avatar_v 引擎；2 分钟级出片，下载后 probe 验收；
- ⚠️ **真实单价 ~0.85 积分/秒**（15.7s 片实测 13 积分，559→546）。全长片提交前先拿 30s 中段核一次计价。

## [5] HyperFrames 透明叠加层（卡片/图表动效）
工程：`_cards_hf/compositions/v2_testcard.html`（换文案只动文字+时间戳）。
- 驱动模式：`gsap.timeline({paused:true})` 注册到 `window.__timelines["main-video"]` + 元素 `data-start/data-duration`；
- 渲染（约 4.5–5 分钟机时，**overlay_v2.mov 172MB 保留至定版，别中途删**——删一次重渲 5 分钟）：
```bash
export PATH="/d/ffmpeg:/c/Users/admin/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd _cards_hf && npx hyperframes render -c compositions/v2_testcard.html -f 25 --format mov \
  -o "../_v2/overlay_v2.mov"
```
- ⚠️ **四个必踩坑（全部实测踩平）**：
  1. 根元素必须 `data-composition-id="..."`，否则 `HF_DE_COMPOSITION_ROOT_MISSING`；
  2. 画幅用 **`data-width`/`data-height`**（`data-composition-width` 不被读取 → 输出竖屏 1080×1920）；
  3. 渲染机 PATH 里 **ffmpeg 和 ffprobe 都要有**（D:\ffmpeg 曾缺 ffprobe → `npm i ffprobe-static --registry=https://registry.npmmirror.com` 一分钟解决；**别从 gyan.dev 下 114MB 包**，国内 ~20KB/s 且断流）；
  4. 渲染输出 1920×1080，合成时 scale 到 1072 对齐成片。

## [6] ffmpeg 合成交付
工具：`工具_测试片v2合成_2026-09-22.py`（每期复制一份，只改顶部 SRC/OV/字幕/点位常量）。
- 链路：zoompan punch-in（8.45/13.25s 各 5%）→ overlay ProRes4444 → **ASS 字幕（`ass=` 路径必须正斜杠相对路径，反斜杠会被转义吞）** → 音效三件套（adelay 对位）→ BGM 床（sidechaincompress 人声闪避）→ loudnorm **-14 LUFS**；
- 字幕：词级时间戳断句，高亮词 `{\c&H6ABEE9&}词{\r}`（BGR 金色）；封面取 13.8s 帧。

## BGM / 音效范式（已成文：`整理_知识类视频BGM与音效范式_2026-09-22.md`）

**知识口播 = BGM 范式 B「信息陪伴型」**：BGM 是教室的灯光，不是舞台配乐。
1. 无旋律（pluck/拨弦，不"唱歌"）；2. C4+ 中高音区（**低音区长音 legato = 氛围片 drone = 压抑感，v2.2 教训**）；3. 跳音留白；4. BPM 88–104 贴语速；5. 频段避让人声 300Hz–3.4kHz；量级 -28~-32 LUFS 相对人声 + sidechain 闪避（threshold 0.028 / ratio 7 / attack 180ms / release 1000ms）。
- 两个预置在 `make_bgm_pluck`（默认）/ `make_bgm_pad`（A/B 备用），`BGM_STYLE` 一词切换；换风格只改和弦表。

**音效三件套**（配方固定，只换点位）：whoosh 转场（lowpass ≤2400）→ tick 反馈（1.2–1.6kHz，量最低）→ thump 强调（全片 ≤2 次感叹号）；音量配比 强调 0.24 : 转场 0.22 : 反馈 0.165；任意 2s 窗口 ≤1 个点位。

## 成本台账（实测口径）
| 项 | 成本 |
|---|---|
| ASR / ffmpeg / HyperFrames / BGM 合成 | 0 |
| MiniMax 克隆 | 9.9 元/音色（首合成才计费）；TTS ≈0.02 元/句 |
| HeyGen 测试片 | **13 积分 / 15.7s**；69s 全长估 ~59 积分，2:44 版估 ~140 |

## 验收清单（出片后逐项过）
1. `volumedetect`：mean ≈ -17dB / max ≤ -2.5dB（无削波）；
2. 抽 3 帧（图表卡 / 关键词卡 / 结论卡时点）：**人脸双手零遮挡**（安全区：左卡 56–546px、右卡 1150–1860px、顶部标题 84px、底部字幕 200px）；
3. 听感三点：开头 3s 有动能、人声突出、结尾有停留感。

## 待办（定版前必办）
- [ ] 全长母版拍板：69s 句末版 or 2:44 全段重裁（74.8s 半句版禁用）；
- [ ] 全长片增量：A7 章节卡 ×5 段、S4 逐句上屏、BGM 扩成 4–8 小节循环 + 尾奏、3s 关注卡。
