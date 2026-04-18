#!/usr/bin/env python3
"""
affiliate_api.py - 联盟 API 独立模块 (Phase 2)
支持：
  - 淘宝联盟（阿里妈妈）商品搜索 + 推广链接生成
  - 京东联盟商品查询 + 推广链接生成

使用方式：
  # 搜索商品
  python3 scripts/affiliate_api.py --query "AirPods Pro" --platform taobao
  python3 scripts/affiliate_api.py --query "AirPods Pro" --platform jd
  python3 scripts/affiliate_api.py --query "AirPods Pro" --platform all

  # 将已知商品链接转换为推广链接（赚佣金）
  python3 scripts/affiliate_api.py --convert-url "https://item.jd.com/100049868979.html" --platform jd

环境变量配置（写入 ~/.zshrc）：
  # 淘宝联盟
  export TAOBAO_APP_KEY="your_app_key"
  export TAOBAO_APP_SECRET="your_app_secret"
  export TAOBAO_PID="mm_xxx_xxx_xxx"    # 推广位 PID

  # 京东联盟
  export JD_APP_KEY="your_app_key"
  export JD_APP_SECRET="your_app_secret"
  export JD_SITE_ID="your_site_id"

申请地址：
  淘宝联盟（阿里妈妈）: https://pub.alimama.com/
  京东联盟:             https://union.jd.com/
"""

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime


# ── 配置（全部从环境变量读取）────────────────────────────────────────────
TAOBAO_CFG = {
    "app_key":    os.environ.get("TAOBAO_APP_KEY", ""),
    "app_secret": os.environ.get("TAOBAO_APP_SECRET", ""),
    "pid":        os.environ.get("TAOBAO_PID", ""),
    "api_url":    "https://eco.taobao.com/router/rest",
}

JD_CFG = {
    "app_key":    os.environ.get("JD_APP_KEY", ""),
    "app_secret": os.environ.get("JD_APP_SECRET", ""),
    "site_id":    os.environ.get("JD_SITE_ID", ""),
    "api_url":    "https://api.jd.com/routerjson",
}


def _safe_get(url: str, timeout: int = 10) -> str | None:
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "PriceHunter/2.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════
# 淘宝联盟
# ══════════════════════════════════════════════════════════════════════════

def _tb_sign(params: dict, secret: str) -> str:
    """淘宝联盟 MD5 签名"""
    sorted_kv = sorted(params.items())
    raw = secret + "".join(f"{k}{v}" for k, v in sorted_kv) + secret
    return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()


