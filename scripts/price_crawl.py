#!/usr/bin/env python3
"""
price_crawl.py - 多平台价格抓取脚本 (Phase 2)
覆盖：淘宝/天猫、京东、拼多多、抖音小店、小红书

Phase 2 新增能力：
  - Playwright 无头浏览器（解决淘宝/抖音登录态 & JS 渲染问题）
  - 淘宝联盟 API（合规 + 可赚佣金）
  - 京东联盟 API（合规 + 可赚佣金）
  - 自动降级策略：联盟 API → Playwright → HTML 解析

输出：JSON 格式的价格数据
"""

import argparse
import json
import sys
import time
import random
import hashlib
import hmac
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

# ── 联盟 API 配置（从环境变量读取，不硬编码密钥）────────────────────────────
import os

TAOBAO_AFFILIATE_CONFIG = {
    "app_key": os.environ.get("TAOBAO_APP_KEY", ""),        # 淘宝联盟 AppKey
    "app_secret": os.environ.get("TAOBAO_APP_SECRET", ""),  # 淘宝联盟 AppSecret
    "pid": os.environ.get("TAOBAO_PID", ""),                # 推广位 PID（mm_xxx_xxx_xxx）
    "api_url": "https://eco.taobao.com/router/rest",
}

JD_AFFILIATE_CONFIG = {
    "app_key": os.environ.get("JD_APP_KEY", ""),            # 京东联盟 AppKey
    "app_secret": os.environ.get("JD_APP_SECRET", ""),      # 京东联盟 AppSecret
    "site_id": os.environ.get("JD_SITE_ID", ""),            # 推广网站 ID
    "api_url": "https://api.jd.com/routerjson",
}

# ── Playwright 可用性检测 ─────────────────────────────────────────────────
def _playwright_available() -> bool:
    """检测 playwright 是否已安装"""
    try:
        import importlib.util
        return importlib.util.find_spec("playwright") is not None
    except Exception:
        return False

PLAYWRIGHT_ENABLED = _playwright_available()

# ── 平台配置 ──────────────────────────────────────────────────────────────
PLATFORMS = {
    "jd": {
        "name": "京东",
        "search_url": "https://search.jd.com/Search?keyword={query}&enc=utf-8",
        "enabled": True,
        "method": "html",           # html | playwright | affiliate
    },
    "taobao": {
        "name": "淘宝/天猫",
        "search_url": "https://s.taobao.com/search?q={query}",
        "enabled": True,
        "method": "affiliate",      # 优先联盟 API，降级 playwright
    },
    "pdd": {
        "name": "拼多多",
        "search_url": "https://mobile.yangkeduo.com/search_result.html?search_key={query}",
        "enabled": True,
        "method": "html",
    },
    "douyin": {
        "name": "抖音小店",
        "search_url": "https://www.douyin.com/search/{query}?type=goods",
        "enabled": True,
        "method": "playwright",     # 只走 Playwright，无联盟 API
    },
    "xiaohongshu": {
        "name": "小红书",
        "search_url": "https://www.xiaohongshu.com/search_result?keyword={query}&source=web_search_result_notes",
        "enabled": True,
        "method": "link_only",      # 以口碑为主，不抓价格
    },
}

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)

DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": DESKTOP_UA,
    "Accept-Language": "zh-CN,zh;q=0.9",
}

MOBILE_HEADERS = {
    "User-Agent": MOBILE_UA,
    "Accept-Language": "zh-CN,zh;q=0.9",
}


# ── 工具函数 ──────────────────────────────────────────────────────────────
def jitter_sleep(min_s=0.5, max_s=1.5):
    time.sleep(random.uniform(min_s, max_s))


def safe_get(url: str, timeout: int = 8, mobile: bool = False):
    try:
        headers = MOBILE_HEADERS if mobile else HEADERS
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None


