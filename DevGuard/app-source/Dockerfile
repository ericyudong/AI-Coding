FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GUARDRAIL_POLICY_PATH=/etc/guardrails/policy.yaml

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/ /app/scripts/
COPY src/ /app/src/
COPY guardrails/policy.yaml /app/guardrails/policy.yaml
COPY prompts/ /app/prompts/

# Default baked-in policy; cluster ConfigMap overrides via volume mount.
RUN mkdir -p /etc/guardrails && cp /app/guardrails/policy.yaml /etc/guardrails/policy.yaml

EXPOSE 8080
USER nobody
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
