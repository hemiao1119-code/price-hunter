# 🔌 跨平台集成指南

本文档介绍如何在 OpenClaw、Cursor、Claude Desktop 等其他 AI Agent 平台使用 PriceHunter 比价 Skill。

---

## 📋 目录

1. [核心原理](#核心原理)
2. [OpenClaw 集成](#openclaw-集成)
3. [Cursor 集成](#cursor-集成)
4. [Claude Desktop (MCP)](#claude-desktop-mcp)
5. [其他 Agent 平台](#其他-agent-平台)
6. [API 直接调用](#api-直接调用)

---

## 核心原理

PriceHunter 本质上是**一组 Python 脚本**，通过命令行接口(CLI)提供服务：

```
用户请求 → Agent 解析 → 调用 Python 脚本 → 返回结构化数据 → 生成报告
```

只要目标 Agent 平台支持**执行本地命令**或**调用外部脚本**，就可以集成 PriceHunter。

---

## OpenClaw 集成

OpenClaw 与 WorkBuddy 架构相似，支持 Skill 机制。

### 安装步骤

```bash
# 1. 克隆仓库到 OpenClaw skills 目录
cd ~/.openclaw/skills
git clone https://github.com/hemiao1119-code/price-hunter.git

# 2. 安装依赖
cd price-hunter
pip install -r requirements.txt

# 3. 重启 OpenClaw
```

### 使用方式

在 OpenClaw 中直接对话：

```
用户：帮我比价大疆 Pocket 3
Agent：自动识别并调用 price-hunter skill
```

### 配置触发词

在 OpenClaw 的 skill 配置中添加触发词：

```yaml
triggers:
  - "帮我比价"
  - "找最低价"
  - "值不值得买"
  - "哪里买最划算"
  - "price compare"
```

---

## Cursor 集成

Cursor 支持通过 `.cursorrules` 文件配置自定义命令，或使用 Agent Mode 调用外部工具。

### 方案 A：自定义命令（推荐）

在 Cursor 项目根目录创建 `.cursorrules` 文件：

```markdown
# PriceHunter 比价工具配置

## 可用命令

当用户需要比价时，执行以下命令：

```bash
# 价格抓取
python3 /path/to/price-hunter/scripts/price_crawl.py --query "<商品名称>"

# 历史价格
python3 /path/to/price-hunter/scripts/price_history.py --query "<商品名称>"

# 口碑分析
python3 /path/to/price-hunter/scripts/review_summary.py --query "<商品名称>"
```

## 输出格式

将脚本返回的 JSON 数据整理为 Markdown 表格，包含：
- 各平台价格对比
- 历史价格走势
- 用户口碑摘要
- 最终购买建议
```

### 方案 B：Cursor Agent Mode

在 Cursor Chat 中使用 Agent Mode，直接告诉 AI：

```
请使用 /path/to/price-hunter/scripts/ 下的脚本帮我比价 iPhone 16，
先抓取各平台价格，再分析历史走势，最后汇总口碑，生成完整的比价报告。
```

### 方案 C：Cursor 插件（未来）

等待 Cursor 插件市场开放后，可开发官方插件。

---

## Claude Desktop (MCP)

Claude Desktop 通过 MCP (Model Context Protocol) 支持外部工具。

### 配置步骤

1. **安装 Claude Desktop**：https://claude.ai/download

2. **配置 MCP 服务器**：

编辑 `~/Library/Application Support/Claude/claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "price-hunter": {
      "command": "python3",
      "args": [
        "/path/to/price-hunter/mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "/path/to/price-hunter"
      }
    }
  }
}
```

3. **创建 MCP 适配器脚本**：

```python
#!/usr/bin/env python3
# mcp_server.py
import json
import sys
from scripts.price_crawl import crawl_prices
from scripts.price_history import get_price_history
from scripts.review_summary import summarize_reviews

def main():
    for line in sys.stdin:
        req = json.loads(line)
        tool = req.get("tool")
        params = req.get("params", {})
        
        if tool == "compare_prices":
            result = crawl_prices(params["query"])
        elif tool == "price_history":
            result = get_price_history(params["query"])
        elif tool == "review_summary":
            result = summarize_reviews(params["query"])
        else:
            result = {"error": "Unknown tool"}
        
        print(json.dumps({"result": result}))
        sys.stdout.flush()

if __name__ == "__main__":
    main()
```

4. **重启 Claude Desktop**，工具将自动加载

### 使用方式

在 Claude Desktop 中直接对话：

```
用户：帮我比价 MacBook Pro M4
Claude：调用 price-hunter.compare_prices 工具...
```

---

## 其他 Agent 平台

### 通用集成模式

任何支持以下能力的 Agent 平台都可以集成：

| 能力 | 实现方式 |
|------|---------|
| 执行本地命令 | 直接调用 `python3 scripts/xxx.py` |
| HTTP API 调用 | 启动 Flask/FastAPI 服务作为中转 |
| 插件系统 | 开发对应平台的插件包装器 |
| Function Calling | 将脚本封装为函数工具 |

### 平台适配示例

#### Dify / FastGPT / LangChain

```python
from langchain.tools import BaseTool

class PriceHunterTool(BaseTool):
    name = "price_hunter"
    description = "比价购物助手，支持淘宝/京东/拼多多/抖音/小红书"
    
    def _run(self, query: str):
        import subprocess
        result = subprocess.run(
            ["python3", "/path/to/price-hunter/scripts/price_crawl.py", 
             "--query", query],
            capture_output=True, text=True
        )
        return result.stdout
```

#### Coze / 扣子

使用「代码节点」调用外部 API：

```python
import requests

def main(args):
    # 调用部署在云端的 PriceHunter API
    resp = requests.post("https://your-api.com/price-crawl", 
                        json={"query": args["product"]})
    return resp.json()
```

---

## API 直接调用

如果你想把 PriceHunter 部署为独立服务，可以通过以下方式：

### 方式 1：Flask HTTP API

```python
# api_server.py
from flask import Flask, request, jsonify
from scripts.price_crawl import crawl_prices

app = Flask(__name__)

@app.route('/api/compare', methods=['POST'])
def compare():
    query = request.json.get('query')
    result = crawl_prices(query)
    return jsonify(result)

if __name__ == '__main__':
    app.run(port=5000)
```

启动后，任何 Agent 都可以通过 HTTP 调用：

```bash
curl -X POST http://localhost:5000/api/compare \
  -H "Content-Type: application/json" \
  -d '{"query": "iPhone 16"}'
```

### 方式 2：Docker 部署

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 5000
CMD ["python", "api_server.py"]
```

```bash
docker build -t price-hunter .
docker run -p 5000:5000 price-hunter
```

---

## 🔧 配置说明

### 环境变量

| 变量名 | 说明 | 必需 |
|--------|------|------|
| `JD_API_KEY` | 京东联盟 API Key | 否 |
| `TB_API_KEY` | 淘宝联盟 API Key | 否 |
| `OPENAI_API_KEY` | OpenAI API Key（用于口碑分析） | 否 |
| `DASHSCOPE_API_KEY` | 通义千问 API Key（国产替代） | 否 |

### 依赖安装

```bash
pip install requests beautifulsoup4 playwright pandas matplotlib

# 安装 Playwright 浏览器
playwright install chromium
```

---

## 📚 示例：完整调用流程

以 Python 直接调用为例：

```python
import subprocess
import json

def price_compare(product_name):
    # Step 1: 抓取价格
    result = subprocess.run(
        ["python3", "scripts/price_crawl.py", "--query", product_name],
        capture_output=True, text=True
    )
    prices = json.loads(result.stdout)
    
    # Step 2: 获取历史价格
    result = subprocess.run(
        ["python3", "scripts/price_history.py", "--query", product_name],
        capture_output=True, text=True
    )
    history = json.loads(result.stdout)
    
    # Step 3: 口碑分析
    result = subprocess.run(
        ["python3", "scripts/review_summary.py", "--query", product_name],
        capture_output=True, text=True
    )
    reviews = json.loads(result.stdout)
    
    # Step 4: 生成报告（用 LLM 或模板）
    report = generate_report(prices, history, reviews)
    return report

# 使用
report = price_compare("大疆 Pocket 3")
print(report)
```

---

## 🤝 贡献与支持

- 发现适配问题？请提交 [Issue](https://github.com/hemiao1119-code/price-hunter/issues)
- 有新平台适配方案？欢迎 [PR](https://github.com/hemiao1119-code/price-hunter/pulls)

---

## 📄 许可证

MIT License - 可自由集成到商业或非商业项目。
