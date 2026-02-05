import os
import re
import traceback
from pathlib import Path

import httpx
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

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
    is_long_text = input_length >= 10
    
    # 检测并标记输入类型
    if is_long_text:
        category = "long_text_analysis"
    else:
        category = "term_definition"
    
    return text, category


def build_optimized_prompt(user_input: str, category: str) -> str:
    """
    构建经济高效的系统prompt
    
    类比：这就像给AI一个清晰的设计蓝图，而不是模糊的需求文档
    """
    
    base_system_prompt = """你是一个知识解答助手，致力于用最简洁有效的语言传达概念。

【回答格式要求】
- 持【中文回答】
- 严谨学术风格，不使用任何markdown格式符号（如**、*、#等）
- 表达自然流畅，避免每句强制换行，不要产生多余空行
- 避免冗长铺垫，直接呈现答案
- 【重要】用必要的类比让抽象概念具象化

【禁止项】
- 不使用 ** 或任何markdown加粗标记
- 不使用 * 或 - 等列表符号作为项目符号
- 不使用 # 等标题符号
- 不使用填充性用语（如"综上所述"、"值得注意的是"）
- 不要逐字重复或原样复述用户提供的文本；只提取要点并进行解释或重构
- 回答长度应随输入长度增长：当用户输入为长段落时，允许更详尽的解释
- 
"""
    
    if category == "long_text_analysis":
        specific_prompt = """
    【长文本解释分析 - 帮助理解为首要目标】
    用户提供了一段详细的文本，你的任务是让他完全理解这段话

    具体步骤：
    1. 单句提炼 - 用一句话说清"这段话的灵魂是什么"，包含一个日常类比，让人瞬间get
    2. 拆解核心机制 - 一句话概括后，拆解1-3个关键概念，每个用2-3句通俗话+生活例子解释（避免专业术语堆砌）
    3. 应用与场景 - 这个概念/机制在什么场景下用，有什么实际意义，如何与其他概念关联
    4.【重要】 整体印象比喻 - 用1个综合性的类比或比喻，让读者形成深刻的整体理解、帮助记忆

    输出格式：
    2-4个段落，各段自然连贯，不要在段落间插入多余空行。同一段落内的句子用逗号或句号自然连接，不要每句分行。
    - 第1段（核心理解）：1句灵魂总结+类比，用最简洁的方式tell the big picture
    - 第2-3段（拆解与深化）：逐个拆解关键概念，每个2-3句+1个类比或例子；解释为什么和怎么用
    - 最后1段（收束）：1个综合类比或对照，帮读者形成完整映像

    语言技巧：
    - 多用"就像"、"好比"、"类似于"等类比词引出生活例子
    - 用反问句或对比来加深理解（"你可能想，为什么不...？原因是..."）
    - 避免罗列，强调逻辑关系（"因此"、"这样才能"、"结果是"）
    - 每个抽象概念后立刻跟一个具体例子或数字，增强代入感

    关键：段落间不要插入空行，保持文本紧凑连贯。整体字数通常150-300词；长段落时可放宽到200-500词。
    """
    elif category == "term_definition":
        specific_prompt = """
【术语简洁介绍】
输出结构（必须严格遵守）：
核心定义（一句话，包含简洁的类比）
[换行]
比喻或类比解释：用一个生活中的例子或场景来说明这个术语的含义
[换行]
应用场景或例子
[换行]
关键特性1：不超过2句
关键特性2：不超过2句
关键特性3：不超过2句
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


def build_translate_prompt(target_lang: str) -> str:
    return f"""
你是一个专业翻译与术语解释助手，请将用户输入内容翻译为{target_lang}。

要求：
1. 保持原意准确，不随意扩展。
2. 如涉及专业术语，给出规范译法。
3. 如涉及计算机/工程含义，请补充说明。
4. 表达简洁严谨。

