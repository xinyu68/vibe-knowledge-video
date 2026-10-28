# 本地 n8n 视频工作流

这条工作流把现有工程接到 n8n 画布：已有片目 → 独立副本 → 段落配音 → 稳定配乐混音与预览 → 审片 → 返修或全片渲染 → 封装和技术检查。

当前处理已经编写好的片目。选题、事实核查、故事、分镜和主题动画仍按本项目规范完成，不会根据一句题目自动生成这些内容。工作流也不会自动解决视觉重复，仍须查看全片分镜、完整声音和连续画面。

## 日常使用

1. 运行 `tools/start-video-workflow.ps1`。首次传入自己的 n8n 安装目录和 ttsCN CLI 位置，之后从本机配置读取。
2. 在本地 n8n 打开“知识视频 · 配音预览与审片返修”。双击“本期参数”，填写已有片目目录名，例如 `phantom-jam`，设置预览起止秒数（片段最长 30 秒）。
3. 选择“手动开始”作为触发器，执行工作流。编辑器会实时高亮执行中的节点和已走过的连线，建议日常用这个入口。接口启动的任务从“执行”记录进入；当前版本在运行期间主要显示状态，等待审片或结束后可查看完整节点轨迹，不能把它当作实时画布。
4. 配音节点输出包含试听；预览节点的 Binary 标签可看海报、播短片。JSON 的 `artifacts` 是本地媒体链接，`review_url` 是当前轮次的审片表单。过大的文件只通过链接查看。
5. 表单内观看短片，并打开全片实时播放器检查其他位置。通过会继续渲染全片；返修会建立下一版，重新配音、混音、预览并等待；取消会保留已有文件并结束。
6. 最后从“查看最终成片”的 `artifacts.final_video` 打开完整 MP4，默认 1920×1080、30fps；音乐和时长来自片目配置。

原始片目不会被覆盖。制作副本保存在 `videos/n8n-<run_id>-r01/`，返修生成 `r02`、`r03`。状态、日志、本机路径配置保存在 `.local/n8n/`；运行产物均已排除出 Git。

## 安装与启动

先按 README 配好 Python 虚拟环境、FFmpeg、浏览器和字体：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-tts.txt
.\.venv\Scripts\python.exe vibe.py doctor
```

复用已有本地 n8n，不要求 Docker。当前在 n8n 2.44.7、Node.js 24、Python 3.12 上联调；其他版本须重新验证原生 Wait 表单和自定义节点接口。

使用带 `start-n8n.ps1` 的 n8n-studio 安装时，在没有执行中的任务时停止它，再安装本项目节点。下列位置替换为自己电脑的实际目录：

```powershell
& '<n8n目录>\stop-n8n.ps1'
.\tools\install-video-workflow.ps1 -N8nDirectory '<n8n目录>'
.\tools\start-video-workflow.ps1 -N8nDirectory '<n8n目录>' -TtsCli '<ttsCN目录>\scripts\tts.py'
```

在 n8n 新建工作流，用 Import from File 导入 `integrations/n8n/workflow.json`。手动执行无需发布；需要本机 Webhook 时再发布工作流。这里的发布只启用本地触发器，不会上传网站或视频。

UI 导入可能产生新的工作流 ID。导入后复制浏览器中的实际本地地址，运行一次 `tools/start-video-workflow.ps1 -WorkflowUrl 'http://127.0.0.1:5678/workflow/<实际ID>'` 保存入口；不要直接输入尖括号占位符。未设置时启动器打开工作流列表，避免使用另一台电脑的 ID。

n8n 2.44 的发布异步生效，保存草稿或发布请求返回后不能立即假定接口已切换。更新后先确认发布状态完成再触发；自动化安装可核对 `publication-status` 的 `status=published` 且 `liveVersionId` 等于目标版本。已经在等待的执行仍保留启动时的画布，不会自动换成新版本。

普通 n8n 安装：把 `integrations/n8n/VibeVideo.node.js` 放入配置的 `N8N_CUSTOM_EXTENSIONS` 目录，确保可以解析 `n8n-workflow` 包；必要时设置进程级 `N8N_RUNTIME_ROOT` 为含 `node_modules` 的 n8n 运行目录。重启后导入工作流，桥接可单独启动：

```powershell
$env:VIBE_TTS_CLI = '<ttsCN目录>\scripts\tts.py'
.\.venv\Scripts\python.exe tools/n8n_bridge.py --port 5681
```

服务仅监听本机。默认 n8n 为 `http://127.0.0.1:5678`，桥接为 `http://127.0.0.1:5681`。5679 可能由 n8n 任务运行器占用，不能作为桥接默认端口。更换桥接端口时同步修改启动器 `-Port` 与“本期参数”的桥接地址。

