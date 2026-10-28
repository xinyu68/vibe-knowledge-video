'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

// Exercise the real node implementation without installing a second n8n runtime.
const filename = path.join(__dirname, 'VibeVideo.node.js');
const loaded = new Module(filename, module);
loaded.filename = filename;
loaded.paths = module.paths;
loaded.require = id => id === 'n8n-workflow' ? {
  NodeOperationError: class extends Error {
    constructor(node, error) { super(error.message); this.cause = error; }
  },
} : require(id);
loaded._compile(fs.readFileSync(filename, 'utf8'), filename);
const { VibeVideo } = loaded.exports;

function context(parameters, input, controller = new AbortController()) {
  return {
    getInputData: () => [{ json: input }],
    getNodeParameter: name => parameters[name],
    getExecutionId: () => 'execution-42',
    getNode: () => ({ id: 'stage-1', name: 'test' }),
    getExecutionCancelSignal: () => controller.signal,
    evaluateExpression: () => 'http://127.0.0.1:5678/form-waiting/42',
    helpers: { prepareBinaryData: async (buffer, fileName, mimeType) => ({ data: buffer.toString('base64'), fileName, mimeType }) },
  };
}
async function server(handler, fn) {
  const requests = [];
  const app = http.createServer(async (req, res) => {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const body = chunks.length ? JSON.parse(Buffer.concat(chunks)) : null;
    requests.push({ method: req.method, url: req.url, body });
    try {
      const answer = await handler(req, body);
      res.writeHead(answer.status || 200, { 'Content-Type': answer.mime || 'application/json' });
      res.end(answer.mime ? answer.data : JSON.stringify(answer.data));
    } catch (error) { res.writeHead(500); res.end(JSON.stringify({ error: { message: error.message } })); }
  });
  await new Promise(resolve => app.listen(0, '127.0.0.1', resolve));
  try { await fn(`http://127.0.0.1:${app.address().port}`, requests); }
  finally { app.closeAllConnections(); await new Promise(resolve => app.close(resolve)); }
}
function run(extra = {}) {
  return { run_id: 'run-01', revision: 1, slug: 'n8n-test-r01', title: 'test', preview_start: 0, preview_end: 12,
    artifacts: {}, cues: [{ id: 'p01', text: '你有没有遇到过？', start: 0, end: 12 }], ...extra };
}

test('node permits only local bridge and bounded preview input', async () => {
  const node = new VibeVideo();
  await assert.rejects(node.execute.call(context({ operation: 'configure', bridgeUrl: 'https://example.com' }, {})), /本机 HTTP/);
  await assert.rejects(node.execute.call(context({ operation: 'configure', bridgeUrl: 'http://127.0.0.1:5681', sourceSlug: '../other', previewStart: 0, previewEnd: 12 }, {})), /目录名/);
  await assert.rejects(node.execute.call(context({ operation: 'configure', sourceSlug: 'phantom-jam', previewStart: 0, previewEnd: 90 }, {})), /短片范围/);
});

test('review rejects stale forms and edits mixed with approval before HTTP write', async () => {
  const node = new VibeVideo();
  const params = { operation: 'review', referenceRunId: 'run-01', referenceRevision: 2 };
  await assert.rejects(node.execute.call(context(params, { run_id: 'run-01', expected_revision: 1, decision: 'approve' })), /版本不一致/);
  await assert.rejects(node.execute.call(context(params, { run_id: 'run-01', expected_revision: 2, decision: 'approve', cue_id: 'p01', text: 'change' })), /返修后重新预览/);
  await assert.rejects(node.execute.call(context(params, { run_id: 'run-01', expected_revision: 2, decision: 'revise', subtitles: '[{"index":0}]' })), /每条字幕修改/);
});

