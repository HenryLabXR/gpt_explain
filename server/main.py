import os
import re
import traceback
from pathlib import Path

import httpx
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

try:
    from .prompts import (
        PROMPT_EXPLAIN_BASE,
        PROMPT_EXPLAIN_LONG,
        PROMPT_EXPLAIN_SHORT,
        PROMPT_TRANSLATE_TEMPLATE,
    )
except ImportError:
    from prompts import (
        PROMPT_EXPLAIN_BASE,
        PROMPT_EXPLAIN_LONG,
        PROMPT_EXPLAIN_SHORT,
        PROMPT_TRANSLATE_TEMPLATE,
    )

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


def build_short_explain_prompt() -> str:
    return PROMPT_EXPLAIN_BASE + PROMPT_EXPLAIN_SHORT


def build_long_explain_prompt() -> str:
    return PROMPT_EXPLAIN_BASE + PROMPT_EXPLAIN_LONG


def build_translate_prompt(target_lang: str) -> str:
    return PROMPT_TRANSLATE_TEMPLATE.format(target_lang=target_lang)


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
    filler_words = ["In summary", "It should be noted", "Worth mentioning", "As is known", "Especially", "Very"]
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
        system_prompt = build_long_explain_prompt() if input_category == "long_text_analysis" else build_short_explain_prompt()

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
