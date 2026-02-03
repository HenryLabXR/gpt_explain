# edge_gpt_explain

一个在浏览器中选中文本后，右键即可解释的本地 GPT 解释工具。前端是 Edge/Chrome 扩展，后端是本地 Flask 服务。

## 功能
- 选中文本右键解释


## 运行环境
- Windows 10/11
- Python 3.7+
- Edge 或 Chrome

## 快速开始
### 1. 启动后端服务
进入项目目录下的 `server`：
```powershell
cd .\edge_gpt_explain\server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

创建或编辑 `edge_gpt_explain/server/.env`：
```
OPENAI_API_KEY=你的Key
OPENAI_MODEL=gpt-4o-mini
PORT=8787
PROXY_TYPE=http
PROXY_PORT=15236
MAX_OUTPUT_TOKENS=8000
```

启动服务：
```powershell
python .\main.py
```
默认服务地址：`http://127.0.0.1:8787/explain`

### 2. 安装浏览器扩展
1. 打开 Edge，进入 `edge://extensions/`
2. 打开“开发者模式”
3. 点击“加载解压缩扩展”，选择 `edge_gpt_explain/extension`

### 3. 使用
1. 在网页中选中一段文本
2. 右键选择 `Ask GPT: what is "xxx"`
3. 右上角会出现解释窗口，等待加载完成后显示结果

## 使用建议
- 短文本：自动做术语解释
- 长文本：自动做分段解释（摘要 + 细节 + 总类比）

## 常见问题
### Missing API key
检查 `edge_gpt_explain/server/.env` 是否存在且包含 `OPENAI_API_KEY`。  
确保启动服务的目录是 `edge_gpt_explain/server`，或已正确配置 `.env` 路径。


## 项目结构
- `edge_gpt_explain/server`：本地服务端（Flask）
- `edge_gpt_explain/extension`：浏览器扩展（content script + service worker）

## 自定义
你可以在 `edge_gpt_explain/server/main.py` 中调整：
- 长文输出结构
- 类比风格
- 最大输出长度（`MAX_OUTPUT_TOKENS`）
