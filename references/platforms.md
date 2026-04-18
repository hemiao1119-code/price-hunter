# 平台说明与接入参考

本文件供 `price-hunter` Skill 的脚本调用时参考，记录各平台的数据接入方式、字段说明和反爬降级策略。

---

## 一、各平台接入现状

### 1. 京东

| 项目 | 说明 |
|------|------|
| 价格接口 | 搜索页 HTML 解析 / `api.jd.com` 开放接口 |
| 历史价格 | 慢慢买、惠惠 均支持 JD 商品 ID 直查 |
| 反爬等级 | ⭐⭐（中等，UA + 随机延迟可绕过） |
| 推荐策略 | 优先使用 `api.jd.com` 开放接口，失败则 HTML 解析 |
| 商品 ID 格式 | 纯数字，如 `100049868979` |

**字段映射：**

```json
{
  "skuId": "商品 ID",
  "name": "商品名称",
  "price": "当前价格（字符串，需转 float）",
  "originalPrice": "原价",
  "promotionInfo": "促销文案"
}
```

---

### 2. 淘宝 / 天猫

| 项目 | 说明 |
|------|------|
| 价格接口 | 需登录态 Cookie，无公开 API |
| 历史价格 | 慢慢买支持，精准度低于京东 |
| 反爬等级 | ⭐⭐⭐⭐（强，需登录态 + 滑块验证） |
| 推荐策略 | 提供搜索直链，提示用户手动查看；或接入官方联盟 API |
| 降级方案 | 引导用户使用"比价"类浏览器插件（惠惠/慢慢买插件版） |

**官方开放渠道（需申请）：**
- 淘宝开放平台：`https://open.taobao.com`
- API：`taobao.items.search`，需 AppKey + Secret

---

### 3. 拼多多

| 项目 | 说明 |
|------|------|
| 价格接口 | `apiv2.yangkeduo.com` / wap 搜索页 |
| 历史价格 | 支持有限，慢慢买覆盖部分 PDD 商品 |
| 反爬等级 | ⭐⭐⭐（需移动端 UA + 随机延迟） |
| 推荐策略 | 使用移动端 wap 地址 + 移动端 UA |
| 关键字段 | `goods_price_str`（含补贴价格）、`goods_name` |

**推荐 UA（移动端）：**

```
Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)
AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1
```

---

### 4. 抖音小店

| 项目 | 说明 |
|------|------|
| 价格接口 | 无公开 API，App 内数据加密 |
| 历史价格 | 不支持 |
| 反爬等级 | ⭐⭐⭐⭐⭐（最强，App 专有协议） |
| 推荐策略 | **只提供搜索直链**，不自动抓取 |
| 官方渠道 | 抖音开放平台 `https://op.jinritemai.com`，需商家资质 |

---

### 5. 小红书

| 项目 | 说明 |
|------|------|
| 价格接口 | 无公开商品价格 API |
| 口碑数据 | 笔记内容可抓取，含种草/避雷关键词 |
| 反爬等级 | ⭐⭐⭐⭐（需登录态） |
| 推荐策略 | 作为**口碑数据来源**，不作价格来源；提供搜索直链 |
| 口碑字段 | 笔记标题、标签（#好用、#避雷）、点赞数 |

---

### 6. 慢慢买（价格历史）

| 项目 | 说明 |
|------|------|
| 接口 | `https://www.manmanbuy.com/getchart.aspx?itemid=<JD_ID>&from=jd` |
| 数据格式 | HTML 内嵌 JSON，字段：`d`（日期）、`p`（价格） |
| 覆盖平台 | 京东（最全）、淘宝（部分）、苏宁 |
| 反爬等级 | ⭐⭐（低，正常请求即可） |
| 限制 | 需知道商品 ID；无 ID 时走关键词搜索精准度较低 |

---

### 7. 惠惠购物助手（价格历史）

| 项目 | 说明 |
|------|------|
| 接口 | `https://zhushou.huihui.cn/s/priceHistory?itemId=<ID>&platform=jd` |
| 数据格式 | JSON，字段：`price`、`date` |
| 覆盖平台 | 京东、天猫、苏宁 |
| 反爬等级 | ⭐（极低） |
| 特色 | 支持价格提醒订阅（需注册账号） |

