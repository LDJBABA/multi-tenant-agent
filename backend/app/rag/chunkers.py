"""
文本切分器

职责：把长文本切成小片段（Chunk），供后续 Embedding 使用
策略：按段落切分，合并过短的片段，拆分过长的片段
"""
import hashlib
from app.utils.common_utils import count_tokens
from app.rag.parsers import DocElement


# ========== 新增：结构化切分 ==========

def chunk_text_structured(
    elements: list[DocElement],
    max_tokens: int = 800,
    min_tokens: int = 100,
    overlap: int = 50,
) -> list[dict]:
    """
    结构化切分，保留标题层级、表格结构、话术对配对

    流程：
    1. 遍历元素，按 section 累积
    2. 遇到标题/表头时，保存当前 section 并开始新 section
    3. 话术对行强制独立 chunk
    4. 最后给所有 chunk 加 overlap
    """
    chunks = []
    current_section = {
        "title": None,
        "content": [],
        "token_count": 0,
        "metadata": {},
    }

    for elem in elements:
        

        if elem.type == "title":
            # 遇到新标题，保存当前 section
            if current_section["content"]:
                chunks.extend(flush_section(current_section, max_tokens, overlap))
            # 开始新 section
            current_section = {
                "title": elem.content,
                "content": [],
                "token_count": count_tokens(elem.content),
                "metadata": {},
            }

        
        elif elem.type == "table":
            # 整表作为独立 chunk
            if current_section["content"]:
                chunks.extend(flush_section(current_section, max_tokens, overlap))
                current_section = {"title": None, "content": [], "token_count": 0, "metadata": {}}
            chunks.append({
                "content": elem.content,
                "token_count": count_tokens(elem.content),
                "metadata": elem.metadata,
            })
       

        elif elem.type == "paragraph":
            # 过滤噪声
            if is_noise(elem.content):
                continue

            elem_tokens = count_tokens(elem.content)
            # 短段落累积
            if elem_tokens < min_tokens:
                current_section["content"].append(elem.content)
                current_section["token_count"] += elem_tokens
            else:
                # 长段落，先保存当前 section
                if current_section["content"]:
                    chunks.extend(flush_section(current_section, max_tokens, overlap))
                # 长段落单独处理
                chunks.extend(split_long_text(elem.content, max_tokens, overlap))
                current_section = {"title": None, "content": [], "token_count": 0, "metadata": {}}

    # 处理最后一个 section
    if current_section["content"]:
        chunks.extend(flush_section(current_section, max_tokens, overlap))

    # 给所有 chunk 加 overlap
    chunks = add_overlap_to_chunks(chunks, overlap)

    # 添加 chunk_index 和 content_hash
    for i, chunk in enumerate(chunks):
        chunk["chunk_index"] = i
        chunk["content_hash"] = hashlib.sha256(chunk["content"].encode()).hexdigest()[:16]

    return chunks


def flush_section(section: dict, max_tokens: int, overlap: int) -> list[dict]:
    """将 section 的内容切分成 chunks"""
    parts = []
    if section["title"]:
        parts.append(section["title"])
    parts.extend(section["content"])
    content = "\n".join(parts)

    if not content.strip():
        return []
    
    # 表格 section 不切分，整段返回
    if section.get("metadata", {}).get("table_id") is not None:
        return [{
            "content": content,
            "token_count": count_tokens(content),
            "metadata": section.get("metadata", {}),
        }]

    if count_tokens(content) <= max_tokens:
        return [{
            "content": content,
            "token_count": count_tokens(content),
            "metadata": section.get("metadata", {}),
        }]
    else:
        return split_long_text(content, max_tokens, overlap)


def is_noise(text: str) -> bool:
    """判断是否为噪声内容"""
    stripped = text.strip()
    if not stripped:
        return True
    if stripped in ["序号", "客户昵称", "备注", "日期", "签名", "内容"]:
        return True
    if len(stripped) < 2:
        return True
    return False


def add_overlap_to_chunks(chunks: list[dict], overlap: int = 50) -> list[dict]:
    """给所有 chunk 添加 overlap，消除边界断裂"""
    if len(chunks) <= 1 or overlap <= 0:
        return chunks

    result = []
    for i, chunk in enumerate(chunks):
        content = chunk["content"]

        # 从前一个 chunk 取末尾 overlap 个词
        if i > 0:
            prev_tokens = chunks[i - 1]["content"].split()
            overlap_text = " ".join(prev_tokens[-overlap:])
            content = f"[前文] {overlap_text}\n[当前文]{content}"

        # 从后一个 chunk 取开头 overlap 个词
        if i < len(chunks) - 1:
            next_tokens = chunks[i + 1]["content"].split()
            overlap_text = " ".join(next_tokens[:overlap])
            content = f"{content}\n[后文] {overlap_text}"

        result.append({
            **chunk,
            "content": content,
            "token_count": count_tokens(content),
        })

    return result


# ========== 保留：旧版切分（兼容） ==========


def chunk_text(
    text: str,
    max_tokens: int = 800,
    min_tokens: int = 100,
    overlap: int = 50,
) -> list[dict]:
    """
    将文本切分为多个片段

    参数：
        text: 原始文本
        max_tokens: 单个 chunk 最大 token 数
        min_tokens: 单个 chunk 最小 token 数（过短则合并）
        overlap: 相邻 chunk 的重叠 token 数（保持上下文连贯）

    返回：
        [{"content": "片段内容", "token_count": 123, "chunk_index": 0}, ...]
    """
    # 第一步：按段落拆分
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    # 第二步：合并过短的段落
    merged = merge_short_paragraphs(paragraphs, min_tokens)

    # 第三步：拆分过长的片段
    chunks = []
    for para in merged:
        if count_tokens(para) > max_tokens:
            chunks.extend(split_long_text(para, max_tokens, overlap))
        else:
            # 统一格式：字典
            chunks.append({"content": para, "token_count": count_tokens(para), "metadata": {}})

    # 第四步：构建结果，加上元信息
    result = []
    for i, chunk in enumerate(chunks):
        result.append({
            "content": chunk["content"],          # 从字典取值
            "token_count": chunk["token_count"],   # 从字典取值
            "chunk_index": i,
            "content_hash": hashlib.sha256(chunk["content"].encode()).hexdigest()[:16],
        })

    return result


def merge_short_paragraphs(paragraphs: list[str], min_tokens: int) -> list[str]:
    """合并过短的段落，避免碎片化"""
    merged = []
    current = ""

    for para in paragraphs:
        # 当前累积的文本 + 新段落
        candidate = f"{current}\n{para}".strip() if current else para

        if count_tokens(candidate) < min_tokens:
            # 还不够长，继续累积
            current = candidate
        else:
            # 够长了，保存并开始新的
            if current:
                merged.append(current)
            current = para

    # 最后一段
    if current:
        merged.append(current)

    return merged


def split_long_text(text: str, max_tokens: int, overlap: int) -> list[dict]:
    """拆分过长的文本，按句子边界切分"""
    sentences = []
    current = ""

    for char in text:
        current += char
        if char in "。！？.!?":
            sentences.append(current.strip())
            current = ""
    if current.strip():
        sentences.append(current.strip())

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        candidate = f"{current_chunk}{sentence}".strip() if current_chunk else sentence
        if count_tokens(candidate) <= max_tokens:
            current_chunk = candidate
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = sentence
    if current_chunk:
        chunks.append(current_chunk)

    # 返回字典列表，统一格式
    return [{"content": c, "token_count": count_tokens(c), "metadata": {}} for c in chunks]

