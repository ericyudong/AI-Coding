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

(async () => {
  const started = Date.now();
  const res = await fetch(`${base}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${key}` },
    body: JSON.stringify({
      model,
      temperature: 0.4,
      max_tokens: 900,
      messages: [
        {
          role: 'system',
          content:
            '你是招聘顾问。请用中文输出严格 JSON（不要 markdown）：{"externalJd":"对外JD全文","internalJd":"内部版摘要","persona":{"mustHave":[],"niceToHave":[],"seniority":""},"optimizationTips":[],"followUpQuestions":[]}。externalJd 控制在 400 字内，职责与要求各 3-5 条即可。',
        },
        {
          role: 'user',
          content: '岗位：Java后端\n需求：业务线供应链，3年以上经验\n组织：\n编制：',
        },
      ],
    }),
  });
  const text = await res.text();
  console.log({ status: res.status, ms: Date.now() - started, preview: text.slice(0, 300).replace(/\s+/g, ' ') });
})();