---

## 二、反爬通用策略

1. **随机延迟**：每次请求间隔 0.5–1.5 秒（`jitter_sleep()`）
2. **UA 轮换**：维护 3–5 个真实 UA，随机选取
3. **降级处理**：单平台失败不阻断流程，报告中标注"数据获取失败"
4. **频率控制**：同一平台每分钟请求不超过 10 次
5. **IP 代理**（可选）：高频使用时接入代理池（推荐：快代理、芝麻代理）

---

## 三、Phase 2 已完成升级

| 升级方向 | 状态 | 说明 |
|----------|------|------|
| Playwright 无头浏览器 | ✅ 已实现 | 解决淘宝/抖音 JS 渲染 + 登录态问题 |
| 淘宝联盟 API | ✅ 已实现 | `taobao.tbk.dg.item.search`，合规 + 带佣金推广链接 |
| 京东联盟 API | ✅ 已实现 | `jd.union.open.goods.query`，合规 + 带佣金推广链接 |
| LLM 情感分析 | ✅ 已实现 | 支持 OpenAI / 通义千问 / Ollama，自动降级关键词分析 |
| 联盟 URL 转换 | ✅ 已实现 | 任意商品链接 → 带佣金推广链接（`affiliate_api.py`） |

---

## 四、Phase 2 环境配置

### 安装 Playwright

```bash
pip install playwright
playwright install chromium
```

### 配置联盟 API 密钥（写入 ~/.zshrc）

```bash
# 淘宝联盟（申请地址：https://pub.alimama.com/）
export TAOBAO_APP_KEY="your_app_key"
export TAOBAO_APP_SECRET="your_app_secret"
export TAOBAO_PID="mm_xxx_xxx_xxx"

# 京东联盟（申请地址：https://union.jd.com/）
export JD_APP_KEY="your_app_key"
export JD_APP_SECRET="your_app_secret"
export JD_SITE_ID="your_site_id"

# 登录态 Cookie（用于 Playwright 抓取，解决淘宝/抖音登录墙）
export TAOBAO_COOKIE="__m_h5_tk=xxx; ..."   # 从浏览器开发工具 -> Network 复制
export DOUYIN_COOKIE="ttwid=xxx; ..."

# LLM 情感分析（三选一）
export OPENAI_API_KEY="sk-..."              # OpenAI
export DASHSCOPE_API_KEY="sk-..."           # 通义千问（国内推荐）
# 或安装 Ollama 后不需要配置（自动尝试本地服务）
export LLM_MODEL="gpt-4o-mini"             # 模型名称
```

### 降级链路说明

| 场景 | 淘宝 | 京东 | 抖音 |
|------|------|------|------|
| 联盟 API 已配置 | ✅ 联盟 API（最优） | ✅ 联盟 API（最优） | ❌ 无联盟 API |
| Playwright 已安装 | ✅ 无头浏览器 | - | ✅ 无头浏览器 |
| 仅普通请求 | ⚠ HTML 解析（低置信度） | ⚠ HTML 解析 | 🔗 搜索直链 |

---

## 五、佣金收益说明

接入联盟 API 后，所有生成的 `click_url` 均为带推广 ID 的追踪链接。

| 平台 | 佣金比例（参考） | 结算周期 |
|------|-----------------|---------|
| 淘宝联盟 | 1% ~ 90%（视商品类目） | 确认收货后 T+15 |
| 京东联盟 | 1% ~ 50%（视商品类目） | 确认收货后 T+20 |

> 注：实际佣金比例以联盟后台展示为准，数码/3C 类目通常 3%-8%。

---

## 六、待完成升级（Phase 3+）

| 升级方向 | 说明 |
|----------|------|
| SQLite 数据缓存 | 相同商品 24h 内复用数据，减少 API 调用 |
| 价格提醒 | 定时轮询 + 微信推送（接入 WorkBuddy 定时任务） |
| 拼多多多多进宝 | PDD 联盟 API，补全拼多多佣金链接 |
| 历史价格图表 | 接入慢慢买/惠惠，生成 90 天价格走势图 |