def tb_search(query: str, page: int = 1, page_size: int = 10) -> dict:
    """
    淘宝联盟商品搜索
    API: taobao.tbk.dg.item.search
    
    返回:
      {
        "success": bool,
        "total": int,
        "items": [{ title, price, sale_price, commission_rate, click_url, coupon_url, ... }]
      }
    """
    if not TAOBAO_CFG["app_key"]:
        return {"success": False, "error": "未配置 TAOBAO_APP_KEY，请先设置环境变量"}

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    params = {
        "method":      "taobao.tbk.dg.item.search",
        "app_key":     TAOBAO_CFG["app_key"],
        "format":      "json",
        "v":           "2.0",
        "sign_method": "md5",
        "timestamp":   ts,
        "q":           query,
        "adzone_id":   TAOBAO_CFG["pid"],
        "page_no":     str(page),
        "page_size":   str(page_size),
        "sort":        "total_sales_des",
        "is_tmall":    "false",   # 同时包含淘宝和天猫
        "platform":    "2",       # 2=PC 1=移动端
    }
    params["sign"] = _tb_sign(params, TAOBAO_CFG["app_secret"])
    url = TAOBAO_CFG["api_url"] + "?" + urllib.parse.urlencode(params)

    raw = _safe_get(url)
    if not raw:
        return {"success": False, "error": "请求淘宝联盟 API 失败"}

    data = json.loads(raw)
    err = data.get("error_response")
    if err:
        return {"success": False, "error": f"{err.get('code')}: {err.get('sub_msg', err.get('msg', ''))}"}

    result_map = (data
                  .get("tbk_dg_item_search_response", {})
                  .get("result", {})
                  .get("result_list", {})
                  .get("map_data", []))

    items = []
    for item in result_map:
        original_price = float(item.get("reserve_price", 0) or 0)
        sale_price = float(item.get("zk_final_price", original_price) or original_price)
        coupon_amount = float(item.get("coupon_amount", 0) or 0)
        final_price = max(0.01, sale_price - coupon_amount)
        commission_rate = item.get("commission_rate", "0")
        commission_amount = round(final_price * float(commission_rate or 0) / 100, 2)

        items.append({
            "platform":         "淘宝/天猫",
            "platform_id":      "taobao",
            "title":            item.get("title", ""),
            "item_id":          item.get("item_id", ""),
            "original_price":   original_price,
            "sale_price":       sale_price,
            "coupon_amount":    coupon_amount,
            "final_price":      final_price,
            "commission_rate":  f"{commission_rate}%",
            "commission_amount": commission_amount,
            "click_url":        item.get("click_url", ""),    # 带佣金的推广链接
            "coupon_click_url": item.get("coupon_click_url", ""),
            "shop_title":       item.get("shop_title", ""),
            "volume":           int(item.get("volume", 0) or 0),
            "pic_url":          item.get("pict_url", ""),
        })

    total = int(
        data.get("tbk_dg_item_search_response", {})
            .get("result", {})
            .get("total_results", len(items))
    )
    return {"success": True, "total": total, "items": items}


def tb_convert_url(item_url: str) -> dict:
    """
    将普通淘宝/天猫商品链接转换为带佣金的推广链接
    API: taobao.tbk.dg.item.coupon.get
    """
    if not TAOBAO_CFG["app_key"]:
        return {"success": False, "error": "未配置 TAOBAO_APP_KEY"}

    # 从 URL 提取商品 ID
    import re
    item_id_match = re.search(r"id=(\d+)|/item/(\d+)", item_url)
    if not item_id_match:
        return {"success": False, "error": "无法从 URL 中提取商品 ID"}
    item_id = item_id_match.group(1) or item_id_match.group(2)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    params = {
        "method":      "taobao.tbk.dg.item.coupon.get",
        "app_key":     TAOBAO_CFG["app_key"],
        "format":      "json",
        "v":           "2.0",
        "sign_method": "md5",
        "timestamp":   ts,
        "adzone_id":   TAOBAO_CFG["pid"],
        "num_iids":    item_id,
    }
    params["sign"] = _tb_sign(params, TAOBAO_CFG["app_secret"])
    url = TAOBAO_CFG["api_url"] + "?" + urllib.parse.urlencode(params)

    raw = _safe_get(url)
    if not raw:
        return {"success": False, "error": "请求失败"}

    data = json.loads(raw)
    err = data.get("error_response")
    if err:
        return {"success": False, "error": f"{err.get('code')}: {err.get('sub_msg', '')}"}

    result = (data
              .get("tbk_dg_item_coupon_get_response", {})
              .get("result", {}))
    coupon_info_list = result.get("result_list", {}).get("map_data", [])
    if not coupon_info_list:
        return {"success": False, "error": "该商品暂无联盟推广资格"}

    info = coupon_info_list[0]
    return {
        "success":         True,
        "item_id":         item_id,
        "click_url":       info.get("click_url", ""),
        "coupon_click_url": info.get("coupon_click_url", ""),
        "commission_rate": info.get("commission_rate", ""),
        "coupon_amount":   info.get("coupon_amount", 0),
    }


# ══════════════════════════════════════════════════════════════════════════
# 京东联盟
# ══════════════════════════════════════════════════════════════════════════

