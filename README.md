# Vibe 知识视频工作台

这是从《没回来的飞机》最终“动态叙事版”整理出来的本地项目。保存选题、完整叙事、深色视觉、主体与因果动画、音乐卡点、双语字幕和渲染验收流程，供其他 Codex 会话继续制作新主题。

**项目面向持续制作内容不同、表现风格相近的短视频。** 沉没成本、博弈、自然现象等主题各自建立独立故事与主体动画；《没回来的飞机》只是一条已完成的参考样片。每条片还可按选题调整色彩、物件、场景与节奏。

默认无口播、16:9、1080p、30fps。当前使用 Canvas + Playwright + FFmpeg，音乐决定时间轴。新主题需要创作内容与场景代码；脚本负责搭工程、预览、渲染和核对。

## 在其他会话里使用

在 Codex 中打开本项目目录 `D:\projectdemo\vibe-knowledge-video`，发送：

> 先读项目 AGENTS.md、README.md 和 docs/制作方案.md，按本项目当前方案制作一支主题为「沉没成本」的完整视频。先确定锚词与故事，再完成分镜和主题动画；使用默认音乐，预览修正后渲染，交付一个 MP4。参考《没回来的飞机》的动态叙事版，但为新主题重新设计主体与事件。

如果新会话在其他目录，先发送：

> 项目位于 D:\projectdemo\vibe-knowledge-video，请先读取该项目 AGENTS.md，接下来的工作全部放在这个项目里。

可直接复制的通用提示词见 [prompts/新会话启动.md](prompts/新会话启动.md)。只讨论时，在请求里加“先沟通选题和方案，不渲染”。

## 快速运行

PowerShell 中：

```powershell
Set-Location 'D:\projectdemo\vibe-knowledge-video'
python .\vibe.py doctor
python .\vibe.py list
python .\vibe.py check missing-planes
```

依赖为 Python 3.10+、NumPy、Pillow、Playwright、Chrome 或 Playwright Chromium、FFmpeg 和 FFprobe。当前机器已验证可用。换环境可使用项目虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# 已装 Chrome 可直接使用；未装时安装 Playwright Chromium
.\.venv\Scripts\python.exe -m playwright install chromium
.\vibe.ps1 doctor
```

`vibe.ps1` 优先使用本项目 `.venv`，否则使用 PATH 中的 Python；不需要激活虚拟环境。FFmpeg/FFprobe 需在 PATH 中。

## 查看认可的示例与源码

- 已认可成片：`videos/missing-planes/reference/没回来的飞机_动态叙事版.mp4`。
- 实际动作分镜和事实核对：`videos/missing-planes/storyboard.md`。
- 4 个场景模块与基础绘制：同目录 `motion_*.js` 和 `film_motion.js`。
- 字幕与时间轴：同目录 `plan.json`；资源、音效与抽帧配置：`film.json`。

重新预览、渲染与混音：

```powershell
python .\vibe.py preview missing-planes
python .\vibe.py render missing-planes --start 0 --end 90 --name smoke --jobs 2
python .\vibe.py mix missing-planes
python .\vibe.py serve missing-planes
```

浏览器访问 `http://127.0.0.1:8765/videos/missing-planes/player.html`，用播放器检查音画，用滑块逐帧查看。停止服务器按 Ctrl+C。所有服务只绑定本机。

需要重建完整示例时：

```powershell
python .\vibe.py render missing-planes --jobs 4
python .\vibe.py finalize missing-planes
```

成片位于 `videos/missing-planes/build/final_video.mp4`。正式渲染前需已有与当前源码匹配且无越界问题的预览；查看预览图片和动作序列后再执行。`finalize` 会重做混音、合成、全片解码、时长和同步检查，并生成成片抽帧。报告通过后仍须查看抽帧、核对实际动作与试听。

## 开始新选题

```powershell
python .\vibe.py new sunk-cost --title '舍不得' --topic '沉没成本'
```

此命令创建 `videos/sunk-cost/` 的待制作骨架，默认使用已打包音乐。依次完成 `brief.md`、`research.md`、`storyboard.md`，在 `plan.json` 填字幕，在 `scenes.js` 创作主题动画，在 `film.json` 调整音效与检查时点。`plan.js` 由工具同步。

骨架默认 `production_ready=false`，只能作为创作起点，不能直接渲染完整成片。完成内容与动画后再改为 true，执行 `preview → 看图修正 → render → finalize → 看图和试听 → 交付`。新音源需先执行 `analyze-music` 并重新制定时间轴；不自动套用 17 秒。

## 文件结构

```text
AGENTS.md                  跨会话自动读取的当前规则
README.md                  项目入口与运行命令
docs/制作方案.md            当前完整方案
docs/选题与叙事.md          选题、故事闭合和内容模板
docs/渲染与验收.md          配置、工具接口与验收边界
docs/history/              早期资料，保留来源但不作为风格默认值
prompts/新会话启动.md       复制给其他会话的提示词
assets/fonts/              本地字体及许可
assets/music/              已选定音乐与检测记录
templates/episode/         新视频骨架
tools/                     渲染、混音、合成与核对
videos/<slug>/             每期分镜、字幕、源码和 build/ 输出
vibe.py / vibe.ps1         命令入口
```

当前优先级：用户本次明确要求 → AGENTS.md → 当前制作方案 → 本期故事和分镜 → 历史资料。旧的米白纸面默认风格已被深色、冷暖对比与动态叙事方案替代。资源来源见 [docs/资源与迁移.md](docs/资源与迁移.md)。

本机实际验证结果见 [docs/项目验收记录.md](docs/项目验收记录.md)。
