const fs = require('fs');
const path = require('path');

const envPath = path.join(__dirname, '..', '.env');
const env = {};
for (const line of fs.readFileSync(envPath, 'utf8').split(/\r?\n/)) {
  const t = line.trim();
  if (!t || t.startsWith('#')) continue;
  const i = t.indexOf('=');
  if (i <= 0) continue;
  let v = t.slice(i + 1).trim();
  if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1);
  env[t.slice(0, i).trim()] = v;
}

const base = (env.OPENAI_BASE_URL || '').replace(/\/$/, '');
const key = env.OPENAI_API_KEY || '';
const model = env.OPENAI_MODEL || '';
const keyMask = key ? `${key.slice(0, 6)}...${key.slice(-4)} (len=${key.length})` : '(empty)';

console.log('config', { base, model, keyMask });

async function probe(name, url, init, timeoutMs) {
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), timeoutMs);
  const started = Date.now();
  try {
    const res = await fetch(url, { ...init, signal: ac.signal });
    const text = await res.text();
    const ms = Date.now() - started;
    let parsed = null;
    try {
      parsed = JSON.parse(text);
    } catch {
      /* html or plain */
    }
    const summary = {
      status: res.status,
      ok: res.ok,
      ms,
      contentType: res.headers.get('content-type'),
      bodyPreview: text.slice(0, 500).replace(/\s+/g, ' '),
    };
    if (parsed?.data && Array.isArray(parsed.data)) {
      summary.modelIds = parsed.data.slice(0, 20).map((m) => m.id || m.name || m);
    }
    if (parsed?.choices?.[0]?.message?.content) {
      summary.reply = String(parsed.choices[0].message.content).slice(0, 200);
    }
    if (parsed?.error) summary.errorObj = parsed.error;
    console.log(`\n=== ${name} ===`);
    console.log(JSON.stringify(summary, null, 2));
    return summary;
  } catch (e) {
    console.log(`\n=== ${name} ===`);
    console.log(JSON.stringify({ error: `${e.name}: ${e.message}`, ms: Date.now() - started }, null, 2));
    return { ok: false, error: e.message };
  } finally {
    clearTimeout(timer);
  }
}

(async () => {
  const models = await probe('GET /models', `${base}/models`, { headers: { Authorization: `Bearer ${key}` } }, 20000);

  const chat = await probe(
    'POST /chat/completions',
    `${base}/chat/completions`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${key}`,
      },
      body: JSON.stringify({
        model,
        messages: [{ role: 'user', content: '只回复一个词：pong' }],
        temperature: 0,
        max_tokens: 32,
      }),
    },
    60000
  );

  // 若 models 列表里有候选，对前几个再试一次（仅当当前模型失败时）
  if (!chat.ok && models.modelIds?.length) {
    for (const mid of models.modelIds.slice(0, 3)) {
      await probe(
        `POST chat model=${mid}`,
        `${base}/chat/completions`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${key}`,
          },
          body: JSON.stringify({
            model: mid,
            messages: [{ role: 'user', content: '只回复：pong' }],
            temperature: 0,
            max_tokens: 16,
          }),
        },
        45000
      );
    }
  }

  const verdict = {
    baseReachable: !!(models.status || chat.status),
    modelsOk: !!models.ok,
    chatOk: !!chat.ok,
    configuredModelWorks: !!chat.ok,
  };
  console.log('\n=== VERDICT ===');
  console.log(JSON.stringify(verdict, null, 2));
})();
