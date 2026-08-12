import { config, llmEnabled } from './config';

export type ChatMessage = { role: 'system' | 'user' | 'assistant'; content: string };

function llmTimeoutMs() {
  return Number(process.env.LLM_TIMEOUT_MS || 90000);
}

/** OpenAI-compatible chat；无 API Key 时由调用方走 mock 路径 */
export async function chatCompletion(
  messages: ChatMessage[],
  opts?: { temperature?: number; json?: boolean; maxTokens?: number; retries?: number }
): Promise<string> {
  if (!llmEnabled()) {
    throw new Error('LLM_DISABLED');
  }
  const timeoutMs = llmTimeoutMs();
  const retries = opts?.retries ?? 2;
  let lastErr: Error | null = null;

  for (let attempt = 0; attempt <= retries; attempt++) {
    const body: Record<string, unknown> = {
      model: config.openaiModel,
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
      const res = await fetch(`${config.openaiBaseUrl}/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${config.openaiApiKey}`,
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
      const data = (await res.json()) as any;
      return data.choices?.[0]?.message?.content || '';
    } catch (e: any) {
      if (e?.name === 'AbortError') {
        lastErr = new Error(`LLM 超时（>${timeoutMs}ms）`);
      } else {
        lastErr = e instanceof Error ? e : new Error(String(e));
      }
      if (attempt < retries && /504|502|429|超时|fetch failed|ECONNRESET/i.test(lastErr.message)) {
        console.warn(`[hr-agent] LLM 异常，重试 ${attempt + 1}/${retries}:`, lastErr.message.slice(0, 120));
        await new Promise((r) => setTimeout(r, 800 * (attempt + 1)));
        continue;
      }
      throw lastErr;
    } finally {
      clearTimeout(timer);
    }
  }
  throw lastErr || new Error('LLM 调用失败');
}

export async function chatOrMock(
  messages: ChatMessage[],
  mockFn: () => string | Promise<string>,
  opts?: { temperature?: number; json?: boolean; maxTokens?: number; retries?: number }
): Promise<{ content: string; provider: 'llm' | 'mock' }> {
  if (!llmEnabled()) {
    return { content: await mockFn(), provider: 'mock' };
  }
  try {
    const content = await chatCompletion(messages, opts);
    return { content, provider: 'llm' };
  } catch (e) {
    console.warn('[hr-agent] LLM 失败，降级 mock:', (e as Error).message);
    return { content: await mockFn(), provider: 'mock' };
  }
}

export function safeJsonParse<T = any>(text: string, fallback: T): T {
  try {
    const cleaned = text.replace(/^```json\s*/i, '').replace(/^```\s*/i, '').replace(/\s*```$/, '');
    return JSON.parse(cleaned) as T;
  } catch {
    return fallback;
  }
}