def parse_price_from_html(html: str, platform: str) -> list:
    import re
    results = []
    price_pattern = re.compile(r"[¥￥]?\s*(\d{1,6}(?:\.\d{1,2})?)")
    prices = price_pattern.findall(html or "")
    if prices:
        valid_prices = sorted(
            [float(p) for p in prices if 1 < float(p) < 100000],
        )[:3]
        for p in valid_prices:
            results.append({
                "platform": platform,
                "price": p,
                "currency": "CNY",
                "promotion": "",
                "url": "",
                "confidence": "low",
            })
    return results


# ══════════════════════════════════════════════════════════════════════════
# 淘宝联盟 API（Phase 2 新增）
# ══════════════════════════════════════════════════════════════════════════

def _taobao_sign(params: dict, secret: str) -> str:
    """淘宝联盟 API 签名算法（MD5）"""
    sorted_params = sorted(params.items())
    sign_str = secret + "".join(f"{k}{v}" for k, v in sorted_params) + secret
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()


def taobao_affiliate_search(query: str) -> list:
    """
    通过淘宝联盟 API 搜索商品并获取带佣金的推广链接。
    API: taobao.tbk.dg.item.search (淘客商品查询)
    文档: https://open.taobao.com/api.htm?docId=24515&docType=2
    
    返回 list[dict]，字段：platform / price / title / url(推广链接) / commission_rate
    """
    cfg = TAOBAO_AFFILIATE_CONFIG
    if not cfg["app_key"] or not cfg["app_secret"]:
        return []  # 未配置密钥，跳过

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    params = {
        "method": "taobao.tbk.dg.item.search",
        "app_key": cfg["app_key"],
        "format": "json",
        "v": "2.0",
        "sign_method": "md5",
        "timestamp": timestamp,
        "q": query,
        "adzone_id": cfg["pid"],
        "page_no": "1",
        "page_size": "5",
        "sort": "total_sales_des",  # 按销量排序
    }
    params["sign"] = _taobao_sign(params, cfg["app_secret"])

    encoded = urllib.parse.urlencode(params)
    url = f"{cfg['api_url']}?{encoded}"

    try:
        html = safe_get(url, timeout=10)
        if not html:
            return []
        data = json.loads(html)
        items = (data
                 .get("tbk_dg_item_search_response", {})
                 .get("result", {})
                 .get("result_list", {})
                 .get("map_data", []))
        results = []
        for item in items:
            results.append({
                "platform": "淘宝/天猫",
                "platform_id": "taobao",
                "title": item.get("title", ""),
                "price": float(item.get("reserve_price", item.get("zk_final_price", 0))),
                "sale_price": float(item.get("zk_final_price", 0)),
                "commission_rate": item.get("commission_rate", ""),
                "commission_type": "淘宝联盟佣金",
                "url": item.get("url", ""),
                "click_url": item.get("click_url", ""),  # 带佣金的推广链接
                "coupon_amount": item.get("coupon_amount", 0),
                "coupon_click_url": item.get("coupon_click_url", ""),
                "shop_title": item.get("shop_title", ""),
                "volume": item.get("volume", 0),  # 月销量
                "confidence": "high",
                "source": "affiliate_api",
            })
        return results
    except Exception as e:
        return []


# ══════════════════════════════════════════════════════════════════════════
# 京东联盟 API（Phase 2 新增）
# ══════════════════════════════════════════════════════════════════════════

