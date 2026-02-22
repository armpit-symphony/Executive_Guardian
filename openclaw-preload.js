// Executive Guardian preload for OpenClaw gateway
// Intercepts high-risk primitives and routes through guardian_cli.py
// Toggle with: EXEC_GUARDIAN_PRELOAD=1 (must be set in systemd env)

const fs = require('fs');
const cp = require('child_process');

const ENABLED = process.env.EXEC_GUARDIAN_PRELOAD === '1' || process.env.EXEC_GUARDIAN_PRELOAD === 'true';
const PY = process.env.EXEC_GUARDIAN_PY || '/usr/bin/python3';
const CLI = process.env.EXEC_GUARDIAN_CLI || '/home/sparky/.openclaw/workspace/executive_guardian/guardian_cli.py';
const LANE = process.env.OPENCLAW_AGENT_ID || 'main';

function logLine(msg) {
  try {
    fs.mkdirSync('/tmp/openclaw', { recursive: true });
    fs.appendFileSync('/tmp/openclaw/executive-guardian-preload.log', msg + '\n');
  } catch {}
}

function callGuardian(payload) {
  // synchronous so tool calls are truly routed through guardian
  const input = JSON.stringify(payload);
  const res = cp.spawnSync(PY, [CLI], { input, encoding: 'utf8' });
  if (res.error) throw res.error;
  const txt = (res.stdout || '').trim();
  if (!txt) throw new Error(`guardian_cli_empty_stdout: ${res.stderr || ''}`);
  let obj;
  try { obj = JSON.parse(txt); } catch (e) { throw new Error(`guardian_cli_bad_json: ${txt.slice(0, 200)}`); }
  if (!obj.ok) throw new Error(`guardian_cli_not_ok: ${JSON.stringify(obj).slice(0, 300)}`);
  return obj;
}

if (!ENABLED) {
  logLine(`[exec-guardian-preload] loaded (DISABLED) ${new Date().toISOString()} pid=${process.pid}`);
  return;
}

logLine(`[exec-guardian-preload] loaded ${new Date().toISOString()} pid=${process.pid}`);

// ---- child_process.exec routing ----
const origExec = cp.exec;
cp.exec = function patchedExec(command, options, callback) {
  try {
    const task_id = `gw-exec-${Date.now()}`;
    const out = callGuardian({
      type: "command_exec",
      task_id,
      lane: LANE,
      command: String(command),
    });
    const r = out.result || {};
    const stdout = r.stdout || '';
    const stderr = r.stderr || '';
    const code = (r.returncode == null ? 0 : r.returncode);

    if (typeof options === 'function') callback = options;
    if (typeof callback === 'function') callback(code ? new Error(`exit ${code}`) : null, stdout, stderr);

    // emulate ChildProcess enough for callers that just need "something"
    return { pid: process.pid, stdout: null, stderr: null };
  } catch (e) {
    try {
      if (typeof options === 'function') callback = options;
      if (typeof callback === 'function') callback(e, '', String(e));
    } catch {}
    // fallback to original if anything weird happens
    return origExec.apply(cp, arguments);
  }
};

// ---- fs write routing (sync + promises) ----
const origWriteFileSync = fs.writeFileSync;
fs.writeFileSync = function patchedWriteFileSync(path, data, options) {
  const content = Buffer.isBuffer(data) ? data.toString('utf8') : String(data ?? '');
  const task_id = `gw-fw-${Date.now()}`;
  callGuardian({ type: "file_write", task_id, lane: LANE, path: String(path), content });
  return; // success
};

if (fs.promises && fs.promises.writeFile) {
  const origWriteFile = fs.promises.writeFile.bind(fs.promises);
  fs.promises.writeFile = async function patchedWriteFile(path, data, options) {
    const content = Buffer.isBuffer(data) ? data.toString('utf8') : String(data ?? '');
    const task_id = `gw-fw-${Date.now()}`;
    callGuardian({ type: "file_write", task_id, lane: LANE, path: String(path), content });
    return;
  };
}

// ---- fetch routing (best-effort) ----
if (typeof globalThis.fetch === 'function' && typeof globalThis.Response === 'function') {
  const origFetch = globalThis.fetch.bind(globalThis);
  globalThis.fetch = async function patchedFetch(url, init = {}) {
    try {
      const method = (init.method || 'GET').toUpperCase();
      const headers = init.headers || {};
      const body = init.body != null ? (typeof init.body === 'string' ? init.body : String(init.body)) : null;

      const task_id = `gw-http-${Date.now()}`;
      const out = callGuardian({
        type: "http_request",
        task_id,
        lane: LANE,
        expected_statuses: [200, 201, 202, 204, 206, 301, 302, 304],
        request: { method, url: String(url), headers, body }
      });

      const r = out.result || {};
      return new Response(r.body || '', { status: r.status || 200, headers: r.headers || {} });
    } catch (e) {
      // fallback to native fetch
      return origFetch(url, init);
    }
  };
}
