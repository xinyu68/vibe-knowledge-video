'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

function workflowModule() {
  try { return require('n8n-workflow'); } catch (error) {
    const marker = path.resolve(__dirname, '..', 'runtime-directory.txt');
    const runtime = process.env.N8N_RUNTIME_ROOT || (fs.existsSync(marker) ? fs.readFileSync(marker, 'utf8').trim() : '');
    if (!runtime) throw new Error('找不到 n8n-workflow。请设置 N8N_RUNTIME_ROOT，或在 custom-nodes 上级保存 runtime-directory.txt。', { cause: error });
    return require(path.join(runtime, 'node_modules', 'n8n-workflow'));
  }
}
const { NodeOperationError } = workflowModule();
const DEFAULT_BRIDGE = 'http://127.0.0.1:5681';
const MAX_BINARY_BYTES = 24 * 1024 * 1024;
const STAGES = new Set(['narrate', 'preview', 'render', 'finalize']);
const DECISIONS = { '通过并渲染全片': 'approve', '返修后重新预览': 'revise', '取消本次制作': 'cancel' };

function bridgeUrl(value) {
  const url = new URL(value || DEFAULT_BRIDGE);
  if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)
      || url.username || url.password || url.search || url.hash || url.pathname !== '/') {
    throw new Error('桥接地址必须是本机 HTTP 根地址，例如 http://127.0.0.1:5681');
  }
  return url.origin;
}
function safeUrl(value, base) {
  const url = new URL(typeof value === 'object' ? value.url : value, base);
  if (url.origin !== base) throw new Error('媒体地址必须与本机桥接服务同源');
  return url.href;
}
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}
function requestId(context, input, operation) {
  const tuple = [String(context.getExecutionId()), context.getNode().id, input.run_id || input.source_slug,
    input.revision ?? 0, operation];
  return 'n8n-' + crypto.createHash('sha256').update(JSON.stringify(tuple)).digest('hex');
}
async function jsonRequest(base, endpoint, { method = 'GET', body, signal } = {}) {
  const timeout = AbortSignal.timeout(30000);
  const response = await fetch(base + endpoint, {
    method, redirect: 'error', headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
  });
  const text = await response.text();
  let data;
  try { data = JSON.parse(text); } catch { throw new Error(`桥接返回非 JSON 数据：HTTP ${response.status}`); }
  if (!response.ok) throw new Error(data.error?.message || data.message || `桥接请求失败：HTTP ${response.status}`);
  return data;
}
function delay(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new Error('执行已停止'));
    const onAbort = () => { clearTimeout(timer); reject(new Error('执行已停止')); };
    const timer = setTimeout(() => { signal?.removeEventListener('abort', onAbort); resolve(); }, ms);
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}
function validateRun(run) {
  if (!run || typeof run.run_id !== 'string' || !Number.isInteger(run.revision)) {
    throw new Error('缺少制作版本 run_id / revision，请从“本期参数”开始运行');
  }
  return run;
}
async function runStage(context, input, stage, base, signal) {
  validateRun(input);
  if (!STAGES.has(stage)) throw new Error('不支持的制作阶段');
  const endpoint = '/api/runs/' + encodeURIComponent(input.run_id) + '/jobs';
  const body = { stage, request_id: requestId(context, input, stage) };
  let jobId;
  let cancelPromise;
  const cancel = () => {
    if (jobId && !cancelPromise) cancelPromise = jsonRequest(base, '/api/jobs/' + encodeURIComponent(jobId) + '/cancel', { method: 'POST', body: {} });
    // Observe rejection even while the execution engine is stopping the node.
    if (cancelPromise) cancelPromise.catch(() => {});
    return cancelPromise;
  };
  try {
    const submitted = await jsonRequest(base, endpoint, { method: 'POST', body, signal });
    jobId = submitted.job_id;
    if (!jobId) throw new Error('桥接服务未返回 job_id');
    signal?.addEventListener('abort', cancel, { once: true });
    if (signal?.aborted) throw new Error('执行已停止');
    const deadline = Date.now() + 6 * 60 * 60 * 1000;
    while (Date.now() < deadline) {
      const job = await jsonRequest(base, '/api/jobs/' + encodeURIComponent(jobId), { signal });
      if (job.status === 'succeeded') return { ...validateRun(job.result), job_id: jobId, stage, log_tail: job.log_tail || [] };
      if (['failed', 'cancelled'].includes(job.status)) {
        throw new Error(`${stage} ${job.status}：${typeof job.error === 'object' ? job.error?.message : job.error || '请查看桥接日志'}\n${Array.isArray(job.log_tail) ? job.log_tail.slice(-8).join('\n') : job.log_tail || ''}`);
      }
      if (!['queued', 'running'].includes(job.status)) throw new Error('桥接返回未知任务状态：' + job.status);
      await delay(2000, signal);
    }
    await cancel();
    throw new Error('阶段执行超过 6 小时，已请求取消');
  } catch (error) {
    if (signal?.aborted) {
      // Recover a submission whose response was interrupted, using the same idempotency key.
      if (!jobId) {
        try { jobId = (await jsonRequest(base, endpoint, { method: 'POST', body })).job_id; } catch { /* Service unavailable; persistent adapter records interrupted jobs. */ }
      }
      try { await cancel(); } catch (cancelError) { throw new Error(`执行已停止，但桥接取消请求失败：${cancelError.message}`, { cause: error }); }
    }
    throw error;
  } finally { signal?.removeEventListener('abort', cancel); }
}
function reviewPayload(input, runId, revision) {
  if (input.run_id !== runId || Number(input.expected_revision) !== Number(revision)) {
    throw new Error('审核表单与当前预览版本不一致，请重新打开当前执行的审片链接');
  }
  const decision = DECISIONS[input['审核决定']] || input.decision;
  if (!['approve', 'revise', 'cancel'].includes(decision)) throw new Error('请选择通过、返修或取消');
  const feedback = String(input['审片意见'] || input.feedback || '').trim();
  const cueId = String(input['配音段落 ID（返修时填写）'] || input.cue_id || '').trim();
  const text = String(input['替换后的整段配音文本'] || input.text || '').trim();
  const rawSubtitles = input['字幕修改 JSON（可选）'] || input.subtitles || '';
  const payload = { decision, feedback, expected_revision: Number(revision) };
  if (Boolean(cueId) !== Boolean(text)) throw new Error('配音返修需要同时填写段落 ID 和替换后的整段文本');
  if (cueId) { payload.cue_id = cueId; payload.text = text; }
  if (rawSubtitles) {
    let subtitles;
    try { subtitles = typeof rawSubtitles === 'string' ? JSON.parse(rawSubtitles) : rawSubtitles; }
    catch { throw new Error('字幕修改必须是有效 JSON 数组，例如 [{"index":0,"zh":"中文字幕","en":"English subtitle"}]'); }
    if (!Array.isArray(subtitles) || subtitles.some(s => !Number.isInteger(s.index) || s.index < 0 || typeof s.zh !== 'string' || typeof s.en !== 'string')) {
      throw new Error('每条字幕修改都需包含非负整数 index、中文 zh 和英文 en');
    }
    payload.subtitles = subtitles;
  }
  if (decision !== 'revise' && (cueId || payload.subtitles?.length)) throw new Error('有文本修改时请选择“返修后重新预览”，不能一边改稿一边通过');
  return payload;
}
function reviewHtml(run, base) {
  const a = run.artifacts || {};
  const links = [['player', '打开全片实时播放器'], ['preview', '下载当前短片'], ['narration', '试听预览区间配音'], ['soundtrack', '试听固定音乐混音']]
    .filter(([key]) => a[key]).map(([key, label]) => `<a href="${escapeHtml(safeUrl(a[key], base))}" target="_blank" rel="noopener">${label}</a>`).join(' · ');
  const media = a.preview ? `<video controls width="100%"${a.poster ? ` poster="${escapeHtml(safeUrl(a.poster, base))}"` : ''}><source src="${escapeHtml(safeUrl(a.preview, base))}" type="video/mp4"></video>` : '';
  const cues = (run.cues || []).map(c => `<li><b>${escapeHtml(c.id)}</b> [${escapeHtml(c.start)}–${escapeHtml(c.end)}s] ${escapeHtml(c.text)}</li>`).join('');
  return `<p><b>${escapeHtml(run.title || run.slug)} · 第 ${run.revision} 版</b></p>${media}<p>${links}</p>` +
    `<p>短片范围：${run.preview_start}–${run.preview_end} 秒。全片播放器可查看其他位置。只有明确通过后才启动全片渲染。</p>` +
    `<p>配音文本和字幕是两份数据：改配音不会自动改字幕、分镜或动画。字幕需明确填写下方 JSON，索引从 0 开始。仅写审片意见会保留意见并创建返修版本，不会自动代写动画。</p>` +
    `<p>返修次数：${run.revision_count ?? 0} / ${run.max_revisions ?? 2}。涉及分镜、选题、节奏结构的修改应先回到项目修改源文件，再发起新制作。</p><h3>当前配音段落</h3><ul>${cues}</ul>`;
}
async function addMedia(context, output, base, stage, signal) {
  const requested = stage === 'narrate' ? ['narration'] : stage === 'preview' ? ['poster', 'preview', 'soundtrack'] : [];
  const warnings = [];
  for (const key of requested) {
    const source = output.json.artifacts?.[key];
    if (!source) continue;
    try {
      const url = safeUrl(source, base);
      const response = await fetch(url, { redirect: 'error', signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(60000)]) : AbortSignal.timeout(60000) });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      if (Number(response.headers.get('content-length')) > MAX_BINARY_BYTES) { await response.body?.cancel(); throw new Error('超过 24 MiB，使用 artifacts 链接查看'); }
      let size = 0; const chunks = [];
      for await (const chunk of response.body) {
        size += chunk.length;
        if (size > MAX_BINARY_BYTES) throw new Error('超过 24 MiB，使用 artifacts 链接查看');
        chunks.push(chunk);
      }
      const mime = (response.headers.get('content-type') || '').split(';')[0] || (key === 'poster' ? 'image/png' : key === 'preview' ? 'video/mp4' : 'audio/wav');
      const ext = mime === 'image/jpeg' ? 'jpg' : mime === 'image/png' ? 'png' : mime === 'video/mp4' ? 'mp4' : mime === 'audio/mpeg' ? 'mp3' : path.extname(new URL(url).pathname).slice(1) || 'wav';
      output.binary ||= {};
      output.binary[key] = await context.helpers.prepareBinaryData(Buffer.concat(chunks), `${key}-r${output.json.revision}.${ext}`, mime);
    } catch (error) {
      if (signal?.aborted) throw error;
      warnings.push(`${key}：${error.message}`);
    }
  }
  if (warnings.length) output.json.media_warnings = warnings;
}