def _jd_sign(params: dict, secret: str) -> str:
    """京东联盟 API 签名（HMAC-SHA256）"""
    sorted_params = sorted(params.items())
    sign_str = "&".join(f"{k}={v}" for k, v in sorted_params)
    return hmac.new(
        secret.encode("utf-8"),
        sign_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def jd_affiliate_search(query: str) -> list:
    """
    通过京东联盟 API 搜索商品并获取带佣金的推广链接。
    API: jd.union.open.goods.query (商品查询接口)
    文档: https://union.jd.com/helpcenter/13246-13247-46301

    返回 list[dict]，字段与淘宝联盟结构对齐
    """
    cfg = JD_AFFILIATE_CONFIG
    if not cfg["app_key"] or not cfg["app_secret"]:
        return []

    timestamp = str(int(time.time() * 1000))
    body = json.dumps({
        "goodsReqDTO": {
            "keyword": query,
            "pageIndex": 1,
            "pageSize": 10,
            "sortName": "inOrderCount30DaysSku",  # 按30天销量排序
            "sort": "desc",
            "hasCoupon": 1,    # 只查有优惠券的商品
        },
        "siteId": cfg["site_id"],
    }, ensure_ascii=False)

    params = {
        "app_key": cfg["app_key"],
        "method": "jd.union.open.goods.query",
        "timestamp": timestamp,
        "format": "json",
        "v": "1.0",
        "sign_method": "hmac-sha256",
        "param_json": body,
    }
    params["sign"] = _jd_sign(params, cfg["app_secret"])

    encoded = urllib.parse.urlencode(params)
    url = f"{cfg['api_url']}?{encoded}"

    try:
        html = safe_get(url, timeout=10)
        if not html:
            return []
        data = json.loads(html)
        goods_list = (data
                      .get("jd.union.open.goods.query_response", {})
                      .get("queryResult", {})
                      .get("data", []) or [])
        results = []
        for g in goods_list:
            price_info = g.get("priceInfo", {}) or {}
            coupon_info = g.get("couponInfo", {}) or {}
            commission_info = g.get("commissionInfo", {}) or {}
            best_coupon = (coupon_info.get("couponList") or [{}])[0]
            results.append({
                "platform": "京东",
                "platform_id": "jd",
                "title": g.get("skuName", ""),
                "price": float(price_info.get("price", 0)),
                "sale_price": float(price_info.get("lowestPrice", price_info.get("price", 0))),
                "commission_rate": str(commission_info.get("commissionShare", "")),
                "commission_type": "京东联盟佣金",
                "url": f"https://item.jd.com/{g.get('skuId', '')}.html",
                "click_url": g.get("materialUrl", ""),  # 带佣金的推广链接
                "coupon_amount": best_coupon.get("quota", 0),
                "coupon_url": best_coupon.get("link", ""),
                "shop_title": (g.get("shopInfo", {}) or {}).get("shopName", ""),
                "volume": g.get("inOrderCount30Days", 0),
                "confidence": "high",
                "source": "affiliate_api",
            })
        return results
    except Exception as e:
        return []


# ══════════════════════════════════════════════════════════════════════════
# Playwright 无头浏览器抓取（Phase 2 新增）
# ══════════════════════════════════════════════════════════════════════════

def _playwright_crawl(url: str, platform_name: str, wait_selector: str = None,
                      extract_js: str = None, cookies: list = None) -> list:
    """
    通用 Playwright 抓取函数。
    
    参数：
      url            - 目标搜索页 URL
      platform_name  - 平台名称（用于日志）
      wait_selector  - 等待出现的 CSS 选择器（None 则只等固定时间）
      extract_js     - 在页面中执行的 JS 脚本，返回商品数据数组
      cookies        - 可注入的 Cookie 列表（解决登录态问题）
    
    返回：list[dict] 价格数据
    """
    if not PLAYWRIGHT_ENABLED:
        return []

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
    except ImportError:
        return []

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",  # 反检测
            ],
        )
        context = browser.new_context(
            user_agent=DESKTOP_UA,
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )

        # 注入 Cookie（登录态）
        if cookies:
            context.add_cookies(cookies)

        # 屏蔽自动化特征
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
        """)

        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            # 等待关键元素出现
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=8000)
                except PwTimeout:
                    pass  # 超时不阻断，尝试继续
            else:
                time.sleep(random.uniform(2, 4))  # 等待 JS 渲染

            # 模拟人类行为：随机滚动
            page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.3)")
            time.sleep(random.uniform(0.5, 1.0))

            # 执行提取 JS
            if extract_js:
                raw = page.evaluate(extract_js)
                if isinstance(raw, list):
                    results = raw
            else:
                # 通用价格提取逻辑
                content = page.content()
                results = parse_price_from_html(content, platform_name)
        except Exception as e:
            pass
        finally:
            browser.close()

    return results


def crawl_taobao_playwright(query: str) -> list:
    """
    Playwright 抓取淘宝搜索结果。
    需要在环境变量中提供 Cookie 以获取登录态价格。
    
    Cookie 配置方式（在 ~/.zshrc 或运行前设置）：
      export TAOBAO_COOKIE="__m_h5_tk=xxx; ...完整cookie..."
    """
    encoded = urllib.parse.quote(query)
    url = f"https://s.taobao.com/search?q={encoded}&imgfile=&commend=all"

    # 从环境变量读取 Cookie（不硬编码）
    cookie_str = os.environ.get("TAOBAO_COOKIE", "")
    cookies = []
    if cookie_str:
        for item in cookie_str.split(";"):
            item = item.strip()
            if "=" in item:
                name, _, value = item.partition("=")
                cookies.append({
                    "name": name.strip(),
                    "value": value.strip(),
                    "domain": ".taobao.com",
                    "path": "/",
                })

    # 提取淘宝商品价格的 JS 脚本
    extract_js = """
    (() => {
        const items = [];
        // 尝试多种选择器（PC版/App版）
        const selectors = [
            '.Price--priceInt--Zp54N3n',   // 天猫搜索
            '.price-value',
            '[data-price]',
            '.priceIntM',
        ];
        for (const sel of selectors) {
            document.querySelectorAll(sel).forEach((el, idx) => {
                if (idx >= 5) return;
                const priceText = el.innerText || el.getAttribute('data-price') || '';
                const price = parseFloat(priceText.replace(/[^0-9.]/g, ''));
                if (price > 1 && price < 100000) {
                    // 尝试获取商品名和链接
                    const parent = el.closest('a, [data-item-id], .item');
                    const href = parent ? (parent.href || '') : '';
                    items.push({
                        platform: '淘宝/天猫',
                        platform_id: 'taobao',
                        price: price,
                        currency: 'CNY',
                        url: href,
                        confidence: 'medium',
                        source: 'playwright',
                    });
                }
            });
            if (items.length > 0) break;
        }
        return items;
    })()
    """

    return _playwright_crawl(
        url=url,
        platform_name="淘宝/天猫",
        wait_selector=".item",
        extract_js=extract_js,
        cookies=cookies if cookies else None,
    )


def crawl_douyin_playwright(query: str) -> list:
    """
    Playwright 抓取抖音商品搜索结果。
    抖音反爬极强，采用 stealth 模式 + 随机延迟。
    
    Cookie 配置：
      export DOUYIN_COOKIE="ttwid=xxx; ...完整cookie..."
    """
    encoded = urllib.parse.quote(query)
    url = f"https://www.douyin.com/search/{encoded}?type=goods"

    cookie_str = os.environ.get("DOUYIN_COOKIE", "")
    cookies = []
    if cookie_str:
        for item in cookie_str.split(";"):
            item = item.strip()
            if "=" in item:
                name, _, value = item.partition("=")
                cookies.append({
                    "name": name.strip(),
                    "value": value.strip(),
                    "domain": ".douyin.com",
                    "path": "/",
                })

    extract_js = """
    (() => {
        const items = [];
        // 抖音商品卡价格选择器
        const priceEls = document.querySelectorAll(
            '[class*="price"], [class*="Price"], .goods-price, .product-price'
        );
        priceEls.forEach((el, idx) => {
            if (idx >= 5) return;
            const text = el.innerText || '';
            const price = parseFloat(text.replace(/[^0-9.]/g, ''));
            if (price > 1 && price < 100000) {
                items.push({
                    platform: '抖音小店',
                    platform_id: 'douyin',
                    price: price,
                    currency: 'CNY',
                    url: window.location.href,
                    confidence: 'medium',
                    source: 'playwright',
                });
            }
        });
        return items;
    })()
    """

    return _playwright_crawl(
        url=url,
        platform_name="抖音小店",
        wait_selector=None,   # 抖音无稳定选择器，等固定时间
        extract_js=extract_js,
        cookies=cookies if cookies else None,
    )


# ══════════════════════════════════════════════════════════════════════════
# 各平台主抓取函数（带降级链路）
# ══════════════════════════════════════════════════════════════════════════

def crawl_taobao(query: str) -> dict:
    """
    淘宝/天猫抓取，完整降级链路：
    1. 淘宝联盟 API（最优：合规+佣金）
    2. Playwright 无头浏览器（次优：能处理登录态）
    3. 静态 HTML 解析（保底：置信度低）
    """
    encoded = urllib.parse.quote(query)
    search_url = f"https://s.taobao.com/search?q={encoded}"
    result = {
        "platform": "淘宝/天猫",
        "platform_id": "taobao",
        "query": query,
        "status": "failed",
        "items": [],
        "search_url": search_url,
        "crawled_at": datetime.now().isoformat(),
        "method_used": "",
    }

    # ── 优先：联盟 API ──
    affiliate_items = taobao_affiliate_search(query)
    if affiliate_items:
        result["items"] = affiliate_items
        result["status"] = "success"
        result["method_used"] = "affiliate_api"
        result["note"] = "数据来自淘宝联盟官方 API，含佣金推广链接"
        return result

    # ── 次选：Playwright ──
    if PLAYWRIGHT_ENABLED:
        pw_items = crawl_taobao_playwright(query)
        if pw_items:
            result["items"] = pw_items
            result["status"] = "success"
            result["method_used"] = "playwright"
            result["note"] = "数据由 Playwright 无头浏览器抓取"
            return result

    # ── 保底：HTML 解析 ──
    html = safe_get(search_url)
    jitter_sleep()
    if html:
        result["items"] = parse_price_from_html(html, "淘宝/天猫")
        result["status"] = "success" if result["items"] else "partial"
        result["method_used"] = "html_parse"
        result["note"] = "淘宝部分数据需登录态，价格仅供参考（置信度低）"
    else:
        result["method_used"] = "none"
        result["note"] = "请配置 TAOBAO_APP_KEY 或 TAOBAO_COOKIE 以获取完整数据"

    return result


def crawl_jd(query: str) -> dict:
    """
    京东抓取，降级链路：
    1. 京东联盟 API（合规+佣金）
    2. HTML 解析（备选）
    """
    encoded = urllib.parse.quote(query)
    search_url = f"https://search.jd.com/Search?keyword={encoded}&enc=utf-8"
    result = {
        "platform": "京东",
        "platform_id": "jd",
        "query": query,
        "status": "failed",
        "items": [],
        "search_url": search_url,
        "crawled_at": datetime.now().isoformat(),
        "method_used": "",
    }

    # ── 优先：京东联盟 API ──
    affiliate_items = jd_affiliate_search(query)
    if affiliate_items:
        result["items"] = affiliate_items
        result["status"] = "success"
        result["method_used"] = "affiliate_api"
        result["note"] = "数据来自京东联盟官方 API，含佣金推广链接"
        return result

    # ── 保底：HTML 解析 ──
    html = safe_get(search_url)
    jitter_sleep()
    if html:
        result["items"] = parse_price_from_html(html, "京东")
        result["status"] = "success" if result["items"] else "partial"
        result["method_used"] = "html_parse"
    else:
        result["status"] = "failed"
        result["method_used"] = "none"
        result["error"] = "请求失败，可能触发反爬"

    return result


def crawl_pdd(query: str) -> dict:
    """拼多多价格抓取（移动端 UA + HTML 解析）"""
    encoded = urllib.parse.quote(query)
    url = f"https://mobile.yangkeduo.com/search_result.html?search_key={encoded}"
    html = safe_get(url, mobile=True)
    jitter_sleep()

    result = {
        "platform": "拼多多",
        "platform_id": "pdd",
        "query": query,
        "status": "success" if html else "failed",
        "items": [],
        "search_url": url,
        "crawled_at": datetime.now().isoformat(),
        "method_used": "html_parse",
    }
    if html:
        result["items"] = parse_price_from_html(html, "拼多多")

    return result


def crawl_douyin(query: str) -> dict:
    """
    抖音小店抓取，降级链路：
    1. Playwright（可处理 JS 渲染）
    2. 提供搜索直链（保底）
    """
    encoded = urllib.parse.quote(query)
    search_url = f"https://www.douyin.com/search/{encoded}?type=goods"
    result = {
        "platform": "抖音小店",
        "platform_id": "douyin",
        "query": query,
        "status": "manual_required",
        "items": [],
        "search_url": search_url,
        "crawled_at": datetime.now().isoformat(),
        "method_used": "",
    }

    # ── 优先：Playwright ──
    if PLAYWRIGHT_ENABLED:
        pw_items = crawl_douyin_playwright(query)
        if pw_items:
            result["items"] = pw_items
            result["status"] = "success"
            result["method_used"] = "playwright"
            result["note"] = "数据由 Playwright 无头浏览器抓取"
            return result

    result["method_used"] = "link_only"
    result["note"] = (
        "抖音反爬极强。已提供搜索直链，请手动查看。\n"
        "如需自动抓取，请安装 playwright：pip install playwright && playwright install chromium\n"
        "并配置 DOUYIN_COOKIE 环境变量注入登录态。"
    )
    return result


def crawl_xiaohongshu(query: str) -> dict:
    """小红书（以口碑为主，价格为辅，提供搜索直链）"""
    encoded = urllib.parse.quote(query)
    search_url = (
        f"https://www.xiaohongshu.com/search_result"
        f"?keyword={encoded}&source=web_search_result_notes"
    )
    return {
        "platform": "小红书",
        "platform_id": "xiaohongshu",
        "query": query,
        "status": "link_only",
        "items": [],
        "search_url": search_url,
        "crawled_at": datetime.now().isoformat(),
        "method_used": "link_only",
        "note": "小红书以口碑为主，价格数据由 review_summary.py 处理",
    }


# ── 主入口 ────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="多平台价格抓取 - PriceHunter Skill Phase 2"
    )
    parser.add_argument("--query", required=True, help="商品名称或关键词")
    parser.add_argument("--url", default=None, help="商品原始链接（可选）")
    parser.add_argument(
        "--platforms",
        default="jd,taobao,pdd,douyin,xiaohongshu",
        help="要抓取的平台，逗号分隔",
    )
    args = parser.parse_args()

    # 打印配置状态（方便调试）
    print(f"[PriceHunter Phase 2] 查询: {args.query}", file=sys.stderr)
    print(f"[PriceHunter Phase 2] Playwright: {'✓ 可用' if PLAYWRIGHT_ENABLED else '✗ 未安装'}", file=sys.stderr)
    print(f"[PriceHunter Phase 2] 淘宝联盟 API: {'✓ 已配置' if TAOBAO_AFFILIATE_CONFIG['app_key'] else '✗ 未配置'}", file=sys.stderr)
    print(f"[PriceHunter Phase 2] 京东联盟 API: {'✓ 已配置' if JD_AFFILIATE_CONFIG['app_key'] else '✗ 未配置'}", file=sys.stderr)

    requested = set(args.platforms.split(","))
    crawlers = {
        "jd": crawl_jd,
        "taobao": crawl_taobao,
        "pdd": crawl_pdd,
        "douyin": crawl_douyin,
        "xiaohongshu": crawl_xiaohongshu,
    }

    results = []
    for platform_id, fn in crawlers.items():
        if platform_id in requested:
            try:
                r = fn(args.query)
                results.append(r)
            except Exception as e:
                results.append({
                    "platform_id": platform_id,
                    "status": "error",
                    "error": str(e),
                    "query": args.query,
                })

    output = {
        "query": args.query,
        "original_url": args.url,
        "crawled_at": datetime.now().isoformat(),
        "phase": "2.0",
        "capabilities": {
            "playwright": PLAYWRIGHT_ENABLED,
            "taobao_affiliate": bool(TAOBAO_AFFILIATE_CONFIG["app_key"]),
            "jd_affiliate": bool(JD_AFFILIATE_CONFIG["app_key"]),
        },
        "platforms": results,
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
