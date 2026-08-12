"""Async contract import queue runner."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.database import SessionLocal
from app.models.cms_models import ContractImportTask
from app.services import audit_service

logger = logging.getLogger(__name__)


async def run_import_job(task_id: int, *, retry: bool = False) -> None:
    """Background job: parse + extract fields, update task progress."""
    async with SessionLocal() as db:
        task = await db.get(ContractImportTask, task_id)
        if not task:
            return
        if retry:
            task.status = "processing"
            task.progress = 5
            task.parse_warnings_json = "[]"
            await db.commit()

        try:
            task.status = "processing"
            task.progress = 10
            await db.commit()

            from app.services.document_parser import parse_file
            from app.services.field_extractor import extract_fields_with_llm

            if not Path(task.file_path).exists():
                task.status = "failed"
                task.progress = 100
                task.parse_warnings_json = json.dumps(["文件不存在，无法解析"], ensure_ascii=False)
                await db.commit()
                return

            task.progress = 30
            await db.commit()

            parsed = parse_file(task.file_path)
            task.progress = 60
            task.content_text = parsed.text or ""
            warnings = list(parsed.warnings)
            await db.commit()

            fields = await extract_fields_with_llm(parsed.text, task.filename or "unknown")
            if fields.pop("_rule_only", None):
                warnings.append("AI 字段抽取暂不可用，已使用规则引擎提取，请人工校对")

            # Low OCR confidence heuristic
            if parsed.char_count < 50 and any("OCR" in w or "扫描" in w for w in warnings):
                warnings.append("需人工复核：OCR 识别文字过少")

            confidence = 85 if parsed.char_count > 100 else 40
            if warnings:
                confidence = max(30, confidence - 8 * min(len(warnings), 5))

            from app.services.cms_service import _generate_code

            task.status = "completed"
            task.progress = 100
            task.confidence = confidence
            task.parse_warnings_json = json.dumps(warnings, ensure_ascii=False)
            task.extracted_json = json.dumps({**fields, "code": _generate_code()}, ensure_ascii=False)
            # retry_count tracked via model field if present
            if hasattr(task, "retry_count") and retry:
                task.retry_count = (task.retry_count or 0) + 1
            await db.commit()

            await audit_service.track_event(
                db,
                event_name="ocr_complete",
                user_id=task.user_id,
                props={"task_id": task.id, "filename": task.filename, "success": True, "chars": parsed.char_count},
            )
        except Exception as exc:
            logger.exception("Import job %s failed: %s", task_id, exc)
            task = await db.get(ContractImportTask, task_id)
            if not task:
                return
            # Auto-retry once
            retries = getattr(task, "retry_count", 0) or 0
            if not retry and retries < 1:
                if hasattr(task, "retry_count"):
                    task.retry_count = retries + 1
                task.status = "processing"
                task.progress = 5
                await db.commit()
                await run_import_job(task_id, retry=True)
                return
            task.status = "failed"
            task.progress = 100
            warns = []
            try:
                warns = json.loads(task.parse_warnings_json or "[]")
            except Exception:
                pass
            warns.append(f"解析失败: {exc}")
            task.parse_warnings_json = json.dumps(warns, ensure_ascii=False)
            await db.commit()
            await audit_service.track_event(
                db,
                event_name="ocr_complete",
                user_id=task.user_id,
                props={"task_id": task.id, "filename": task.filename, "success": False, "error": str(exc)},
            )
