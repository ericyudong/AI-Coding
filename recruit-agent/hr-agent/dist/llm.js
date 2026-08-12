"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.chatCompletion = chatCompletion;
exports.chatOrMock = chatOrMock;
exports.safeJsonParse = safeJsonParse;
const config_1 = require("./config");
function llmTimeoutMs() {
    return Number(process.env.LLM_TIMEOUT_MS || 90000);
}
/** OpenAI-compatible chat；无 API Key 时由调用方走 mock 路径 */
async function chatCompletion(messages, opts) {
    if (!(0, config_1.llmEnabled)()) {
        throw new Error('LLM_DISABLED');
    }
    const timeoutMs = llmTimeoutMs();
    const retries = opts?.retries ?? 2;
    let lastErr = null;
    for (let attempt = 0; attempt <= retries; attempt++) {
        const body = {
            model: config_1.config.openaiModel,
            messages,
            temperature: opts?.temperature ?? 0.4,
            max_tokens: opts?.maxTokens ?? 1024,
        };
        if (opts?.json && process.env.LLM_FORCE_JSON === '1') {
            body.response_format = { type: 'json_object' };
        }
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), timeoutMs);
        try {
            const res = await fetch(`${config_1.config.openaiBaseUrl}/chat/completions`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${config_1.config.openaiApiKey}`,
                },
                body: JSON.stringify(body),
                signal: controller.signal,
            });
            if (!res.ok) {
                const text = await res.text();
                const err = new Error(`LLM 调用失败: ${res.status} ${text.slice(0, 200)}`);
                // 网关超时/过载可重试
                if ((res.status === 504 || res.status === 502 || res.status === 429) && attempt < retries) {
                    lastErr = err;
                    console.warn(`[hr-agent] LLM ${res.status}，重试 ${attempt + 1}/${retries}`);
                    await new Promise((r) => setTimeout(r, 800 * (attempt + 1)));
                    continue;
                }
                throw err;
            }
            const data = (await res.json());
            return data.choices?.[0]?.message?.content || '';
        }
        catch (e) {
            if (e?.name === 'AbortError') {
                lastErr = new Error(`LLM 超时（>${timeoutMs}ms）`);
            }
            else {
                lastErr = e instanceof Error ? e : new Error(String(e));
            }
            if (attempt < retries && /504|502|429|超时|fetch failed|ECONNRESET/i.test(lastErr.message)) {
                console.warn(`[hr-agent] LLM 异常，重试 ${attempt + 1}/${retries}:`, lastErr.message.slice(0, 120));
                await new Promise((r) => setTimeout(r, 800 * (attempt + 1)));
                continue;
            }
            throw lastErr;
        }
        finally {
            clearTimeout(timer);
        }
    }
    throw lastErr || new Error('LLM 调用失败');
}
async function chatOrMock(messages, mockFn, opts) {
    if (!(0, config_1.llmEnabled)()) {
        return { content: await mockFn(), provider: 'mock' };
    }
    try {
        const content = await chatCompletion(messages, opts);
        return { content, provider: 'llm' };
    }
    catch (e) {
        console.warn('[hr-agent] LLM 失败，降级 mock:', e.message);
        return { content: await mockFn(), provider: 'mock' };
    }
}
function safeJsonParse(text, fallback) {
    try {
        const cleaned = text.replace(/^```json\s*/i, '').replace(/^```\s*/i, '').replace(/\s*```$/, '');
        return JSON.parse(cleaned);
    }
    catch {
        return fallback;
    }
}