def _jd_sign(params: dict, secret: str) -> str:
    """京东联盟 HMAC-SHA256 签名"""
    sorted_kv = sorted(params.items())
    raw = "&".join(f"{k}={v}" for k, v in sorted_kv)
    return hmac.new(
        secret.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def jd_search(query: str, page: int = 1, page_size: int = 10) -> dict:
    """
    京东联盟商品查询
    API: jd.union.open.goods.query
    文档: https://union.jd.com/helpcenter/13246-13247-46301
    """
    if not JD_CFG["app_key"]:
        return {"success": False, "error": "未配置 JD_APP_KEY，请先设置环境变量"}

    timestamp = str(int(time.time() * 1000))
    body = json.dumps({
        "goodsReqDTO": {
            "keyword":             query,
            "pageIndex":           page,
            "pageSize":            page_size,
            "sortName":            "inOrderCount30DaysSku",
            "sort":                "desc",
            "hasCoupon":           1,
            "isHot":               0,
        },
        "siteId": JD_CFG["site_id"],
    }, ensure_ascii=False, separators=(",", ":"))

    params = {
        "app_key":     JD_CFG["app_key"],
        "method":      "jd.union.open.goods.query",
        "timestamp":   timestamp,
        "format":      "json",
        "v":           "1.0",
        "sign_method": "hmac-sha256",
        "param_json":  body,
    }
    params["sign"] = _jd_sign(params, JD_CFG["app_secret"])

    url = JD_CFG["api_url"] + "?" + urllib.parse.urlencode(params)
    raw = _safe_get(url)
    if not raw:
        return {"success": False, "error": "请求京东联盟 API 失败"}

    data = json.loads(raw)
    resp = data.get("jd.union.open.goods.query_response", {})
    query_result = resp.get("queryResult", {})
    if query_result.get("code") != 200:
        return {"success": False, "error": query_result.get("message", "未知错误")}

    goods_list = query_result.get("data", []) or []
    items = []
    for g in goods_list:
        price_info      = g.get("priceInfo", {}) or {}
        coupon_info     = g.get("couponInfo", {}) or {}
        commission_info = g.get("commissionInfo", {}) or {}
        shop_info       = g.get("shopInfo", {}) or {}
        image_info      = g.get("imageInfo", {}) or {}
        coupons         = coupon_info.get("couponList") or [{}]
        best_coupon     = coupons[0] if coupons else {}

        original_price  = float(price_info.get("price", 0) or 0)
        lowest_price    = float(price_info.get("lowestPrice", original_price) or original_price)
        coupon_amount   = float(best_coupon.get("quota", 0) or 0)
        final_price     = max(0.01, lowest_price - coupon_amount)
        comm_share      = float(commission_info.get("commissionShare", 0) or 0)
        commission_amount = round(final_price * comm_share / 100, 2)

        items.append({
            "platform":          "京东",
            "platform_id":       "jd",
            "title":             g.get("skuName", ""),
            "sku_id":            str(g.get("skuId", "")),
            "original_price":    original_price,
            "sale_price":        lowest_price,
            "coupon_amount":     coupon_amount,
            "final_price":       final_price,
            "commission_rate":   f"{comm_share}%",
            "commission_amount": commission_amount,
            "click_url":         g.get("materialUrl", ""),  # 带佣金推广链接
            "coupon_url":        best_coupon.get("link", ""),
            "shop_title":        shop_info.get("shopName", ""),
            "volume":            int(g.get("inOrderCount30Days", 0) or 0),
            "pic_url":           (image_info.get("imageList") or [""])[0],
            "brand_name":        g.get("brandName", ""),
            "owner":             "京东自营" if shop_info.get("shopType") == 1 else "第三方商家",
        })

    total = query_result.get("totalCount", len(items))
    return {"success": True, "total": total, "items": items}


def jd_convert_url(item_url: str) -> dict:
    """
    将京东商品链接转换为带佣金的推广链接
    API: jd.union.open.promotion.byunionid.get
    """
    if not JD_CFG["app_key"]:
        return {"success": False, "error": "未配置 JD_APP_KEY"}

    import re
    sku_match = re.search(r"/(\d+)\.html|skuId=(\d+)|id=(\d+)", item_url)
    if not sku_match:
        return {"success": False, "error": "无法从 URL 中提取 SKU ID"}
    sku_id = sku_match.group(1) or sku_match.group(2) or sku_match.group(3)

    timestamp = str(int(time.time() * 1000))
    body = json.dumps({
        "promotionCodeReq": {
            "materialId":    f"https://item.jd.com/{sku_id}.html",
            "siteId":        JD_CFG["site_id"],
            "positionId":    "0",
            "chainType":     3,   # 3=长链接（含佣金）
        }
    }, ensure_ascii=False, separators=(",", ":"))

    params = {
        "app_key":     JD_CFG["app_key"],
        "method":      "jd.union.open.promotion.byunionid.get",
        "timestamp":   timestamp,
        "format":      "json",
        "v":           "1.0",
        "sign_method": "hmac-sha256",
        "param_json":  body,
    }
    params["sign"] = _jd_sign(params, JD_CFG["app_secret"])

    url = JD_CFG["api_url"] + "?" + urllib.parse.urlencode(params)
    raw = _safe_get(url)
    if not raw:
        return {"success": False, "error": "请求失败"}

    data = json.loads(raw)
    resp = data.get("jd.union.open.promotion.byunionid.get_response", {})
    result = resp.get("getResult", {}) or {}
    if result.get("code") != 200:
        return {"success": False, "error": result.get("message", "未知错误")}

    promo_url = result.get("data", {}).get("shortURL", "")
    return {
        "success":        True,
        "sku_id":         sku_id,
        "click_url":      promo_url,
        "original_url":   item_url,
    }


# ── 格式化输出 ─────────────────────────────────────────────────────────────
def format_result_table(items: list, platform: str) -> str:
    """将商品列表格式化为 Markdown 表格"""
    if not items:
        return f"（{platform} 暂无结果）"

    lines = [
        f"### {platform} 商品列表\n",
        "| # | 商品名称 | 原价 | 券后价 | 佣金比例 | 购买链接 |",
        "|---|----------|------|--------|----------|----------|",
    ]
    for i, item in enumerate(items[:5], 1):
        title = item.get("title", "")[:20] + ("..." if len(item.get("title", "")) > 20 else "")
        original = f"¥{item.get('original_price', '-'):.2f}"
        final = f"¥{item.get('final_price', item.get('sale_price', '-')):.2f}"
        comm = item.get("commission_rate", "-")
        link = item.get("click_url") or item.get("coupon_click_url") or "-"
        link_text = f"[购买]({link})" if link != "-" else "-"
        lines.append(f"| {i} | {title} | {original} | {final} | {comm} | {link_text} |")

    return "\n".join(lines)


# ── 主入口 ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="联盟 API 工具 - PriceHunter Phase 2")
    parser.add_argument("--query", help="商品搜索关键词")
    parser.add_argument("--convert-url", dest="convert_url", help="将商品链接转为推广链接")
    parser.add_argument(
        "--platform",
        default="all",
        choices=["taobao", "jd", "all"],
        help="平台选择",
    )
    parser.add_argument("--format", default="json", choices=["json", "table"], help="输出格式")
    args = parser.parse_args()

    if not args.query and not args.convert_url:
        parser.print_help()
        sys.exit(1)

    results = {}

    if args.convert_url:
        # URL 转推广链接模式
        if args.platform in ("taobao", "all"):
            results["taobao_convert"] = tb_convert_url(args.convert_url)
        if args.platform in ("jd", "all"):
            results["jd_convert"] = jd_convert_url(args.convert_url)

    elif args.query:
        # 商品搜索模式
        if args.platform in ("taobao", "all"):
            results["taobao"] = tb_search(args.query)
        if args.platform in ("jd", "all"):
            results["jd"] = jd_search(args.query)

    if args.format == "table":
        # Markdown 表格输出
        for key, data in results.items():
            if data.get("success"):
                print(format_result_table(data.get("items", []), key))
            else:
                print(f"❌ {key}: {data.get('error', '未知错误')}")
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