class VibeVideo {
  constructor() {
    this.description = {
      displayName: '知识视频制作', name: 'vibeVideo', group: ['transform'], version: 1,
      icon: 'fa:video',
      description: '连接本机知识视频工程：独立版本、配音、可试听预览、人工审片与全片渲染',
      defaults: { name: '知识视频制作', color: '#507a9f' }, inputs: ['main'], outputs: ['main'],
      properties: [
        { displayName: '操作', name: 'operation', type: 'options', default: 'configure', options: [
          { name: '本期参数', value: 'configure' }, { name: '建立独立制作版本', value: 'create' },
          { name: '执行制作阶段', value: 'stage' }, { name: '登记人工审核', value: 'review' },
          { name: '整理结果', value: 'result' }] },
        { displayName: '本机桥接地址', name: 'bridgeUrl', type: 'string', default: DEFAULT_BRIDGE,
          displayOptions: { show: { operation: ['configure'] } } },
        { displayName: '已编写的片目目录名', name: 'sourceSlug', type: 'string', default: 'phantom-jam',
          description: '选择已有完整片目；目录中需有 film.json、配音稿和动画源文件', displayOptions: { show: { operation: ['configure'] } } },
        { displayName: '短片起始秒', name: 'previewStart', type: 'number', default: 0, typeOptions: { minValue: 0 }, displayOptions: { show: { operation: ['configure'] } } },
        { displayName: '短片结束秒', name: 'previewEnd', type: 'number', default: 12, typeOptions: { minValue: 1 }, displayOptions: { show: { operation: ['configure'] } } },
        { displayName: '制作阶段', name: 'stage', type: 'options', default: 'narrate', options: [
          { name: '合成段落配音', value: 'narrate' }, { name: '混音与画面预览', value: 'preview' },
          { name: '全片渲染', value: 'render' }, { name: '封装与技术验收', value: 'finalize' }], displayOptions: { show: { operation: ['stage'] } } },
        { displayName: '审核对应制作 ID', name: 'referenceRunId', type: 'string', default: '', displayOptions: { show: { operation: ['review'] } } },
        { displayName: '审核对应版本', name: 'referenceRevision', type: 'number', default: 1, displayOptions: { show: { operation: ['review'] } } },
        { displayName: '审核对应桥接地址', name: 'referenceBridgeUrl', type: 'string', default: DEFAULT_BRIDGE, displayOptions: { show: { operation: ['review'] } } },
        { displayName: '已授权的工程步骤，不接受任意命令。图片、短片、音频见输出的 Binary 标签；大文件见 artifacts 链接。', name: 'notice', type: 'notice', default: '' },
      ],
    };
  }
  async execute() {
    const items = this.getInputData(); const outputs = [];
    for (let i = 0; i < items.length; i++) {
      try {
        const input = items[i].json;
        const operation = this.getNodeParameter('operation', i);
        const signal = this.getExecutionCancelSignal();
        let base = bridgeUrl(input.bridge_url || DEFAULT_BRIDGE);
        let result; let stage;
        if (operation === 'configure') {
          const supplied = input.body || {};
          base = bridgeUrl(this.getNodeParameter('bridgeUrl', i));
          const sourceSlug = String(supplied.source_slug || this.getNodeParameter('sourceSlug', i));
          const start = Number(supplied.preview_start ?? this.getNodeParameter('previewStart', i));
          const end = Number(supplied.preview_end ?? this.getNodeParameter('previewEnd', i));
          if (!/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(sourceSlug)) throw new Error('片目目录名只能包含字母、数字、下划线和短横线');
          if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start || end - start > 30) throw new Error('短片范围应为 0–30 秒之间的有效片段');
          await jsonRequest(base, '/health', { signal });
          result = { source_slug: sourceSlug, preview_start: start, preview_end: end };
        } else if (operation === 'create') {
          result = validateRun(await jsonRequest(base, '/api/runs', { method: 'POST', signal,
            body: { source_slug: input.source_slug, preview_start: input.preview_start, preview_end: input.preview_end, request_id: requestId(this, input, 'create') } }));
        } else if (operation === 'stage') {
          stage = this.getNodeParameter('stage', i);
          result = await runStage(this, input, stage, base, signal);
        } else if (operation === 'review') {
          base = bridgeUrl(this.getNodeParameter('referenceBridgeUrl', i));
          const runId = this.getNodeParameter('referenceRunId', i);
          const revision = this.getNodeParameter('referenceRevision', i);
          const payload = reviewPayload(input, runId, revision);
          payload.request_id = requestId(this, { run_id: runId, revision }, 'review-' + crypto.createHash('sha256').update(JSON.stringify(payload)).digest('hex'));
          result = validateRun(await jsonRequest(base, '/api/runs/' + encodeURIComponent(runId) + '/review', { method: 'POST', body: payload, signal }));
          result.decision = payload.decision;
        } else if (operation === 'result') {
          result = { ...input, delivery_note: input.decision === 'cancel' ? '本次制作已取消，已有版本和预览保留。' : '全片已生成并完成技术检查；发布前仍需人工观看并核对引用。大文件通过 artifacts.final_video 打开，不写入 n8n 执行数据库。' };
        } else throw new Error('未知操作');
        result.bridge_url = base;
        if (stage === 'preview') {
          result.review_html = reviewHtml(result, base);
          const reviewUrl = new URL(this.evaluateExpression('{{ $execution.resumeFormUrl }}', i));
          reviewUrl.pathname = reviewUrl.pathname.replace(/\/$/, '') + '/review-r' + result.revision;
          result.review_url = reviewUrl.href;
        }
        const output = { json: result, pairedItem: { item: i } };
        if (stage) await addMedia(this, output, base, stage, signal);
        outputs.push(output);
      } catch (error) { throw new NodeOperationError(this.getNode(), error, { itemIndex: i }); }
    }
    return [outputs];
  }
}
module.exports = { VibeVideo };
