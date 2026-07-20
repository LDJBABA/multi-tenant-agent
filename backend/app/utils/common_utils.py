import tiktoken

def count_tokens(text: str) -> int:
    """计算文本的 token 数，使用和百炼/OpenAI 一致的编码器"""
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))