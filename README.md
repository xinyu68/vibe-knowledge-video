# Vibe 知识短视频制作项目

用代码和动画，把一个知识问题讲成普通人看得懂、有起因和结果的故事。项目提供从选题、事实核对、分镜和动画，到音乐、字幕、渲染和检查的完整本地流程。

**每次可以制作不同内容的新短片。** 例如：为什么投入越多越难放弃、为什么个人的选择会造成集体困境、为什么成功经验不能直接照搬。题目可以涉及心理、社会、自然和科学，但都要查证事实、重新设计故事与主体动画。

默认制作带中文 AI 配音、双语字幕、音乐驱动的动画短片：16:9、1080p、30fps，深色画面搭配有含义的色彩对比。**中文配音负责讲述，音乐负责情绪和大结构，动画负责展示过程。** 先按音乐安排段落与高潮，再安放旁白和动作；配乐保持稳定增益，不随每句话反复升降。风格、主题、声音和音乐可按每期需要调整，也可指定无口播。工具使用 Canvas + Playwright + FFmpeg，全部在本地运行。

## 让创作助手制作第一条短片

先按下方步骤安装环境，在 Codex 等支持本地文件与代码执行的创作助手中打开克隆后的项目文件夹，发送：

> 先读 AGENTS.md、制作方案和配音流程，帮我做一支关于「为什么投入越多越难放弃」的完整知识短视频。面向普通人，用故事和动作解释沉没成本，使用默认音乐、画风和云健中文配音。音乐控制大结构，旁白安排在合适的位置，配乐保持稳定、不做逐句闪避。先查事实、设计故事与带旁白的分镜，实测配音时长，预览修正后渲染，交付一个 MP4。

想换题目，替换引号中的问题即可。每条片会创建独立目录，重新创作故事、字幕和场景。制作流程是：

> 观众关心的问题 → 故事与事实核对 → 音乐结构和旁白分镜 → 合成配音并实测 → 主题动画与字幕 → 看预览并修正 → 稳定配乐混音、渲染与检查 → 完整 MP4

默认成片保存在 `videos/<主题目录>/build/final_video.mp4`。如果助手未打开本项目，把你实际克隆的目录告诉它即可。项目可以放在任意电脑和目录。

完整提示词见 [prompts/新会话启动.md](prompts/新会话启动.md)。如果想先讨论，在请求里加“先沟通选题和方案，不渲染”。脚本提供工程骨架和制作工具，具体内容与动画需要创作助手编写。

## 快速运行

先安装 Python 3.10+、FFmpeg 和 FFprobe，并确保 FFmpeg/FFprobe 可从 PATH 调用。浏览器可使用本机 Chrome，或按下方命令安装 Playwright Chromium。字体、音乐和参考样片已随仓库保存。

在你选择的父目录中克隆：

```shell
git clone https://github.com/xinyu68/vibe-knowledge-video.git
cd vibe-knowledge-video
```

Windows / PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe .\vibe.py doctor
.\.venv\Scripts\python.exe .\vibe.py list
.\.venv\Scripts\python.exe .\vibe.py check missing-planes
```

macOS / Linux：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python vibe.py doctor
.venv/bin/python vibe.py list
.venv/bin/python vibe.py check missing-planes
```

