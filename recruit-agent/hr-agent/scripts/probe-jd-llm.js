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
const base = env.OPENAI_BASE_URL.replace(/\/$/, '');
const key = env.OPENAI_API_KEY;
const model = env.OPENAI_MODEL;

async function once(label, messages, max_tokens) {
  const started = Date.now();
  try {
    const res = await fetch(`${base}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${key}` },
      body: JSON.stringify({ model, messages, temperature: 0.4, max_tokens }),
    });
    const text = await res.text();
    console.log(label, { status: res.status, ms: Date.now() - started, preview: text.slice(0, 180).replace(/\s+/g, ' ') });
  } catch (e) {
    console.log(label, { error: e.message, ms: Date.now() - started });
  }
}

(async () => {
  await once('short', [{ role: 'user', content: '用一句话写Java后端JD标题' }], 64);
  await once(
    'jd-json',
    [
      {
        role: 'system',
        content:
          '你是资深招聘顾问。根据业务描述生成结构化 JD。只输出 JSON：{externalJd,internalJd,persona,optimizationTips,followUpQuestions}',
      },
      {
        role: 'user',
        content: JSON.stringify({ title: '待定岗位', brief: '需要一个Java后端，业务线供应链，3年以上经验' }),
      },
    ],
    1200
  );
})();
