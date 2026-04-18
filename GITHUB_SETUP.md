# GitHub 仓库设置指南

## 第一步：在 GitHub 上创建仓库

1. 访问 https://github.com/new
2. 填写仓库信息：
   - **Repository name**: `price-hunter` （或你喜欢的名字）
   - **Description**: 智能比价购物助手 - 覆盖五大电商平台，AI 帮你找到最低价
   - **Visibility**: Public （推荐公开，方便获得 Star）
   - **Initialize**: 不要勾选任何初始化选项（README、.gitignore 等已准备好）
3. 点击 **Create repository**

## 第二步：推送代码到 GitHub

在终端执行以下命令：

```bash
# 进入项目目录
cd /Users/shakira/WorkBuddy/Claw/price-hunter-github

# 添加远程仓库（替换 yourusername 为你的 GitHub 用户名）
git remote add origin https://github.com/yourusername/price-hunter.git

# 推送代码
git push -u origin main
```

## 第三步：启用 GitHub Pages

1. 进入仓库页面 → Settings → Pages
2. Source 选择 **Deploy from a branch**
3. Branch 选择 **main**，文件夹选择 **/docs**
4. 点击 Save
5. 等待几分钟，访问 `https://yourusername.github.io/price-hunter` 查看网页

## 第四步：完善仓库信息

在仓库页面点击右侧的 **⚙️ Settings** 图标：

### 添加 Topics（标签）
点击右侧 "Topics" 添加：
- `price-comparison`
- `shopping-assistant`
- `workbuddy-skill`
- `ai-agent`
- `e-commerce`
- `python`
- `web-scraping`

### 添加 Social Preview（社交预览图）
在 Settings → General → Social preview 上传一张吸引人的封面图（建议 1280×640）

## 第五步：撰写 Release 说明

1. 点击仓库页面的 **Releases** → **Create a new release**
2. Tag version: `v2.0.0`
3. Release title: `PriceHunter v2.0 - Phase 2 Release`
4. 内容：

```markdown
## 🎉 PriceHunter v2.0 正式发布

### ✨ 新特性
- 支持 Playwright 无头浏览器（解决淘宝/抖音登录态问题）
- 接入淘宝联盟 / 京东联盟官方 API（合规 + 可赚佣金）
- LLM 情感分析替换关键词统计（口碑更准确）
- 三级降级策略确保稳定性

### 🛒 支持平台
- 京东 ✅ 价格 + 历史 + 口碑
- 淘宝/天猫 ✅ 价格 + 口碑
- 拼多多 ✅ 价格 + 口碑
- 抖音 ✅ 价格 + 口碑
- 小红书 ✅ 口碑分析

### 📖 文档
- 完整使用文档：https://yourusername.github.io/price-hunter
- GitHub 仓库：https://github.com/yourusername/price-hunter

### 🙏 感谢
感谢 WorkBuddy 框架提供的 Skill 支持！
```

## 第六步：推广获取 Star

### 分享渠道
1. **Twitter/X**: 发布项目介绍，@ 相关账号
2. **V2EX**: 在「分享创造」板块发帖
3. **即刻**: 分享到你的圈子
4. **朋友圈**: 让朋友帮忙 Star

### 分享文案模板

**中文版本：**
```
开源了一个智能比价助手 PriceHunter 🛒

覆盖淘宝、京东、拼多多、抖音、小红书五大平台，AI 自动分析价格走势和用户口碑，告诉你现在该不该买。

作为 WorkBuddy Skill 使用，一句话就能比价：
"帮我比价 iPhone 16 Pro"

GitHub: https://github.com/yourusername/price-hunter
演示: https://yourusername.github.io/price-hunter

求 Star ⭐ 支持！
```

**英文版本：**
```
Just open-sourced PriceHunter 🛒 - An AI-powered price comparison agent

Compare prices across 5 major Chinese e-commerce platforms (Taobao, JD, PDD, Douyin, Xiaohongshu) with AI review analysis.

GitHub: https://github.com/yourusername/price-hunter
Demo: https://yourusername.github.io/price-hunter

Star ⭐ if you find it useful!
```

## 文件结构说明

```
price-hunter/
├── README.md              # 项目主页说明
├── LICENSE                # MIT 许可证
├── requirements.txt       # Python 依赖
├── .gitignore            # Git 忽略文件
├── GITHUB_SETUP.md       # 本文件
├── docs/
│   └── index.html        # GitHub Pages 网页
├── scripts/              # 核心脚本
│   ├── price_crawl.py    # 多平台价格抓取
│   ├── price_history.py  # 历史价格查询
│   ├── review_summary.py # AI 口碑分析
│   └── affiliate_api.py  # 联盟 API
└── references/           # 参考文档
    └── platforms.md      # 平台接入说明
```

## 后续维护建议

1. **定期更新**: 每月检查依赖更新，修复潜在问题
2. **回应 Issue**: 及时回复用户的问题和建议
3. **添加功能**: 根据用户反馈持续迭代
4. **撰写文章**: 在技术社区分享开发经验，引流到项目

祝你的项目获得很多 Star！🌟