Linux 若缺浏览器的系统依赖，可按 [Playwright 官方说明](https://playwright.dev/python/docs/browsers#install-system-dependencies)执行 `python -m playwright install --with-deps chromium`（使用本项目虚拟环境的 Python）。FFmpeg 安装包见 [FFmpeg 下载页](https://ffmpeg.org/download.html)。

后续示例里的 `python` 表示当前项目的虚拟环境解释器：可激活环境后执行，或替换成上述完整的相对解释器路径。PowerShell 也可用 `.\vibe.ps1 doctor` 等命令；它按脚本所在目录寻找 `.venv`，不依赖调用者的当前目录。

换电脑或移动项目后重新创建 `.venv`，不要复制旧虚拟环境；虚拟环境自身可能记录解释器路径，见 [Python venv 文档](https://docs.python.org/3/library/venv.html)。项目源码和资源通过脚本位置与相对路径定位。`doctor` 显示的是当前机器实际位置，用于诊断，并不是写死的配置。

## 了解一个完整示例（可选）

仓库附带一支解释**幸存者偏差**的完整示例：通过受损飞机能否返航、哪些记录被留下，说明只看成功案例为什么可能判断失准。它用于展示工程结构、动作如何解释知识，以及整条工具链如何运行。新选题的制作规范已独立写在项目文档中。

- 示例成片：`videos/missing-planes/reference/没回来的飞机_动态叙事版.mp4`。
- 实际动作分镜和事实核对：`videos/missing-planes/storyboard.md`。
- 4 个场景模块与基础绘制：同目录 `motion_*.js` 和 `film_motion.js`。
- 字幕与时间轴：同目录 `plan.json`；资源、音效与抽帧配置：`film.json`。
- 当前配音正文与时间窗：`narration.json`；29 句原始合成音频及元数据：`audio/narration/`。这些已随仓库保存，可离线重建当前示例的混音。

重新预览、渲染与混音：

```powershell
python .\vibe.py preview missing-planes
python .\vibe.py render missing-planes --start 0 --end 90 --name smoke --jobs 2
python .\vibe.py mix missing-planes
python .\vibe.py serve missing-planes
```

浏览器访问 `http://127.0.0.1:8765/videos/missing-planes/player.html`，用播放器检查音画，用滑块逐帧查看。停止服务器按 Ctrl+C。所有服务只绑定本机。

需要了解完整渲染步骤时，可重建这个示例：

```powershell
python .\vibe.py render missing-planes --jobs 4
python .\vibe.py finalize missing-planes
```

当前示例成片位于 `videos/missing-planes/build-voiceover-stable/final_video.mp4`，按 `film.json.output` 决定。正式渲染前需已有与当前源码匹配且无越界问题的预览；查看预览图片和动作序列后再执行。`finalize` 会重做混音、合成、全片解码、时长和同步检查，并生成成片抽帧。报告通过后仍须查看抽帧、核对实际动作与试听。`build/` 和 `build-*/` 为本机生成物，不上传 GitHub；新电脑需执行上方命令重建，`reference/` 中的是历史参考片。

## 开始新选题

```powershell
python .\vibe.py new sunk-cost --title '舍不得' --topic '沉没成本' --narrated
```

此命令创建 `videos/sunk-cost/` 的带配音待制作骨架，默认使用已打包音乐、云健中文声音和稳定配乐。依次完成 `brief.md`、`research.md`、`storyboard.md`，在 `plan.json` 填字幕，在 `narration.json` 填本期旁白与时间窗，在 `scenes.js` 创作主题动画，在 `film.json` 调整音效与检查时点。`plan.js` 由工具同步。新骨架的 `cues` 为空，必须写正文后才能合成或混音；不能直接当成成片。不带 `--narrated` 仍可创建兼容的无口播骨架。

骨架默认 `production_ready=false`，只能作为创作起点，不能直接渲染完整成片。先合成配音，按实测时长修正文案和动作；完成内容与动画后再改为 true，执行 `mix → preview → 看图修正 → render → finalize → 看图和试听 → 交付`。新音源需先执行 `analyze-music` 并重新制定时间轴；不自动套用 17 秒。生成新旁白的方法见下方配音章节。

## 文件结构

```text
AGENTS.md                  跨会话自动读取的当前规则
README.md                  项目入口与运行命令
docs/制作方案.md            当前完整方案
docs/选题与叙事.md          选题、故事闭合和内容模板
docs/渲染与验收.md          配置、工具接口与验收边界
docs/配音流程.md            中文旁白、实测入窗、稳定混音与跨电脑使用
docs/history/              早期资料，保留来源但不作为风格默认值
prompts/新会话启动.md       复制给其他会话的提示词
assets/fonts/              本地字体及许可
assets/music/              已选定音乐与检测记录
templates/episode/         新视频骨架
templates/narration.json    带配音骨架使用的空白时间轴
tools/                     渲染、混音、合成与核对
videos/<slug>/             每期分镜、字幕、源码和 build/ 输出
vibe.py / vibe.ps1         命令入口
```

当前优先级：用户本次明确要求 → AGENTS.md → 制作方案 → 本期故事和分镜 → 历史资料。资源来源与示例资料见 [docs/资源与迁移.md](docs/资源与迁移.md)。

本机实际验证结果见 [docs/项目验收记录.md](docs/项目验收记录.md)。

## 生成中文 AI 旁白

每期可以选择无口播或配音；音乐继续作为主时钟。当前幸存者偏差示例已增加云健 `zh-CN-YunjianNeural` 配音配置，稳定配乐版输出在 `videos/missing-planes/build-voiceover-stable/`，旧版保留在 `build/`、`build-voiceover/` 和 `reference/`。

`film.json` 的 `narration` 指向本期 `narration.json`，逐句声明文案、开始时间、最晚结束时间及对应字幕编号。原始 WAV 和合成信息缓存在本期 `audio/narration/`，因此已有音频的混音、渲染与合成可完全离线进行。删除 `narration` 配置就恢复无口播混音。

需要生成或修改旁白时，准备 [ttsCN](https://github.com/Agents365-ai/ttsCN) 的 `scripts/tts.py`，在本项目 Python 虚拟环境安装可选配音依赖（固定此次验证过的 edge-tts 7.3.1）。已有 Codex ttsCN 技能可直接使用其脚本，无须复制个人技能目录到仓库。新电脑使用自己的安装位置，不沿用另一台机器的绝对路径。

```powershell
python -m pip install -r requirements-tts.txt
$ttsCli = Read-Host '请输入 ttsCN scripts/tts.py 的完整路径'
python .\vibe.py narrate missing-planes --tts-cli $ttsCli
python .\vibe.py mix missing-planes
python .\vibe.py preview missing-planes
python .\vibe.py render missing-planes --jobs 4
python .\vibe.py finalize missing-planes
```

上面演示修改示例；新主题将 `missing-planes` 换成本期 slug。macOS/Linux 同样在项目虚拟环境安装依赖，用 `python vibe.py narrate <slug> --tts-cli <实际安装的脚本路径>` 传入本机位置。此路径仅是一次命令参数，不保存到影片配置。Edge 合成需要联网、不需要 key；已有缓存的 `mix`、渲染和合成不需要连接 TTS 服务。

`narrate` 只对变化的文案重新请求合成，逐句实测并安放音频，不按字数猜时长。超出窗口最多允许约 10% 的保音高加速；仍放不下时停止，改短文案后重合成。整体旁白按双声道等效响度处理至约 −18 LUFS；默认 `music_mode=constant`，音乐整段保持固定增益，句间不反复升降，首高潮保护区不安排旁白。当前示例配乐固定 −18dB，保留原曲自身动态。详见 [docs/配音流程.md](docs/配音流程.md)。

可移植性回归测试：安装依赖和浏览器后运行 `python -m unittest discover -s tests -v`。该测试把当前源码及运行资源复制到含中文和空格的新目录，从无关工作目录检查示例、创建新主题、生成预览、渲染短片和混音；不需要原机器目录。
