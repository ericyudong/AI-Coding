import './loadEnv';

export const config = {
  port: Number(process.env.PORT || 3002),
  recruitosBaseUrl: (process.env.RECRUITOS_BASE_URL || 'http://127.0.0.1:3001').replace(/\/$/, ''),
  openaiApiKey: process.env.OPENAI_API_KEY || '',
  openaiBaseUrl: (process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1').replace(/\/$/, ''),
  openaiModel: process.env.OPENAI_MODEL || 'gpt-4o-mini',
};

export function llmEnabled() {
  return Boolean(config.openaiApiKey);
}
