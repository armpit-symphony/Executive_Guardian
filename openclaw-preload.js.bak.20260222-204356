/**
 * Executive Guardian preload (SAFE MINIMAL)
 * Purpose: prove preload is running without touching module loading.
 */
(() => {
  try {
    const fs = require("fs");
    const dir = "/tmp/openclaw";
    try { fs.mkdirSync(dir, { recursive: true }); } catch {}
    const line = `[exec-guardian-preload] loaded ${new Date().toISOString()} pid=${process.pid}\n`;
    fs.appendFileSync(`${dir}/executive-guardian-preload.log`, line);
    console.error(line.trim());
  } catch {
    // never crash OpenClaw because of guardian
  }
})();
