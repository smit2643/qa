"""Hierarchical context compression for accessibility trees and conversation history."""

MAX_CHARS = 12000  # safe for most models

KEEP_ROLES = {
    "button", "link", "textbox", "input", "combobox", "checkbox",
    "radio", "menuitem", "tab", "listitem", "heading", "form",
}


def compress_tree(tree_text: str, max_chars: int = MAX_CHARS) -> str:
    """
    If tree_text fits within max_chars, return it as-is.
    Otherwise keep only interactive/important elements and drop decorative ones.
    If still too long, truncate with a note.
    """
    if len(tree_text) <= max_chars:
        return tree_text

    lines = tree_text.split("\n")
    kept = []
    for line in lines:
        stripped = line.strip().lower()
        if any(stripped.startswith(role) for role in KEEP_ROLES):
            kept.append(line)
        elif ":" in stripped:
            role_part = stripped.split(":")[0].strip()
            if role_part in KEEP_ROLES:
                kept.append(line)

    result = "\n".join(kept)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n... [truncated for context limit]"
    return result


def compress_messages(messages: list[dict], max_total_chars: int = 40000) -> list[dict]:
    """
    If conversation history is too long, summarize older messages.
    Keeps the last 4 messages intact and compresses earlier ones.
    """
    total = sum(len(m.get("content", "")) for m in messages)
    if total <= max_total_chars:
        return messages

    if len(messages) <= 4:
        # Can't compress further — just return as-is
        return messages

    recent = messages[-4:]
    older = messages[:-4]
    summary_content = "Earlier conversation summary: " + " | ".join(
        f"{m['role']}: {m['content'][:200]}..." for m in older
    )
    return [
        {"role": "user", "content": summary_content},
        {"role": "assistant", "content": "Understood."},
    ] + recent
