// Renders scene.html frame-by-frame with headless Chromium and pipes PNGs into ffmpeg.
// Usage:
//   node render.js                         -> out/video.mp4 (full 16s @ 30fps)
//   node render.js --stills 2,6,10,13      -> out/still_<t>.png preview frames
//   node render.js --from 4 --to 9 --fps 15 -> partial preview
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');

const args = process.argv.slice(2);
const opt = (name, def) => { const i = args.indexOf('--' + name); return i >= 0 ? args[i + 1] : def; };
const FPS = +opt('fps', 30);
const OUT = path.join(__dirname, 'out');
fs.mkdirSync(OUT, { recursive: true });

const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json' };
const server = http.createServer((req, res) => {
  const p = path.join(__dirname, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(__dirname) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': types[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});

(async () => {
  await new Promise(r => server.listen(0, r));
  const url = `http://127.0.0.1:${server.address().port}/scene.html`;
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
  page.on('pageerror', e => console.error('PAGE ERROR:', e.message));
  page.on('console', m => { if (m.type() === 'error') console.error('console:', m.text()); });
  await page.goto(url);
  await page.waitForFunction('window.ready === true', null, { timeout: 120000 });
  fs.writeFileSync(path.join(OUT, 'events.json'), JSON.stringify(await page.evaluate(() => window.getEvents()), null, 1));
  const duration = await page.evaluate(() => window.DURATION);
  const wrap = await page.$('#wrap');

  const stills = opt('stills', null);
  if (stills) {
    for (const t of stills.split(',').map(Number)) {
      await page.evaluate(t => window.renderAt(t), t);
      await wrap.screenshot({ path: path.join(OUT, `still_${t}.png`) });
      console.log('still', t);
    }
  } else {
    const from = +opt('from', 0), to = +opt('to', duration);
    const file = path.join(OUT, opt('out', 'video_silent.mp4'));
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-',
      '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '17', '-preset', 'slow', '-movflags', '+faststart', file], { stdio: ['pipe', 'inherit', 'inherit'] });
    const n = Math.round((to - from) * FPS), t0 = Date.now();
    for (let f = 0; f < n; f++) {
      await page.evaluate(t => window.renderAt(t), from + f / FPS);
      const buf = await wrap.screenshot({ type: 'png' });
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (f % 30 === 0) console.log(`frame ${f}/${n}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
    }
    ff.stdin.end();
    await new Promise(r => ff.on('close', r));
    console.log('wrote', file);
  }
  await browser.close();
  server.close();
})().catch(e => { console.error(e); process.exit(1); });
