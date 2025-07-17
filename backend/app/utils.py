from typing import List

def split_message(text: str, max_length: int = 2000) -> List[str]:
    if not text: return []
    parts = []
    while len(text) > 0:
        if len(text) <= max_length: parts.append(text); break
        cut_index = text.rfind('\n', 0, max_length)
        if cut_index == -1: cut_index = text.rfind(' ', 0, max_length)
        if cut_index == -1: cut_index = max_length
        parts.append(text[:cut_index].strip())
        text = text[cut_index:].strip()
    return parts