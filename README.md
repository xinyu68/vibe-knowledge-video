# Vibe 知识短视频制作项目

用代码和动画，把一个知识问题讲成普通人看得懂、有起因和结果的故事。项目提供从选题、事实核对、分镜和动画，到音乐、字幕、渲染和检查的完整本地流程。

**每次可以制作不同内容的新短片。** 例如：为什么投入越多越难放弃、为什么个人的选择会造成集体困境、为什么成功经验不能直接照搬。题目可以涉及心理、社会、自然和科学，但都要查证事实、重新设计故事与主体动画。

**选题第一步：明确观众能带走什么认识，再设计故事和动画。** 每个候选题先写“看前直觉→看后认识”，说明观众以后能多问自己什么、依据是什么、适用边界在哪里。只有这些成立，才进入锚词、分镜和视觉设计；不能只因题材热门或好做动画就开始，也不在结尾硬补人生道理。具体标准见[选题与叙事](docs/选题与叙事.md)。

默认制作带中文 AI 配音、双语字幕、音乐驱动的动画短片：16:9、1080p、30fps，深色画面搭配有含义的色彩对比。**中文配音负责讲述，音乐负责情绪和大结构，动画负责展示过程。** 当前4.5方案采用语义段落整段合成、字幕独立分屏、因果线连续推进、镜头随叙事变化；避免每条字幕重新起腔和机械长停顿。先按音乐安排段落与高潮，再按实测声音对齐动作；配乐保持稳定增益，不随每句话反复升降。风格、主题、声音和音乐可按每期需要调整，也可指定无口播。工具使用 Canvas + Playwright + FFmpeg，全部在本地运行。

**同一条故事线不等于同一个物件占满全片。** 讲生活时让场景走出手机和卡片，转场后展示新的事件、关系或证据。先看全片分镜总览和带完整声音的粗剪，再精做动画；把重复镜头的原因、返修与复查记录在本期 `visual-review.md`。具体方法见[视觉叙事与镜头变化](docs/视觉叙事与镜头变化.md)。这是制作与审片要求，当前 CLI 不会自动判断画面是否单调。

## 让创作助手制作第一条短片

先按下方步骤安装环境，在 Codex 等支持本地文件与代码执行的创作助手中打开克隆后的项目文件夹，发送：

> 使用 $vibe-video，帮我做一支关于「为什么投入越多越难放弃」的完整知识短视频。面向普通人，其余采用项目默认值，由当前会话负责制作和检查。

想换题目，替换引号中的问题即可。每条片会创建独立目录，重新创作故事、字幕和场景。制作流程是：

> 认识、证据与故事 → 文案、音乐结构与实测配音 → 镜头设计与关键样段 → 专项视觉审核、返工后扩展镜头 → 完整混音粗剪 → 全片复查与返修 → 精做、渲染及成片检查 → 完整 MP4

默认成片保存在 `videos/<主题目录>/build/final_video.mp4`。如果助手未打开本项目，把你实际克隆的目录告诉它即可。项目可以放在任意电脑和目录。

完整提示词见 [prompts/新会话启动.md](prompts/新会话启动.md)。如果想先讨论，在请求里加“先沟通选题和方案，不渲染”。脚本提供工程骨架和制作工具，具体内容与动画需要创作助手编写。

## 当前会话直接制作

制作入口是仓库内 [vibe-video Skill](.agents/skills/vibe-video/SKILL.md)：按阶段读取规范，先读本期 `brief.md` 的当前制作记录，再接续工作。它不替代创作判断，也不会因为写了规则就自动保证质量。按[视觉参考与样段](docs/视觉参考与样段.md)选择本期参考，先验证造型与关键动作，再扩展全片；用户否定的近期试片不进入素材库。

先与当前会话讨论选题和大体思路，确认后由同一会话直接负责研究、文案、配音、分镜、动画、复查和交付。当前版本不依赖 n8n，不自动拆分制作 Agent；制作规范和逐项自查继续保留。

沿用原有本地 CLI；可选的[本地粗剪与检查工具](docs/本地粗剪与检查.md)能够导出带声音的关键短样段、完整混音的全片粗剪、镜头总览和检查记录。画面质量、人物动作及叙事节奏由当前会话实际检查，技术报告不能替代创作判断。

