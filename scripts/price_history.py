#!/usr/bin/env python3
"""
price_history.py - 历史价格查询脚本
数据来源：慢慢买（manmanbuy.com）、惠惠购物助手（huihui.cn）
输出：JSON 格式的历史价格走势
"""

import argparse
import json
import time
import random
import re
import urllib.request
import urllib.parse
from datetime import datetime, timedelta


UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"}


def jitter_sleep(a=0.5, b=1.2):
    time.sleep(random.uniform(a, b))


def safe_get(url: str, timeout: int = 10):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None


# ── 慢慢买历史价格 ────────────────────────────────────────────────────────
def fetch_manmanbuy(query: str, item_id: str | None = None) -> dict:
    """
    慢慢买：国内最完整的京东/淘宝价格历史数据库。
    支持商品 ID 直查 或 关键词搜索后取第一个结果。
    """
    if item_id:
        # 京东商品直查
        url = f"https://www.manmanbuy.com/getchart.aspx?itemid={item_id}&from=jd"
    else:
        encoded = urllib.parse.quote(query)
        url = f"https://www.manmanbuy.com/getItemInfo.aspx?key={encoded}"

    html = safe_get(url)
    jitter_sleep()

    result = {
        "source": "慢慢买",
        "source_url": url,
        "status": "success" if html else "failed",
        "data": [],
        "summary": {},
    }

    if html:
        # 尝试提取价格历史数据（JSON 格式嵌在 HTML 中）
        json_match = re.search(r'\[(\{"d":"[^]]+)\]', html)
        if json_match:
            try:
                raw = json.loads(f"[{json_match.group(1)}]")
                prices = [
                    {"date": item.get("d", ""), "price": float(item.get("p", 0))}
                    for item in raw
                    if item.get("p")
                ]
                result["data"] = prices[-90:]  # 最近90天

                if prices:
                    price_vals = [p["price"] for p in prices]
                    result["summary"] = {
                        "current_price": price_vals[-1],
                        "min_price": min(price_vals),
                        "max_price": max(price_vals),
                        "min_date": prices[price_vals.index(min(price_vals))]["date"],
                        "trend": _calc_trend(price_vals),
                    }
            except Exception:
                result["status"] = "parse_error"
        else:
            result["status"] = "no_data"

    return result


# ── 惠惠购物助手历史价格 ──────────────────────────────────────────────────
def fetch_huihui(query: str, item_id: str | None = None) -> dict:
    """
    惠惠购物助手：支持京东/淘宝/苏宁价格历史。
    """
    if item_id:
        url = f"https://zhushou.huihui.cn/s/priceHistory?itemId={item_id}&platform=jd"
    else:
        encoded = urllib.parse.quote(query)
        url = f"https://www.huihui.cn/search?keywords={encoded}"

    html = safe_get(url)
    jitter_sleep()

    result = {
        "source": "惠惠购物助手",
        "source_url": url,
        "status": "success" if html else "failed",
        "data": [],
        "summary": {},
    }

    if html:
        # 简单提取价格数字（降级处理）
        prices = re.findall(r'"price"\s*:\s*"?(\d+(?:\.\d+)?)"?', html)
        if prices:
            price_vals = [float(p) for p in prices if 1 < float(p) < 100000][:90]
            if price_vals:
                result["data"] = [
                    {
                        "date": (datetime.now() - timedelta(days=len(price_vals) - i)).strftime("%Y-%m-%d"),
                        "price": p,
                    }
                    for i, p in enumerate(price_vals)
                ]
                result["summary"] = {
                    "current_price": price_vals[-1],
                    "min_price": min(price_vals),
                    "max_price": max(price_vals),
                    "trend": _calc_trend(price_vals),
                }

    return result


# ── 工具函数 ──────────────────────────────────────────────────────────────
def _calc_trend(prices: list[float]) -> str:
    """计算近30天价格趋势"""
    if len(prices) < 2:
        return "数据不足"
    recent = prices[-30:] if len(prices) >= 30 else prices
    delta = recent[-1] - recent[0]
    pct = delta / recent[0] * 100 if recent[0] > 0 else 0

    if pct > 5:
        return f"上涨（近30天涨幅 {pct:.1f}%）"
    elif pct < -5:
        return f"下跌（近30天降幅 {abs(pct):.1f}%）"
    else:
        return f"平稳（近30天波动 {pct:+.1f}%）"


def _buy_advice(summary: dict) -> str:
    """根据历史价格给出购买建议"""
    if not summary:
        return "数据不足，建议手动查看历史"

    current = summary.get("current_price", 0)
    min_p = summary.get("min_price", 0)
    max_p = summary.get("max_price", 0)
    trend = summary.get("trend", "")

    if min_p == 0:
        return "数据不足"

    ratio = (current - min_p) / (max_p - min_p + 0.01)

    if ratio < 0.15:
        return "✅ 现在买！当前价格接近历史最低，是入手好时机"
    elif ratio < 0.4:
        return "🟡 价格偏低，可以考虑购买，但非历史最低"
    elif "下跌" in trend:
        return "⏳ 价格仍在下降，建议再等等"
    elif ratio > 0.8:
        return "❌ 当前价格偏高，建议等大促（618/双11）再入手"
    else:
        return "🟡 价格处于中间水平，等待降价或优惠券后入手更划算"


# ── 主入口 ────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="历史价格查询 - PriceHunter Skill")
    parser.add_argument("--query", required=True, help="商品名称或关键词")
    parser.add_argument("--item_id", default=None, help="商品 ID（可选，提升精准度）")
    parser.add_argument(
        "--sources",
        default="manmanbuy,huihui",
        help="数据来源，逗号分隔",
    )
    args = parser.parse_args()

    sources = set(args.sources.split(","))
    platform_results = []

    if "manmanbuy" in sources:
        platform_results.append(fetch_manmanbuy(args.query, args.item_id))
    if "huihui" in sources:
        platform_results.append(fetch_huihui(args.query, args.item_id))

    # 取最完整的数据源结果
    best = max(platform_results, key=lambda r: len(r.get("data", [])), default={})
    advice = _buy_advice(best.get("summary", {}))

    output = {
        "query": args.query,
        "item_id": args.item_id,
        "crawled_at": datetime.now().isoformat(),
        "buy_advice": advice,
        "best_source": best.get("source", ""),
        "summary": best.get("summary", {}),
        "price_history": best.get("data", []),
        "all_sources": platform_results,
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
