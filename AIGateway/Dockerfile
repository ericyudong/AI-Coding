FROM docker.litellm.ai/berriai/litellm:main-latest

WORKDIR /app

# 策略与自定义护栏（挂载到 PYTHONPATH 可被 LiteLLM 加载）
COPY guardrails/ /app/guardrails/
COPY custom_guardrail.py /app/custom_guardrail.py
COPY custom_callbacks.py /app/custom_callbacks.py
COPY config/ /app/config/

# 官方镜像通常已含 PyYAML；用 python -m pip 兼容无 pip 可执行文件的情况
RUN python -m pip install --no-cache-dir pyyaml jsonschema || true

ENV GUARDRAIL_POLICY_PATH=/app/guardrails/policy.yaml
ENV AUDIT_LOG_PATH=/var/log/ai-gateway/audit.jsonl
ENV PYTHONPATH=/app

EXPOSE 4000

CMD ["--config", "/app/config/config.yaml", "--port", "4000"]
