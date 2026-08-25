# @deepseek-ai/dsh-recruit-agent

RecruitOS / HR Agent plugin for DeepSeek Harness.

## What it provides

- **Tools**: `recruitos_query`, `recruitos_search`, `recruitos_save_draft`, `recruitos_propose_action`, `hr_agent_invoke`
- **Skills**: `hr-recruitment`, `hr-jd`, `hr-resume`, `hr-interview`, `hr-offer`, `hr-analytics`

## Configuration

| Field | Default | Description |
|-------|---------|-------------|
| `recruitosBaseUrl` | `http://127.0.0.1:3001` | RecruitOS API |
| `hrAgentBaseUrl` | `http://127.0.0.1:3002` | HR Agent service |
| `authToken` | — | Bearer JWT; falls back to `RECRUITOS_JWT` or `RECRUITOS_TOKEN` |

## Example cordis.yml row

```yaml
- id: recruit-agent
  name: '@deepseek-ai/dsh-recruit-agent'
  config:
    recruitosBaseUrl: http://127.0.0.1:3001
    hrAgentBaseUrl: http://127.0.0.1:3002
```

## Known Limitations and Deferred Work

- Requires a running RecruitOS stack and valid user JWT; no embedded mock backend.
- HR Agent AI endpoints are proxied over HTTP; offline mock mode stays in the standalone `hr-agent` service.
