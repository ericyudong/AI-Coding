"""Contract version diff."""
import difflib
import re
from dataclasses import dataclass


@dataclass
class DiffChange:
    change_type: str  # added | removed | modified
    section: str
    left_text: str
    right_text: str
    detail: str = ""


_SNIPPET_LIMIT = 800
_MAX_CHANGES = 40

_CLAUSE_SPLIT = re.compile(
    r"(?=第[一二三四五六七八九十百零\d]+条)",
    re.MULTILINE,
)


def _split_clauses(text: str) -> list[tuple[str, str]]:
    text = text.strip()
    if not text:
        return []
    parts = _CLAUSE_SPLIT.split(text)
    clauses: list[tuple[str, str]] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = re.match(r"(第[一二三四五六七八九十百零\d]+条[^\n]*)", part)
        title = m.group(1).strip() if m else f"段落{len(clauses) + 1}"
        clauses.append((title, part))
    if not clauses and text:
        return [("全文", text)]
    return clauses


def _is_structured_clauses(clauses: list[tuple[str, str]]) -> bool:
    if not clauses:
        return False
    structured = sum(1 for title, _ in clauses if title.startswith("第") and "条" in title)
    return structured >= max(1, len(clauses) // 2)


def _clause_title_overlap(left_clauses: list[tuple[str, str]], right_clauses: list[tuple[str, str]]) -> float:
    left_titles = {t for t, _ in left_clauses}
    right_titles = {t for t, _ in right_clauses}
    if not left_titles or not right_titles:
        return 0.0
    shared = len(left_titles & right_titles)
    return shared / max(len(left_titles), len(right_titles))


def _truncate(text: str, limit: int = _SNIPPET_LIMIT) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _join_lines(lines: list[str]) -> str:
    return "\n".join(line.strip() for line in lines if line.strip())


def _build_change_detail(left: str, right: str) -> str:
    left_lines = left.splitlines()
    right_lines = right.splitlines()
    sm = difflib.SequenceMatcher(None, left_lines, right_lines)
    parts: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            old = _join_lines(left_lines[i1:i2])
            new = _join_lines(right_lines[j1:j2])
            if old and new:
                parts.append(f"「{old}」→「{new}」")
            elif old:
                parts.append(f"删除：{old}")
            elif new:
                parts.append(f"新增：{new}")
        elif tag == "delete":
            old = _join_lines(left_lines[i1:i2])
            if old:
                parts.append(f"删除：{old}")
        elif tag == "insert":
            new = _join_lines(right_lines[j1:j2])
            if new:
                parts.append(f"新增：{new}")
    return "；".join(parts[:10]) if parts else ""


def _focused_diff_snippets(left: str, right: str) -> tuple[str, str]:
    """长文本变更时仅展示有差异的行，便于快速定位修改点。"""
    left_lines = left.splitlines()
    right_lines = right.splitlines()
    sm = difflib.SequenceMatcher(None, left_lines, right_lines)
    left_parts: list[str] = []
    right_parts: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag in ("replace", "delete"):
            for line in left_lines[i1:i2]:
                if line.strip():
                    left_parts.append(line.rstrip())
        if tag in ("replace", "insert"):
            for line in right_lines[j1:j2]:
                if line.strip():
                    right_parts.append(line.rstrip())
    if left_parts or right_parts:
        return "\n".join(left_parts) or "[无]", "\n".join(right_parts) or "[无]"
    return left, right


def _make_modified_change(section: str, left: str, right: str) -> DiffChange:
    detail = _build_change_detail(left, right)
    display_left, display_right = left, right
    if max(len(left), len(right)) > 120 and detail:
        display_left, display_right = _focused_diff_snippets(left, right)
    return DiffChange(
        "modified",
        section,
        _truncate(display_left),
        _truncate(display_right),
        detail=detail,
    )


def _line_diff_changes(left: str, right: str) -> list[DiffChange]:
    left_lines = left.splitlines()
    right_lines = right.splitlines()
    if not left_lines and not right_lines:
        return []

    changes: list[DiffChange] = []
    sm = difflib.SequenceMatcher(None, left_lines, right_lines)
    block_idx = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        block_idx += 1
        left_snip = "\n".join(left_lines[i1:i2]).strip()
        right_snip = "\n".join(right_lines[j1:j2]).strip()
        ctype = {"insert": "added", "delete": "removed", "replace": "modified"}.get(tag, "modified")
        if tag == "insert":
            left_snip = left_snip or "[无]"
            right_snip = right_snip or "[无]"
        elif tag == "delete":
            left_snip = left_snip or "[无]"
            right_snip = right_snip or "[已删除]"
        detail = _build_change_detail(left_snip, right_snip) if ctype == "modified" else ""
        disp_left, disp_right = left_snip, right_snip
        if ctype == "modified" and max(len(left_snip), len(right_snip)) > 120 and detail:
            disp_left, disp_right = _focused_diff_snippets(left_snip, right_snip)
        changes.append(
            DiffChange(
                ctype,
                f"差异片段 {block_idx}",
                _truncate(disp_left),
                _truncate(disp_right),
                detail=detail,
            )
        )
        if len(changes) >= _MAX_CHANGES:
            break
    return changes


def _clause_diff_changes(left: str, right: str) -> list[DiffChange]:
    left_clauses = _split_clauses(left)
    right_clauses = _split_clauses(right)
    left_map = {t: c for t, c in left_clauses}
    right_map = {t: c for t, c in right_clauses}
    all_titles = list(dict.fromkeys([t for t, _ in left_clauses] + [t for t, _ in right_clauses]))

    changes: list[DiffChange] = []
    for title in all_titles:
        l = left_map.get(title, "")
        r = right_map.get(title, "")
        if l and not r:
            changes.append(
                DiffChange("removed", title, _truncate(l), "[已删除]", detail=f"删除：{_truncate(l, 200)}")
            )
        elif r and not l:
            changes.append(
                DiffChange("added", title, "[新增]", _truncate(r), detail=f"新增：{_truncate(r, 200)}")
            )
        elif l != r:
            sm = difflib.SequenceMatcher(None, l.splitlines(), r.splitlines())
            if sm.ratio() < 0.99:
                changes.append(_make_modified_change(title, l, r))
        if len(changes) >= _MAX_CHANGES:
            break
    return changes


def diff_contract_versions(left: str, right: str) -> list[DiffChange]:
    left = left or ""
    right = right or ""
    if left.strip() == right.strip():
        return []

    left_clauses = _split_clauses(left)
    right_clauses = _split_clauses(right)
    left_structured = _is_structured_clauses(left_clauses)
    right_structured = _is_structured_clauses(right_clauses)
    if left_structured and right_structured:
        overlap = _clause_title_overlap(left_clauses, right_clauses)
        # 条款标题几乎对不上时（如摘要版 vs 全文），改按行 diff，避免固定出现「3删+8增」
        if overlap >= 0.25:
            changes = _clause_diff_changes(left, right)
            if changes:
                return changes
    elif left_structured or right_structured:
        shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
        if len(shorter.strip()) < max(200, len(longer.strip()) * 0.35):
            return _line_diff_changes(left, right)

    return _line_diff_changes(left, right)


def summarize_diff_stats(changes: list[DiffChange]) -> dict:
    added = sum(1 for c in changes if c.change_type == "added")
    removed = sum(1 for c in changes if c.change_type == "removed")
    modified = sum(1 for c in changes if c.change_type in ("modified", "replace"))
    return {
        "total": len(changes),
        "added": added,
        "removed": removed,
        "modified": modified,
        "risk": min(modified + removed, len(changes)),
    }
