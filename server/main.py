import os
import re
import traceback

import httpx
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv()

# ============================================================================
# Prompt Optimization System - 成本优化与输出精简化系统
# ============================================================================

def normalize_user_input(raw_input: str) -> tuple:
    """
    输入规范化：去除冗余、提炼关键需求、压缩重复表述
    
    就像医生诊断前的问诊规范化 - 把杂乱的症状描述转化为关键信息
    """
    # 移除多余空白
    text = re.sub(r'\s+', ' ', raw_input).strip()
    
    # 根据输入长度判断：长文本解释，短文本介绍术语
    input_length = len(text)
    is_long_text = input_length >= 50
    
    # 检测并标记输入类型
    if any(keyword in text.lower() for keyword in ['代码', 'code', 'error', '错误', 'debug']):
        category = "code_debug"
    elif any(keyword in text.lower() for keyword in ['什么是', 'what is', '如何', 'how']):
        category = "concept_explanation"
    else:
        category = "long_text_analysis" if is_long_text else "term_definition"
    
    return text, category


def build_optimized_prompt(user_input: str, category: str) -> str:
    """
    构建经济高效的系统prompt
    
    类比：这就像给AI一个清晰的设计蓝图，而不是模糊的需求文档
    """
    
    base_system_prompt = """你是一个知识解答助手，致力于用最简洁有效的语言传达概念。

【回答格式要求】
- 严谨学术风格，不使用任何markdown格式符号（如**、*、#等）
- 必须使用换行分隔不同部分，每个部分独立成行
- 避免冗长铺垫，直接呈现答案
- 用必要的类比让抽象概念具象化

【禁止项】
- 不使用 ** 或任何markdown加粗标记
- 不使用 * 或 - 等列表符号作为项目符号
- 不使用 # 等标题符号
- 不使用填充性用语（如"综上所述"、"值得注意的是"）
- 不要逐字重复或原样复述用户提供的文本；只提取要点并进行解释或重构
- 回答长度应随输入长度增长：当用户输入为长段落时，允许更详尽的解释
"""
    
    if category == "code_debug":
        specific_prompt = """
    【代码问题处理】
    分析问题时：
    1. 诊断阶段 - 指出问题的根本原因（而非症状）
    2. 解决方案 - 给出修复代码及原因解释
    3. 预防建议 - 如何避免类似问题

    回答长度：150-250词（若用户提供更长的示例或日志，可适当延长）
    """
    elif category == "long_text_analysis":
        specific_prompt = """
    【长文本解释分析】
    用户提供了一段详细的文本，你需要：
    1. 提取核心含义 - 用一句话总结这段话的主要意思
    2. 技术细节解读 - 解释其中涉及的关键概念和机制
    3. 相关联系 - 说明与其他类似技术或概念的关系

    输出结构：
    核心含义解读（一句话概括，可包含类比）

    分段解释：针对长段落，按主题或逻辑分为多段，每段用1-3个段落句子详细说明，段落间用空行分隔

    关键技术点1：详细解释这个概念/机制
    关键技术点2：详细解释这个概念/机制
    关键技术点3：详细解释这个概念/机制

    与相关技术的比较或应用场景

    回答长度：通常200-300词；当输入为长段落时，按输入长度显著放宽输出（保留多段结构与充分解释），优先保证信息密度与可理解性
    """
    elif category == "term_definition":
        specific_prompt = """
【术语简洁介绍】
输出结构（必须严格遵守）：
核心定义（一句话，包含简洁的类比）
[换行]
关键特性1：不超过2句
关键特性2：不超过2句
关键特性3：不超过2句
[换行]
应用场景或例子

回答长度：80-150词
"""
    else:
        specific_prompt = """
    【通用回答指南】
    按信息密度和清晰性组织答案。
    使用换行分隔核心内容的不同部分。
    回答长度：80-150词（若用户输入为长段落，可适当延长以便充分解释）
    """
    
    return base_system_prompt + specific_prompt


def compress_explanation(text: str) -> str:
    """
    后处理：删除冗余表述，压缩最终回答
    """
    # 移除常见的填充词
    filler_words = ['综上所述', '需要注意的是', '值得一提的是', '众所周知', '尤其是', '非常']
    for word in filler_words:
        text = text.replace(word, '')
    # 规范换行：保留段落换行，但去除行首尾空格，合并连续空行为单个空行
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = [line.strip() for line in text.split('\n')]
    new_lines = []
    prev_empty = False
    for line in lines:
        if line == '':
            if not prev_empty:
                new_lines.append('')
            prev_empty = True
        else:
            new_lines.append(line)
            prev_empty = False

    text = '\n'.join(new_lines).strip()
    return text

# Optional: auto-apply local proxy for VPN if provided via env.
proxy_port = os.getenv("PROXY_PORT", "").strip()
proxy_type = os.getenv("PROXY_TYPE", "http").strip().lower()
if proxy_port and "HTTP_PROXY" not in os.environ and "HTTPS_PROXY" not in os.environ:
    proxy_url = f"{proxy_type}://127.0.0.1:{proxy_port}"
    os.environ["HTTP_PROXY"] = proxy_url
    os.environ["HTTPS_PROXY"] = proxy_url

app = Flask(__name__)
CORS(app, resources={r"/explain": {"origins": "*"}})

BASE_URL = os.getenv("BASE_URL", "https://api.vectorengine.ai").rstrip("/")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY")


@app.route("/explain", methods=["POST"])
def explain():
    try:
        data = request.get_json(silent=True) or {}
        selection = (data.get("text") or "").strip()
        user_prompt = (data.get("prompt") or "").strip()

        if not selection and not user_prompt:
            return jsonify(ok=False, error="Missing text"), 400

        if not user_prompt:
            user_prompt = f"请解释：{selection}"

        if not API_KEY:
            return jsonify(ok=False, error="Missing API key"), 400

        # 应用输入优化和Prompt构建
        normalized_input, input_category = normalize_user_input(user_prompt)
        system_prompt = build_optimized_prompt(normalized_input, input_category)

        url = f"{BASE_URL}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }
        # 根据用户输入长度动态调整允许的最大输出长度（token 估算）
        # 目标策略：输出长度与输入长度成比例，示例：100 字输入 -> 约 1000 token 输出
        # 计算方法：每个输入字符映射约 10 token，最少 100 token，最大上限 4000 token
        source_input = selection or user_prompt or normalized_input
        input_len = len(source_input)
        computed_max_tokens = min(4000, max(100, input_len * 10))

        payload = {
            "model": DEFAULT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": normalized_input}
            ],
            "temperature": 0.3,
            "max_tokens": computed_max_tokens,
            "stream": False,
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=headers, json=payload)

        if resp.status_code != 200:
            return jsonify(ok=False, error=f"Upstream error: {resp.text}"), 502

        response_data = resp.json()
        output_text = None
        try:
            output_text = response_data["choices"][0]["message"]["content"]
        except Exception:
            output_text = None

        if not output_text:
            return jsonify(ok=False, error="Empty response"), 502

        # 应用输出优化：压缩冗余表述
        optimized_output = compress_explanation(output_text)

        return jsonify(ok=True, text=optimized_output.strip())

    except Exception as exc:
        traceback.print_exc()
        return jsonify(ok=False, error=f"Server error: {exc}"), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8787"))
    app.run(host="127.0.0.1", port=port)