所有题材都须完成[专项视觉审核](docs/视觉参考与样段.md#专项视觉审核与放行)：检查主体结构、接触、遮挡、构图和动作，有人物时另查人体结构。工具生成未审草稿并校验记录、证据与版本，正式整片 `render/finalize` 不接受仅有 `production_ready=true` 的影片。未审或需返工时仍可生成预览、短样段和粗剪。审核由当前会话实际执行，不增加用户逐项审批，也不自动给画面打分。

## 快速运行

先安装 Python 3.10+，克隆仓库后运行一个初始化入口：

```shell
git clone https://github.com/xinyu68/vibe-knowledge-video.git
cd vibe-knowledge-video
python bootstrap.py
```

macOS/Linux 可使用 `python3 bootstrap.py`。初始化会创建项目虚拟环境、安装渲染与内置 Edge 配音依赖、下载本地 Chromium，并运行带全新配音的十秒自检。Windows x64 缺少 FFmpeg/FFprobe 时自动下载校验后的项目内副本；其他平台按提示安装。所有资源与服务留在本地，不修改系统 PATH。

成功后查看 `.local/self-test-latest.json` 中的 `ok`、`fresh_online_synthesis` 和测试视频位置。测试画面只验证工具链，不作为影片素材。完整步骤、失败重试和检查边界见[新电脑启动](docs/新电脑启动.md)。

后续命令中的 `python` 指本项目虚拟环境：Windows 使用 `.\.venv\Scripts\python.exe`，macOS/Linux 使用 `.venv/bin/python`。Windows 也可用 `.\vibe.ps1 doctor`，它从脚本位置定位项目与解释器。

```powershell
.\.venv\Scripts\python.exe vibe.py doctor
.\.venv\Scripts\python.exe vibe.py doctor --online
.\.venv\Scripts\python.exe vibe.py self-test
```

`doctor` 默认只检查本地依赖；`--online` 实际合成一句新语音。换电脑或移动项目后重建 `.venv`，不要复制旧虚拟环境。字体、音乐和工程示例随仓库保存；默认新配音无需额外寻找个人 Skill 脚本。

## 当前段落配音示例：没有事故，为什么突然堵了？

`videos/phantom-jam/` 用同一辆金色车经历减速、停车和驶出拥堵区，解释“车向前，拥堵波向后”。它展示本次优化后的完整流程：10段连续旁白、41条独立字幕、具有体积和状态变化的车辆、连续转场、简化模型与事实边界。数字属于本片实例，新主题无需照搬。

- 内容与证据：`brief.md`、`research.md`、`storyboard.md`。
- 配音与对齐：`narration.json`、`subtitle-script.json`、`timing_build.py`，以及10段已打包的 `audio/narration/` 缓存。
- 动作实现：`world.js`、`traffic.js`、`scenes.js`。模型参数是示意，不是原实验轨迹。
- 实际制作、修正和验收结果：`production-notes.md`。其中历史结果不能替代新电脑的重新检查。

新电脑无需联网合成声音即可重建这个已完成示例：

```powershell
python vibe.py check phantom-jam
python vibe.py mix phantom-jam
python vibe.py preview phantom-jam
python -m tools.visual_review prepare phantom-jam --evidence build/review/layout_audit.json
# 实际检查并填写 build/review/visual-review.json；需返工则先修正、重建证据
python -m tools.visual_review check phantom-jam
python vibe.py render phantom-jam --jobs 4
python vibe.py finalize phantom-jam
```

结果在 `videos/phantom-jam/build/final_video.mp4`。最终编码后还须查看关键帧并按实际条件试听；源帧通过不等于压缩后也无问题。`build/` 不上传GitHub，完整视频在本机生成。可选的 `node videos/phantom-jam/validate_model.js` 需要Node.js，仅使用内置模块，无需npm依赖；浏览器渲染仍按通用环境运行。

这支片的 `timing_build.py`、`prepare_release.py` 含专用时间轴和断言，不能直接套到新主题。它们用于理解实现方法；通用默认规则以 [制作方案](docs/制作方案.md)、[配音流程](docs/配音流程.md) 和 [新会话提示词](prompts/新会话启动.md) 为准。

## 较早的完整示例：幸存者偏差（可选）

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
python -m tools.visual_review prepare missing-planes --evidence build-voiceover-stable/review/layout_audit.json
# 实际检查并填写 build-voiceover-stable/review/visual-review.json
python -m tools.visual_review check missing-planes
python .\vibe.py render missing-planes --jobs 4
python .\vibe.py finalize missing-planes
```

当前示例成片位于 `videos/missing-planes/build-voiceover-stable/final_video.mp4`，按 `film.json.output` 决定。正式渲染前需已有与当前源码匹配且无越界问题的预览及通过的专项视觉审核记录。旧片不自动补通过，既有媒体保留；准备新一轮审核用 `prepare --replace` 备份旧记录并重置为未审。`finalize` 会重做混音、合成、全片解码、时长和同步检查，并生成成片抽帧。报告通过后仍须查看抽帧、核对实际动作与试听。`build/` 和 `build-*/` 为本机生成物，不上传 GitHub；新电脑需执行上方命令重建，`reference/` 中的是历史参考片。

## 开始新选题

```powershell
python .\vibe.py new sunk-cost --title '舍不得' --topic '沉没成本' --narrated
```

此命令创建 `videos/sunk-cost/` 的带配音待制作骨架，默认使用已打包音乐、云健中文声音和稳定配乐。依次完成 `brief.md`、`research.md`、`storyboard.md`，使用 `visual-review.md` 记录镜头总览、粗剪和全片审片；在 `plan.json` 填字幕，在 `narration.json` 填本期旁白与时间窗，在 `scenes.js` 创作主题动画，在 `film.json` 调整音效与检查时点。`plan.js` 由工具同步。新骨架的 `cues` 为空，必须写正文后才能合成或混音；不能直接当成成片。不带 `--narrated` 仍可创建兼容的无口播骨架。

骨架默认 `production_ready=false`，只能作为创作起点，不能直接渲染完整成片。先合成配音，按实测时长修正文案和动作；样段经专项视觉审核后再铺开全片。内容与动画完成后设为 true，执行 `mix → preview → 准备并实际完成当前版本视觉审核 → render → finalize → 看图和试听 → 交付`。审核命令及六项判断见[视觉参考与样段](docs/视觉参考与样段.md#专项视觉审核与放行)。新音源需先执行 `analyze-music` 并重新制定时间轴；不自动套用 17 秒。生成新旁白的方法见下方配音章节。

## 文件结构

```text
AGENTS.md                  跨会话自动读取的当前规则
README.md                  项目入口与运行命令
bootstrap.py               首次环境配置与十秒自检
docs/新电脑启动.md          新电脑安装、验证与故障恢复
docs/制作方案.md            当前完整方案
docs/选题与叙事.md          选题、故事闭合和内容模板
docs/视觉叙事与镜头变化.md  镜头变化、生活场景、全片粗剪与重复检查
docs/渲染与验收.md          配置、工具接口与验收边界
docs/配音流程.md            中文旁白、实测入窗、稳定混音与跨电脑使用
docs/history/              早期资料，保留来源但不作为风格默认值
prompts/新会话启动.md       复制给其他会话的提示词
.agents/skills/vibe-video/  当前会话制作 Skill
docs/视觉参考与样段.md      参考选择、样段检查与排除规则
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

`film.json` 的 `narration` 指向本期 `narration.json`，每个cue声明一个语义段落的文案、开始时间及最晚结束时间。字幕独立维护；旧逐句cue仍兼容。原始 WAV 和合成信息缓存在本期 `audio/narration/`，因此已有音频的混音、渲染与合成可完全离线进行。新骨架 `max_tempo=1.0`，超窗先改写或重排；删除 `narration` 配置就恢复无口播混音。

初始化已包含 `edge-tts`，新旁白直接用项目内接口合成：

```powershell
python vibe.py narrate <slug>
python vibe.py mix <slug>
```

使用前先在本期 `narration.json` 写真实段落。Edge 合成需要联网，无需 API key；已有声音缓存的混音与渲染可离线完成。项目保存原生词边界，不保证自动完成字幕和动作对齐。

旧的 `python vibe.py narrate <slug> --tts-cli <外部脚本路径>` 继续兼容，用于已有 ttsCN 环境或其他已配置后端；它是可选入口。`requirements-tts.txt` 也保留为兼容安装入口，不需要把个人技能目录加入仓库。内置接口使用 [edge-tts](https://github.com/rany2/edge-tts)，项目已验证的版本固定在 requirements.txt。

`narrate` 只对变化的cue重新请求合成，按语义段落实测并安放音频，不按字数猜时长。新模板 `max_tempo=1.0`，超窗先改短文案或重排窗口，再重合成受影响段落；旧配置允许的少量加速不作为新片默认。字幕与动作需要另行对齐，工具不会自动完成。整体旁白按双声道等效响度处理至约−18 LUFS；默认 `music_mode=constant`，音乐整段保持固定增益，句间不反复升降，首高潮保护区不安排旁白。示例配乐固定−18dB，保留原曲自身动态。详见 [docs/配音流程.md](docs/配音流程.md)。

可移植性回归测试：安装依赖和浏览器后运行 `python -m unittest discover -s tests -v`。该测试把当前源码及运行资源复制到含中文和空格的新目录，从无关工作目录检查示例、创建新主题、生成预览、渲染短片和混音；不需要原机器目录。
