# 🛒 PriceHunter - 智能比价购物助手

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-WorkBuddy%20Skill-orange.svg)](https://github.com/features/copilot)

> 跨平台智能比价 Agent，覆盖淘宝/天猫、京东、拼多多、抖音、小红书五大电商平台，帮你找到最低价，避开智商税。

[English](./README_EN.md) | 简体中文

---

## ✨ 核心功能

| 功能 | 描述 |
|------|------|
| 🔍 **多平台比价** | 一键查询五大电商平台实时价格 |
| 📈 **历史价格** | 90天价格走势，识别虚假促销 |
| 💬 **口碑分析** | LLM 智能分析用户评价，生成买/不买建议 |
| 🤖 **AI 决策** | 结合价格+口碑，给出明确的购买建议 |
| 💰 **联盟佣金** | 支持淘宝/京东联盟 API，合规赚取佣金 |

---

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/price-hunter.git
cd price-hunter

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright（可选，用于抖音/淘宝抓取）
pip install playwright
playwright install chromium
```

### 基础使用

```bash
# 比价查询
python scripts/price_crawl.py --query "iPhone 16 Pro"

# 查看历史价格
python scripts/price_history.py --query "iPhone 16 Pro"

# 口碑分析
python scripts/review_summary.py --query "iPhone 16 Pro"
```

### 作为 WorkBuddy Skill 使用

1. 将本仓库克隆到 `~/.workbuddy/skills/price-hunter`
2. 在 WorkBuddy 中说出："帮我比价 iPhone 16 Pro"
3. 获取完整比价报告

### 在其他 AI Agent 平台使用

PriceHunter 支持多种 AI Agent 平台集成：

| 平台 | 集成方式 | 文档 |
|------|---------|------|
| **OpenClaw** | Skill 克隆安装 | [查看详情](INTEGRATION.md#openclaw-集成) |
| **Cursor** | `.cursorrules` 配置 | [查看详情](INTEGRATION.md#cursor-集成) |
| **Claude Desktop** | MCP 协议 | [查看详情](INTEGRATION.md#claude-desktop-mcp) |
| **Dify/FastGPT** | HTTP API / 代码节点 | [查看详情](INTEGRATION.md#其他-agent-平台) |
| **Coze/扣子** | 插件/API 调用 | [查看详情](INTEGRATION.md#其他-agent-平台) |

👉 [完整跨平台集成指南](INTEGRATION.md)

---

## 📊 效果展示

### 比价报告示例

```markdown
# 🛒 比价报告：大疆 Pocket 3

## 📊 价格对比

| 平台 | 当前价 | 促销信息 |
|------|--------|----------|
| 京东 | ¥2,799 | 百亿补贴 |
| 淘宝 | ¥2,899 | 官方直营 |
| 拼多多 | ¥2,699 | 百亿补贴 |
| 抖音 | ¥2,799 | 直播间专属 |

## 📈 历史价格

- **历史最低价**：¥2,599（2024-11-11）
- **当前价格**：¥2,699
- **近30天趋势**：↓ 下跌 5%
- **买入建议**：✅ 现在买（接近历史低价）

## 💬 用户口碑

- **综合评分**：4.6/5
- **好评关键词**：画质清晰、便携、防抖出色
- **差评关键词**：续航一般、配件贵

## ✅ 最终建议

> **买** — 当前价格接近历史低价，拼多多百亿补贴最划算。
> 建议购买标准版，配件可后期按需添置。
```

---

## 🏗️ 技术架构

```
price-hunter/
├── scripts/
│   ├── price_crawl.py      # 多平台价格抓取
│   ├── price_history.py    # 历史价格查询
│   ├── review_summary.py   # 口碑分析（LLM）
│   └── affiliate_api.py    # 联盟 API 接口
├── references/
│   └── platforms.md        # 平台接入文档
├── assets/                 # 静态资源
├── README.md
├── requirements.txt
└── LICENSE
```

### 技术栈

- **Python 3.8+** - 核心开发语言
- **Playwright** - 无头浏览器抓取
- **LLM API** - OpenAI / 通义千问 / Ollama 情感分析
- **淘宝/京东联盟 API** - 合规数据获取

---

## 🔧 高级配置

### 配置联盟 API（可选，用于合规抓取+赚佣金）

```bash
# 淘宝联盟
export TAOBAO_APP_KEY="your_app_key"
export TAOBAO_APP_SECRET="your_app_secret"
export TAOBAO_PID="mm_xxx_xxx_xxx"

# 京东联盟
export JD_APP_KEY="your_app_key"
export JD_APP_SECRET="your_app_secret"
export JD_SITE_ID="your_site_id"
```

### 配置 LLM（用于口碑情感分析）

```bash
# 三选一
export OPENAI_API_KEY="sk-..."           # OpenAI
export DASHSCOPE_API_KEY="sk-..."        # 通义千问（推荐国内用户）
# 或本地部署 Ollama，无需配置
```

---

## 🛡️ 反爬策略

PriceHunter 采用三级降级策略，确保数据获取稳定性：

```
┌─────────────────────────────────────────────────────────┐
│  Level 1: 官方联盟 API（最稳定、合规、可赚佣金）         │
│     ↓ 失败                                               │
│  Level 2: Playwright 无头浏览器（模拟真人操作）          │
│     ↓ 失败                                               │
│  Level 3: HTML 解析（基础抓取，可能不完整）              │
└─────────────────────────────────────────────────────────┘
```

---

## 📱 支持平台

| 平台 | 价格抓取 | 历史价格 | 口碑分析 | 联盟 API |
|------|---------|---------|---------|---------|
| 京东 | ✅ | ✅ | ✅ | ✅ |
| 淘宝/天猫 | ✅ | ⚠️ | ✅ | ✅ |
| 拼多多 | ✅ | ⚠️ | ✅ | ❌ |
| 抖音 | ✅ | ❌ | ✅ | ❌ |
| 小红书 | ❌ | ❌ | ✅ | ❌ |

> ✅ 完全支持 | ⚠️ 部分支持 | ❌ 不支持

---

## 🤝 贡献指南

欢迎提交 Issue 和 PR！

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/amazing-feature`
3. 提交更改：`git commit -m 'Add amazing feature'`
4. 推送分支：`git push origin feature/amazing-feature`
5. 创建 Pull Request

---

## 📄 许可证

本项目采用 [MIT](LICENSE) 许可证。

---

## 🙏 致谢

- 感谢各大电商平台提供的数据接口
- 感谢开源社区的优秀工具：Playwright、BeautifulSoup、Requests
- 感谢 WorkBuddy 框架提供的 Skill 支持

---

## 📞 联系我们

- 作者：[@yourusername](https://github.com/yourusername)
- 项目主页：[https://github.com/yourusername/price-hunter](https://github.com/yourusername/price-hunter)
- 问题反馈：[Issues](https://github.com/yourusername/price-hunter/issues)

---

<p align="center">
  如果本项目对你有帮助，请 ⭐ Star 支持一下！
</p>