本机路径只写入 Git 忽略的 `.local/n8n/settings.json`。源码通过脚本位置定位项目；换电脑重新配置路径、创建虚拟环境，不复制旧 `.venv` 或运行状态。启动器复用已有 n8n 登录方式，不记录账号、密码或 API Key。

## 审片和返修边界

- **配音改稿**：填写准确段落 ID 和替换后的完整段落，保持连续语气和原有时间窗。超窗时先改文案，或回到工程调整时间轴。
- **字幕改稿**：独立填写 JSON 数组，例如 `[{"index":0,"zh":"没有事故，怎么停了？","en":"No crash. Why have we stopped?"}]`，索引从 0 开始。它替换字幕文字，不自动翻译或对齐。
- **意见记录**：自由文字会保存。只写“画面太重复”“增加转场”，不会自动重写动画；结构修改应回到工程完成后重新开始制作。
- **通过**：仅针对当前已预览版本。改稿先返修再预览，不能在同一次提交中既改稿又通过。三版审片使用独立固定路径，旧表单不能消耗下一轮等待。
- **轮数**：默认最多返修两轮。更复杂调整回到工程完成，再启动新制作。

沿用中文云健段落配音、独立字幕和固定增益配乐，不恢复逐句闪避。配音试听只覆盖所选预览区间；全片声音通过混音链接或实时播放器检查。程序检查布局、源码一致性、封装、帧数和时长，不能替代审美、事实、叙事与真实试听。

## 中断和重试

展开失败节点查看错误和日志摘要，完整日志在 `.local/n8n/jobs/`。桥接把任务放在后台串行执行，n8n 节点等待其结果，不让一个 HTTP 请求覆盖整段渲染时间。

n8n Stop 会请求取消当前桥接任务及其子进程。`tools/stop-video-workflow.ps1` 核实根进程属于本项目后按进程树停止，不停止其他 n8n 工作流。桥接异常退出后，重启会把原有活动任务标记中断，不会自动重跑；若只强杀父进程，渲染子进程可能残留，需先核对并结束残留任务，再显式重试或新开制作。

相同执行、节点和版本的重复请求复用相同任务，避免重复生成；新执行建立新副本。源码或音乐变更后旧审批失效，旧文件不会作为当前产物返回。重新预览后才能通过。

节点升级需重启 n8n。安装脚本只复制节点，不自动覆盖你调整过的画布；重新导入 JSON 前先导出当前工作流备份。

## 工程文件

| 文件 | 用途 |
|---|---|
| `integrations/n8n/workflow.json` | 可导入画布 |
| `integrations/n8n/generate-workflow.cjs` | 工作流生成源 |
| `integrations/n8n/VibeVideo.node.js` | 本机节点、任务等待、媒体输出 |
| `tools/n8n_bridge.py` | 版本、持久任务和现有 CLI 适配 |
| `tools/start-video-workflow.ps1` | 日常启动入口 |
| `tools/stop-video-workflow.ps1` | 停止本项目桥接 |
| `tests/test_n8n_bridge.py` | 版本、审批、路径、取消和重试测试 |

发布后本机 `POST /webhook/vibe-knowledge-video` 可提交 `source_slug`、`preview_start`、`preview_end`，仍须经过审片，没有自动通过开关。节点只调用固定制作步骤，不接受任意 shell 命令。运行不会发送飞书或推送 GitHub。