禁止使用markdown格式。
"""

def compress_explanation(text: str) -> str:
    """
    后处理：删除冗余表述，保留清晰段落结构但减少过多空行
    """
    # 移除常见的填充词
    filler_words = [
    "综上所述",
    "值得注意的是",
    "需要指出的是",
    "可以看出",
    "总体来看"
    ]
    for word in filler_words:
        text = text.replace(word, '')
    
    # 规范换行
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # 按行拆分
    lines = []
    for line in text.split('\n'):
        cleaned = line.strip()
        # 过滤掉"selected"等前缀信息
        

        if re.match(r'^(selected|selection)\s*[:?]', cleaned, re.IGNORECASE):
            continue
        lines.append(cleaned)

    # 重建段落：连续非空行合并成一段，只在原有段落间保留单个空行
    paragraphs = []
    current = []
    for line in lines:
        if line == '':
            if current:
                para_text = ' '.join(current).strip()
                if para_text:
                    paragraphs.append(para_text)
                current = []
        else:
            current.append(line)
    
    if current:
        para_text = ' '.join(current).strip()
        if para_text:
            paragraphs.append(para_text)

    # 用单换行分隔段落，减少过多空白
    text = '\n'.join(paragraphs)
    return text.strip()

def compress_translation(text: str) -> str:
    """
    Preserve line structure while removing filler words and extra blank lines.
    """

    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = []
    for line in text.split('\n'):
        cleaned = line.strip()
        if re.match(r'^(selected|selection)\s*[:?]', cleaned, re.IGNORECASE):
            continue
        lines.append(cleaned)

    # collapse multiple blank lines
    compact = []
    prev_blank = False
    for line in lines:
        is_blank = line == ''
        if is_blank and prev_blank:
            continue
        compact.append(line)
        prev_blank = is_blank

    return '\n'.join(compact).strip()

# Optional: auto-apply local proxy for VPN if provided via env.
proxy_port = os.getenv("PROXY_PORT", "").strip()
proxy_type = os.getenv("PROXY_TYPE", "http").strip().lower()
if proxy_port and "HTTP_PROXY" not in os.environ and "HTTPS_PROXY" not in os.environ:
    proxy_url = f"{proxy_type}://127.0.0.1:{proxy_port}"
    os.environ["HTTP_PROXY"] = proxy_url
    os.environ["HTTPS_PROXY"] = proxy_url

app = Flask(__name__)
CORS(app, resources={r"/explain": {"origins": "*"}, r"/translate": {"origins": "*"}})

BASE_URL = os.getenv("BASE_URL", "https://api.vectorengine.ai").rstrip("/")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY")
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "8000"))
TRANSLATE_TARGET_LANG = os.getenv("TRANSLATE_TARGET_LANG", "中文")


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
        
        #computed_max_tokens = min(MAX_OUTPUT_TOKENS, max(200, input_len * 12))
        if input_category == "long_text_analysis":
            computed_max_tokens = 1200  # 稳定值
        else:
            computed_max_tokens = 500

        payload = {
            "model": DEFAULT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": normalized_input}
            ],
            "temperature": 0.4 if input_category == "long_text_analysis" else 0.3,
            "max_tokens": computed_max_tokens,
            "stream": False,
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=headers, json=payload)

        if resp.status_code != 200:
            return jsonify(ok=False, error=f"Upstream error: {resp.text}"), 502

        response_data = resp.json()
        output_text = None
        finish_reason = None
        try:
            output_text = response_data["choices"][0]["message"]["content"]
            finish_reason = response_data["choices"][0].get("finish_reason")
        except Exception:
            output_text = None

        if not output_text:
            return jsonify(ok=False, error="Empty response"), 502

        # 应用输出优化：压缩冗余表述
        optimized_output = compress_explanation(output_text)

        return jsonify(ok=True, text=optimized_output.strip(), finish_reason=finish_reason)

    except Exception as exc:
        traceback.print_exc()
        return jsonify(ok=False, error=f"Server error: {exc}"), 500


@app.route("/translate", methods=["POST"])
def translate():
    try:
        data = request.get_json(silent=True) or {}
        text = (data.get("text") or "").strip()
        user_prompt = (data.get("prompt") or "").strip()

        if not text and not user_prompt:
            return jsonify(ok=False, error="Missing text"), 400

        if not text:
            text = user_prompt

        if not API_KEY:
            return jsonify(ok=False, error="Missing API key"), 400

        system_prompt = build_translate_prompt(TRANSLATE_TARGET_LANG)

        url = f"{BASE_URL}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": DEFAULT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "temperature": 0.3,
            "max_tokens": 600,
            "stream": False,
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=headers, json=payload)

        if resp.status_code != 200:
            return jsonify(ok=False, error=f"Upstream error: {resp.text}"), 502

        response_data = resp.json()
        output_text = None
        finish_reason = None
        try:
            output_text = response_data["choices"][0]["message"]["content"]
            finish_reason = response_data["choices"][0].get("finish_reason")
        except Exception:
            output_text = None

        if not output_text:
            return jsonify(ok=False, error="Empty response"), 502

        optimized_output = compress_translation(output_text)

        return jsonify(ok=True, text=optimized_output.strip(), finish_reason=finish_reason)

    except Exception as exc:
        traceback.print_exc()
        return jsonify(ok=False, error=f"Server error: {exc}"), 500


if __name__ == "__main__":
    print("API_KEY:", os.getenv("OPENAI_API_KEY"))
    port = int(os.getenv("PORT", "8787"))
    app.run(host="127.0.0.1", port=port)