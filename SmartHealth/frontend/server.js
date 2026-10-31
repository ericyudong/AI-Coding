/**
 * SmartHealth 前端控制台服务（零 npm 依赖）。
 *
 * 只做两件事：
 *   1. 静态托管 public/（自包含前端，无任何外部 CDN，院内可离线运行）
 *   2. 把 /api/** 反向代理到后端，避免浏览器跨域与令牌二次配置
 *
 * 用法：
 *   node server.js                         # 默认代理到 http://127.0.0.1:8100
 *   node server.js --api http://host:8100  # 指定后端
 *   node server.js --port 8101
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const { URL } = require('url');

function parseArgs(argv) {
  const args = { port: 8101, api: 'http://127.0.0.1:8100', host: '127.0.0.1' };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const val = argv[i + 1];
    if (key === '--port') { args.port = parseInt(val, 10); i += 1; }
    else if (key === '--api') { args.api = val; i += 1; }
    else if (key === '--host') { args.host = val; i += 1; }
  }
  return args;
}

const ARGS = parseArgs(process.argv);
const PUBLIC_DIR = path.join(__dirname, 'public');
const API_BASE = new URL(ARGS.api);

/**
 * 除 /api/** 外，还需要反向代理的路径。
 *
 * 为什么：前端常被当作唯一对外入口（院内只开一个端口）。
 * 若探针与指标请求落到静态服务上，会被 SPA 回退成 index.html 并返回 200 ——
 * 监控看到"一切正常"，运维却拿不到任何真实状态，这比直接 404 更危险。
 */
const PROXY_PREFIXES = ['/api/', '/healthz', '/readyz', '/metrics',
                        '/docs', '/redoc', '/openapi.json'];

function shouldProxy(url) {
  return PROXY_PREFIXES.some((p) => url === p || url.startsWith(p));
}

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.map': 'application/json; charset=utf-8',
};

/* ------------------------------------------------------------------ 代理 */

/**
 * 识别 SSE 请求。
 *
 * 前端被当作唯一对外入口时（院内只开一个端口），SSE 必须经过这层代理。
 * 而 Node 的 http 代理**默认会缓冲响应**：upstream.pipe(res) 看着是流式，
 * 但只要 socket 未设置 noDelay、且没有显式 flushHeaders，中间这一跳就可能
 * 把 SSE 攒在缓冲区里，表现为"浏览器 EventSource 连上了但永远收不到事件"。
 * 所以这里对 SSE 走一条专用分支：显式 flushHeaders、关 Nagle、禁超时。
 */
function isSseRequest(req) {
  const accept = String(req.headers.accept || '');
  return accept.includes('text/event-stream') || req.url.startsWith('/api/v1/jobs/stream');
}

function proxy(req, res) {
  const options = {
    hostname: API_BASE.hostname,
    port: API_BASE.port || 80,
    path: req.url,
    method: req.method,
    headers: { ...req.headers, host: API_BASE.host },
  };

  const sse = isSseRequest(req);
  const upstream = http.request(options, (upRes) => {
    const headers = { ...upRes.headers };
    if (sse) {
      // 双重保险：上游已声明 X-Accel-Buffering，这里再压一次，确保任何
      // 中间设备都不缓冲；同时补 Connection/Cache-Control。
      headers['Cache-Control'] = 'no-cache, no-transform';
      headers['X-Accel-Buffering'] = 'no';
      headers['Connection'] = 'keep-alive';
      delete headers['content-length'];   // 长度未知（长连接），留着会让客户端等满
    }
    res.writeHead(upRes.statusCode, headers);
    if (sse) {
      res.flushHeaders();                  // 立即把响应头推出去，EventSource 才能进入 open
      res.socket.setNoDelay(true);         // 关 Nagle：小帧不攒批，毫秒级送达
      res.socket.setTimeout(0);            // 长连接不设空闲超时
    }
    upRes.pipe(res);
  });

  if (sse) {
    upstream.setNoDelay(true);
    upstream.setTimeout(0);
  }

  upstream.on('error', (err) => {
    res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({
      code: 502,
      message: `后端不可达（${API_BASE.origin}）：${err.code || err.message}。请先执行 python run.py 启动后端。`,
      data: null,
    }));
  });

  req.pipe(upstream);
}

/* -------------------------------------------------------------- 静态资源 */
function serveStatic(req, res) {
  let urlPath = decodeURIComponent(req.url.split('?')[0]);
  if (urlPath === '/' || urlPath === '') urlPath = '/index.html';

  // 防止路径穿越
  const safePath = path.normalize(path.join(PUBLIC_DIR, urlPath));
  if (!safePath.startsWith(PUBLIC_DIR)) {
    res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('403 Forbidden');
    return;
  }

  fs.stat(safePath, (err, stat) => {
    if (err || !stat.isFile()) {
      // SPA 回退：未命中的非静态路径统一返回 index.html
      fs.readFile(path.join(PUBLIC_DIR, 'index.html'), (e2, buf) => {
        if (e2) {
          res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
          res.end('404 Not Found');
          return;
        }
        res.writeHead(200, { 'Content-Type': MIME['.html'], 'Cache-Control': 'no-cache' });
        res.end(buf);
      });
      return;
    }
    const ext = path.extname(safePath).toLowerCase();
    res.writeHead(200, {
      'Content-Type': MIME[ext] || 'application/octet-stream',
      'Cache-Control': ext === '.html' ? 'no-cache' : 'public, max-age=300',
    });
    fs.createReadStream(safePath).pipe(res);
  });
}

/* ------------------------------------------------------------------ 启动 */
const server = http.createServer((req, res) => {
  const urlPath = req.url.split('?')[0];
  if (shouldProxy(urlPath)) {
    proxy(req, res);
    return;
  }
  serveStatic(req, res);
});

server.listen(ARGS.port, ARGS.host, () => {
  console.log('='.repeat(68));
  console.log('  SmartHealth 控制台');
  console.log(`  打开：http://${ARGS.host}:${ARGS.port}`);
  console.log(`  后端：${API_BASE.origin}（代理 /api/** 与探针 /healthz · /readyz · /metrics）`);
  console.log('  演示账号：admin/admin123 · cmo/cmo123 · algo01/algo01123 · doctor01/doctor01123');
  console.log('='.repeat(68));
});
