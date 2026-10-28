'use strict';

const fs = require('node:fs');
const path = require('node:path');
const nodes = [];
const connections = {};
function node(id, name, type, typeVersion, position, parameters, extra = {}) {
  nodes.push({ id, name, type, typeVersion, position, parameters, ...extra });
  return name;
}
function custom(id, name, position, operation, parameters = {}) {
  return node(id, name, 'CUSTOM.vibeVideo', 1, position, { operation, ...parameters });
}
function link(from, to, output = 0) {
  connections[from] ||= { main: [] };
  while (connections[from].main.length <= output) connections[from].main.push([]);
  connections[from].main[output].push({ node: to, type: 'main', index: 0 });
}
const manual = node('vibe-manual', '手动开始', 'n8n-nodes-base.manualTrigger', 1, [-960, 100], {});
const webhook = node('vibe-webhook', '本机接口开始', 'n8n-nodes-base.webhook', 2, [-960, 280], {
  httpMethod: 'POST', path: 'vibe-knowledge-video', responseMode: 'onReceived', options: {},
}, { webhookId: 'vibe-knowledge-video-local-v1' });
const settings = custom('vibe-configure', '本期参数', [-720, 180], 'configure', {
  bridgeUrl: 'http://127.0.0.1:5681', sourceSlug: 'phantom-jam', previewStart: 0, previewEnd: 12,
});
const create = custom('vibe-create', '建立独立制作版本', [-480, 180], 'create');
const narrate = custom('vibe-narrate', '合成段落配音', [-240, 180], 'stage', { stage: 'narrate' });
const preview = custom('vibe-preview', '混音与画面预览', [0, 180], 'stage', { stage: 'preview' });
const revisionRouter = node('vibe-review-revision', '选择当前审片版本', 'n8n-nodes-base.switch', 3.2, [240, 180], {
  mode: 'rules', rules: { values: [1, 2, 3].map(revision => ({
    conditions: { options: { caseSensitive: true, leftValue: '', typeValidation: 'strict', version: 2 },
      conditions: [{ id: 'review-r' + revision, leftValue: '={{ $json.revision }}', rightValue: revision, operator: { type: 'number', operation: 'equals' } }], combinator: 'and' },
    renameOutput: true, outputKey: '第 ' + revision + ' 版',
  })) }, options: { fallbackOutput: 'extra', renameFallbackOutput: '超出最大轮次' },
});
const reviewWait = (revision, label, y) => node('vibe-review-form-r' + revision, label, 'n8n-nodes-base.wait', 1.1, [480, y], {
  resume: 'form', incomingAuthentication: 'none',
  formTitle: '={{ "知识视频审片 · 第 " + $json.revision + " 版" }}',
  formDescription: '={{ $json.review_html }}',
  formFields: { values: [
    { fieldType: 'hiddenField', fieldName: 'run_id', fieldValue: '={{ $json.run_id }}' },
    { fieldType: 'hiddenField', fieldName: 'expected_revision', fieldValue: '={{ String($json.revision) }}' },
    { fieldLabel: '审核决定', fieldType: 'dropdown', requiredField: true,
      fieldOptions: { values: ['通过并渲染全片', '返修后重新预览', '取消本次制作'].map(option => ({ option })) } },
    { fieldLabel: '审片意见', fieldType: 'textarea', placeholder: '记录节奏、声音、画面、字幕问题。意见会保存；具体配音和字幕修改请填下方。' },
    { fieldLabel: '配音段落 ID（返修时填写）', fieldType: 'text', placeholder: '从上方段落清单复制准确 ID' },
    { fieldLabel: '替换后的整段配音文本', fieldType: 'textarea', placeholder: '替换一个完整段落，保持已分配的时间窗口。不是一句一句重新起腔。' },
    { fieldLabel: '字幕修改 JSON（可选）', fieldType: 'textarea', placeholder: '[{"index":0,"zh":"中文字幕","en":"English subtitle"}]' },
  ] },
  responseMode: 'onReceived', limitWaitTime: false,
  options: { webhookSuffix: 'review-r' + revision, appendAttribution: false, respondWithOptions: { values: { respondWith: 'text', formSubmittedText: '已提交。请回到 n8n 执行画布查看处理进度；返修完成后，重新打开当前审片链接查看新版本。' } } },
}, { webhookId: 'vibe-knowledge-video-review-r' + revision, notesInFlow: true, notes: '打开预览节点输出 review_url；此链接只适用于本轮。逐项审片后再通过。' });
const waits = [reviewWait(1, '人工审片 · 首版', 20), reviewWait(2, '人工审片 · 返修一版', 200), reviewWait(3, '人工审片 · 返修二版', 380)];
const overflow = node('vibe-review-overflow', '达到返修上限', 'n8n-nodes-base.stopAndError', 1, [480, 600], {
  errorType: 'errorMessage', errorMessage: '已超过两轮返修。请回到片目源文件完成结构调整，再发起新的制作。',
});
const review = custom('vibe-review', '登记审核与版本', [720, 180], 'review', {
  referenceRunId: '={{ $items("混音与画面预览", 0, $runIndex)[0].json.run_id }}',
  referenceRevision: '={{ $items("混音与画面预览", 0, $runIndex)[0].json.revision }}',
  referenceBridgeUrl: '={{ $items("混音与画面预览", 0, $runIndex)[0].json.bridge_url }}',
});
const route = node('vibe-route', '审核分流', 'n8n-nodes-base.switch', 3.2, [960, 180], {
  mode: 'rules', rules: { values: [
    ['approve', '通过 → 全片渲染'], ['revise', '返修 → 配音与预览'], ['cancel', '取消 → 保留结果'],
  ].map(([value, label]) => ({ conditions: { options: { caseSensitive: true, leftValue: '', typeValidation: 'strict', version: 2 },
    conditions: [{ id: 'decision-' + value, leftValue: '={{ $json.decision }}', rightValue: value, operator: { type: 'string', operation: 'equals' } }], combinator: 'and' },
    renameOutput: true, outputKey: label })) }, options: {},
});
const render = custom('vibe-render', '全片渲染', [1200, 60], 'stage', { stage: 'render' });
const finalize = custom('vibe-finalize', '封装与技术验收', [1440, 60], 'stage', { stage: 'finalize' });
const result = custom('vibe-result', '查看最终成片', [1680, 60], 'result');
const cancel = custom('vibe-cancel', '已取消 · 保留已有版本', [1200, 400], 'result');
node('vibe-help', '使用说明', 'n8n-nodes-base.stickyNote', 1, [-1020, -380], {
  content: '## 知识视频 · 第一条可审片生产线\n1. 在「本期参数」选择已有片目，设置 0–30 秒短片范围。默认 phantom-jam。\n2. 点击 Execute workflow，看配音、预览节点逐步运行。\n3. 节点输出 Binary 可直接看图、听配音、播短片；JSON 的 artifacts.player 是全片实时播放器。\n4. 到人工审片时打开 review_url。通过才渲染全片；返修会保留旧版并再次预览。\n5. 最后从 artifacts.final_video 打开成片。\n\n本机服务与素材均保存在本地；此工作流不自动发送飞书、不发布作品。',
  height: 390, width: 660, color: 5,
});
node('vibe-boundary', '范围与返修边界', 'n8n-nodes-base.stickyNote', 1, [-300, -380], {
  content: '## 这次跑通什么\n已有选题/剧本/动画 → 独立版本 → 云健段落配音 → 固定音乐混音 → 预览 → 人工审核 → 渲染 → 技术检查。\n\n## 还需要人完成什么\n新选题、资料核查、故事、分镜、动画和美术仍在现有项目中完成；不是输入一句话自动创作成片。\n\n## 返修不会遗漏字幕\n审核页可明确替换一个配音段落，并单独提交字幕 JSON。配音改稿不会自动同步字幕/动画；仅填意见只保存意见，默认最多返修两轮。\n技术验收不能证明叙事或画面质量。',
  height: 390, width: 660, color: 4,
});
node('vibe-ops', '运行与中断', 'n8n-nodes-base.stickyNote', 1, [420, -440], {
  content: '## 版本与停止\n每次执行建立独立版本。返修保存上一版，旧审片表单不能通过新版本。\n配音/渲染期间按 n8n Stop 会请求桥接取消任务；失败节点展开看错误与日志。\n重试相同执行、节点、版本会复用幂等任务；新执行会新建版本。\n\n## 测试入口\n发布后可本机 POST /webhook/vibe-knowledge-video，body 可带 source_slug、preview_start、preview_end。测试入口同样必须人工审核，不能跳过审核。\n大母版只留本地链接，避免塞进 n8n 执行数据库。',
  height: 350, width: 660, color: 6,
});
link(manual, settings); link(webhook, settings); link(settings, create); link(create, narrate);
link(narrate, preview); link(preview, revisionRouter);
waits.forEach((wait, index) => { link(revisionRouter, wait, index); link(wait, review); });
link(revisionRouter, overflow, 3); link(review, route);
link(route, render, 0); link(route, narrate, 1); link(route, cancel, 2);
link(render, finalize); link(finalize, result);

const workflow = {
  id: 'vibeKnowledgeVideo001', name: '知识视频 · 配音预览与审片返修', active: false,
  nodes, connections, pinData: {},
  settings: { executionOrder: 'v1', saveExecutionProgress: true, saveManualExecutions: true,
    saveDataErrorExecution: 'all', saveDataSuccessExecution: 'all', timezone: 'Asia/Shanghai' },
};
fs.writeFileSync(path.join(__dirname, 'workflow.json'), JSON.stringify(workflow, null, 2) + '\n', 'utf8');
console.log('Generated integrations/n8n/workflow.json');