test('review retries share idempotency key and explicitly carry subtitle edits', async () => {
  await server(async () => ({ data: run({ revision: 2 }) }), async (base, requests) => {
    const node = new VibeVideo();
    const params = { operation: 'review', referenceRunId: 'run-01', referenceRevision: 1, referenceBridgeUrl: base };
    const input = { run_id: 'run-01', expected_revision: '1', '审核决定': '返修后重新预览',
      '配音段落 ID（返修时填写）': 'p01', '替换后的整段配音文本': '新的完整段落',
      '字幕修改 JSON（可选）': '[{"index":0,"zh":"新的字幕","en":"New caption"}]' };
    const first = await node.execute.call(context(params, input));
    await node.execute.call(context(params, input));
    assert.equal(first[0][0].json.decision, 'revise');
    assert.equal(requests[0].body.request_id, requests[1].body.request_id);
    assert.match(requests[0].body.request_id, /^n8n-[a-f0-9]{64}$/);
    assert.equal(requests[0].body.expected_revision, 1);
    assert.equal(requests[0].body.subtitles[0].index, 0);
  });
});

test('preview exposes real native media and keeps large final movie as URL', async () => {
  await server(async req => {
    if (req.url.endsWith('/jobs')) return { data: { job_id: 'job-01' } };
    if (req.url === '/api/jobs/job-01') return { data: { status: 'succeeded', result: run({
      artifacts: { poster: '/media/poster.jpg', preview: '/media/preview.mp4', soundtrack: '/media/audio.mp3', final_video: '/media/full.mp4', player: '/player' },
    }) } };
    if (req.url.endsWith('.jpg')) return { mime: 'image/jpeg', data: Buffer.from('image') };
    if (req.url.endsWith('.mp4')) return { mime: 'video/mp4', data: Buffer.from('video') };
    return { mime: 'audio/mpeg', data: Buffer.from('audio') };
  }, async (base, requests) => {
    const result = await new VibeVideo().execute.call(context({ operation: 'stage', stage: 'preview' }, run({ bridge_url: base })));
    const item = result[0][0];
    assert.equal(item.binary.poster.fileName, 'poster-r1.jpg');
    assert.equal(item.binary.preview.mimeType, 'video/mp4');
    assert.equal(item.binary.soundtrack.fileName, 'soundtrack-r1.mp3');
    assert.match(item.json.review_html, /<video controls width="100%"/);
    assert.match(item.json.review_url, /form-waiting\/42\/review-r1$/);
    assert.ok(!requests.some(req => req.url === '/media/full.mp4'));
  });
});

test('stopping an active stage sends cancellation to its exact job', async () => {
  const controller = new AbortController();
  await server(async req => {
    if (req.url.endsWith('/jobs')) return { data: { job_id: 'job-cancel' } };
    if (req.url.endsWith('/cancel')) return { data: { status: 'cancelled' } };
    setImmediate(() => controller.abort());
    return { data: { status: 'running' } };
  }, async (base, requests) => {
    await assert.rejects(new VibeVideo().execute.call(context({ operation: 'stage', stage: 'narrate' }, run({ bridge_url: base }), controller)));
    assert.equal(requests.filter(req => req.url === '/api/jobs/job-cancel/cancel').length, 1);
  });
});

test('workflow requires human review for every path to final render and loops revisions', () => {
  const workflow = JSON.parse(fs.readFileSync(path.join(__dirname, 'workflow.json'), 'utf8'));
  assert.equal(workflow.id, 'vibeKnowledgeVideo001');
  const waits = workflow.nodes.filter(n => n.type === 'n8n-nodes-base.wait');
  assert.equal(waits.length, 3);
  for (const [index, wait] of waits.entries()) {
    assert.equal(wait.typeVersion, 1.1);
    assert.equal(wait.parameters.resume, 'form');
    assert.equal(wait.parameters.limitWaitTime, false);
    assert.equal(wait.parameters.options.webhookSuffix, 'review-r' + (index + 1));
    assert.equal(workflow.connections[wait.name].main[0][0].node, '登记审核与版本');
  }
  const review = workflow.nodes.find(n => n.id === 'vibe-review');
  assert.match(review.parameters.referenceRevision, /\$items\("混音与画面预览", 0, \$runIndex\)/);
  assert.deepEqual(workflow.connections['审核分流'].main[1], [{ node: '合成段落配音', type: 'main', index: 0 }]);
  const incoming = Object.entries(workflow.connections).filter(([, value]) => value.main.flat().some(edge => edge.node === '全片渲染')).map(([name]) => name);
  assert.deepEqual(incoming, ['审核分流']);
});
