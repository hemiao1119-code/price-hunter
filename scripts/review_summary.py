#!/usr/bin/env python3
"""
review_summary.py - 用户口碑聚合脚本 (Phase 2)
数据来源：小红书、知乎、B站、京东/淘宝评价

Phase 2 升级：
  - LLM 情感分析替换关键词统计（更准确，能理解语境）
  - 支持多 LLM 后端：OpenAI / 通义千问 / 本地 Ollama
  - LLM 不可用时自动降级到关键词统计（Phase 1 逻辑）
  - 输出结构化口碑摘要：评分 + 正负面关键词 + 典型评价 + 综合结论

LLM 配置（写入 ~/.zshrc 或运行前设置）：
  # 使用 OpenAI（或兼容接口）
  export OPENAI_API_KEY="sk-..."
  export OPENAI_BASE_URL="https://api.openai.com/v1"  # 可替换为国内代理
  export LLM_MODEL="gpt-4o-mini"                     # 性价比最高的模型

  # 或使用通义千问
  export DASHSCOPE_API_KEY="sk-..."
  export LLM_BACKEND="qwen"

  # 或使用本地 Ollama（免费）
  export LLM_BACKEND="ollama"
  export OLLAMA_BASE_URL="http://localhost:11434"
  export LLM_MODEL="qwen2.5:7b"                     # 推荐中文模型
"""

import argparse
import json
import os
import sys
import time
import random
import urllib.request
import urllib.parse
from datetime import datetime
from collections import Counter


# ── User-Agent ────────────────────────────────────────────────────────────
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"}


# ── Phase 1 关键词词典（降级备用）────────────────────────────────────────
POSITIVE_KEYWORDS = [
    "好用", "值得", "推荐", "正品", "快递快", "性价比高", "颜值高", "质量好",
    "满意", "超赞", "完美", "惊喜", "耐用", "舒适", "实惠", "划算", "超值",
    "很好", "不错", "喜欢", "棒", "强烈推荐", "真的好", "真香", "闭眼入",
]
NEGATIVE_KEYWORDS = [
    "差评", "假货", "劣质", "退货", "慢", "坏了", "失望", "不值", "后悔",
    "质量差", "客服差", "坑", "骗", "虚假", "过期", "漏液", "破损", "踩坑",
    "不推荐", "避雷", "别买", "垃圾", "智商税", "翻车",
]


# ══════════════════════════════════════════════════════════════════════════
# LLM 情感分析（Phase 2 核心升级）
# ══════════════════════════════════════════════════════════════════════════

LLM_BACKEND  = os.environ.get("LLM_BACKEND", "openai")      # openai | qwen | ollama
OPENAI_KEY   = os.environ.get("OPENAI_API_KEY", "")
OPENAI_URL   = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
DASHSCOPE_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
OLLAMA_URL   = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL    = os.environ.get("LLM_MODEL", "gpt-4o-mini")

# 情感分析 Prompt 模板
SENTIMENT_PROMPT = """你是一位专业的购物口碑分析师。请分析以下商品评论文本，输出 JSON 格式的口碑摘要。

商品名称：{product_name}

评论文本：
{reviews_text}

请以如下 JSON 格式输出（不要输出其他内容）：
{{
  "score": <1.0-5.0之间的数字，基于情感倾向判断>,
  "positive_keywords": ["关键词1", "关键词2", "关键词3", "关键词4", "关键词5"],
  "negative_keywords": ["关键词1", "关键词2", "关键词3"],
  "sentiment_summary": "一句话总结整体口碑（20字以内）",
  "buy_advice": "买 | 谨慎 | 不买",
  "reasoning": "给出建议的核心理由（30字以内）",
  "typical_positive": "最具代表性的好评摘录（原文，40字以内）",
  "typical_negative": "最具代表性的差评摘录（原文，40字以内，无差评填空字符串）"
}}

评分标准：
- 5.0：极度好评，无明显槽点
- 4.0-4.9：多数好评，少量问题
- 3.0-3.9：褒贬参半，需谨慎
- 2.0-2.9：差评居多，明显问题
- 1.0-1.9：极差，强烈不推荐"""


def _call_openai(prompt: str) -> str | None:
    """调用 OpenAI 兼容接口"""
    if not OPENAI_KEY:
        return None
    payload = json.dumps({
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 512,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OPENAI_URL.rstrip('/')}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {OPENAI_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except Exception:
        return None


def _call_qwen(prompt: str) -> str | None:
    """调用阿里通义千问 DashScope API"""
    if not DASHSCOPE_KEY:
        return None
    payload = json.dumps({
        "model": os.environ.get("LLM_MODEL", "qwen-turbo"),
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "parameters": {"temperature": 0.3},
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
        data=payload,
        headers={
            "Authorization": f"Bearer {DASHSCOPE_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["output"]["text"]
    except Exception:
        return None


def _call_ollama(prompt: str) -> str | None:
    """调用本地 Ollama"""
    payload = json.dumps({
        "model": LLM_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "")
    except Exception:
        return None


def _call_llm(prompt: str) -> str | None:
    """统一 LLM 调用入口，按配置选择后端"""
    backends = {
        "openai": _call_openai,
        "qwen":   _call_qwen,
        "ollama": _call_ollama,
    }
    fn = backends.get(LLM_BACKEND)
    if fn:
        return fn(prompt)
    # 未知 backend，按优先级依次尝试
    for backend_fn in [_call_openai, _call_qwen, _call_ollama]:
        result = backend_fn(prompt)
        if result:
            return result
    return None


def _extract_json_from_llm(text: str) -> dict | None:
    """从 LLM 输出中提取 JSON（处理 markdown 代码块等情况）"""
    import re
    # 去掉 markdown 代码块
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = text.strip()
    # 找到第一个 { 到最后一个 }
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    try:
        return json.loads(text[start:end])
    except Exception:
        return None


def llm_analyze_sentiment(product_name: str, reviews: list[str]) -> dict:
    """
    使用 LLM 对评论文本进行情感分析。
    如果 LLM 不可用，自动降级到关键词统计。
    
    返回与 keyword_analyze_sentiment 相同结构的 dict。
    """
    if not reviews:
        return {"score": 3.0, "positive_keywords": [], "negative_keywords": [],
                "method": "empty", "sentiment_summary": "暂无评论数据"}

    # 限制输入长度：取最长的 10 条，每条截断到 200 字
    top_reviews = sorted(reviews, key=len, reverse=True)[:10]
    reviews_text = "\n".join(f"- {r[:200]}" for r in top_reviews)

    prompt = SENTIMENT_PROMPT.format(
        product_name=product_name,
        reviews_text=reviews_text,
    )

    raw = _call_llm(prompt)
    if raw:
        parsed = _extract_json_from_llm(raw)
        if parsed and "score" in parsed:
            return {
                "score":              float(parsed.get("score", 3.0)),
                "positive_keywords":  parsed.get("positive_keywords", [])[:5],
                "negative_keywords":  parsed.get("negative_keywords", [])[:5],
                "sentiment_summary":  parsed.get("sentiment_summary", ""),
                "buy_advice":         parsed.get("buy_advice", ""),
                "reasoning":          parsed.get("reasoning", ""),
                "typical_positive":   parsed.get("typical_positive", ""),
                "typical_negative":   parsed.get("typical_negative", ""),
                "method":             f"llm:{LLM_BACKEND}/{LLM_MODEL}",
            }

    # ── 降级：关键词统计（Phase 1 逻辑）──
    print("[review_summary] LLM 不可用，降级到关键词统计", file=sys.stderr)
    return keyword_analyze_sentiment(" ".join(reviews))


def keyword_analyze_sentiment(text: str) -> dict:
    """Phase 1 关键词统计情感分析（保留为降级方案）"""
    pos_hits = [kw for kw in POSITIVE_KEYWORDS if kw in text]
    neg_hits = [kw for kw in NEGATIVE_KEYWORDS if kw in text]
    total = len(pos_hits) + len(neg_hits)
    if total == 0:
        score = 3.0
    else:
        score = round(3.0 + 2.0 * (len(pos_hits) - len(neg_hits)) / total, 1)
        score = max(1.0, min(5.0, score))
    return {
        "score":             score,
        "positive_keywords": pos_hits[:5],
        "negative_keywords": neg_hits[:5],
        "method":            "keyword_dict",
    }


# ══════════════════════════════════════════════════════════════════════════
# 各平台口碑抓取
# ══════════════════════════════════════════════════════════════════════════

def jitter_sleep(a=0.3, b=0.8):
    time.sleep(random.uniform(a, b))


def safe_get(url: str, timeout: int = 8):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None


def _extract_text_snippets(html: str, max_items: int = 10) -> list[str]:
    """从 HTML 中提取有意义的文本片段"""
    import re
    snippets = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL)
    clean = [re.sub(r"<[^>]+>", "", s).strip() for s in snippets]
    return [s for s in clean if 10 < len(s) < 300][:max_items]


def fetch_zhihu(query: str) -> dict:
    """知乎搜索口碑"""
    encoded = urllib.parse.quote(f"{query} 怎么样 值得买吗")
    url = f"https://www.zhihu.com/search?type=content&q={encoded}"
    html = safe_get(url)
    jitter_sleep()

    result = {
        "platform": "知乎",
        "status": "success" if html else "failed",
        "search_url": url,
        "snippets": [],
        "raw_text": "",
        "sentiment": {},
    }
    if html:
        snippets = _extract_text_snippets(html)
        result["snippets"] = snippets
        result["raw_text"] = " ".join(snippets)
    return result


def fetch_jd_reviews(query: str) -> dict:
    """京东评论口碑（通过搜索页提取商品名片段）"""
    import re
    encoded = urllib.parse.quote(query)
    url = f"https://search.jd.com/Search?keyword={encoded}&enc=utf-8"
    html = safe_get(url)
    jitter_sleep()

    result = {
        "platform": "京东评论",
        "status": "success" if html else "failed",
        "search_url": url,
        "snippets": [],
        "raw_text": "",
        "sentiment": {},
    }
    if html:
        # 提取商品名称（作为口碑语料）
        names = re.findall(
            r'class="p-name[^"]*"[^>]*><[^>]+>(.*?)</[^>]+>', html, re.DOTALL
        )
        clean = [re.sub(r"<[^>]+>", "", s).strip() for s in names]
        snippets = [s for s in clean if 5 < len(s) < 200][:8]
        result["snippets"] = snippets
        result["raw_text"] = " ".join(snippets)
    return result


def fetch_xiaohongshu(query: str) -> dict:
    """小红书口碑（需登录态，提供搜索直链）"""
    encoded = urllib.parse.quote(query)
    search_url = (
        f"https://www.xiaohongshu.com/search_result"
        f"?keyword={encoded}&source=web_search_result_notes"
    )
    return {
        "platform":   "小红书",
        "status":     "manual_required",
        "search_url": search_url,
        "snippets":   [],
        "raw_text":   "",
        "sentiment":  {},
        "note":       "小红书需登录态，提供搜索直链，请手动参考",
    }


def fetch_bilibili(query: str) -> dict:
    """B站视频口碑（测评/开箱视频标题）"""
    import re
    encoded = urllib.parse.quote(f"{query} 开箱 测评")
    url = f"https://search.bilibili.com/all?keyword={encoded}&order=click"
    html = safe_get(url)
    jitter_sleep()

    result = {
        "platform": "B站",
        "status": "success" if html else "failed",
        "search_url": url,
        "snippets": [],
        "raw_text": "",
        "sentiment": {},
    }
    if html:
        titles = re.findall(r'"title":"([^"]{10,100})"', html)[:8]
        result["snippets"] = titles
        result["raw_text"] = " ".join(titles)
    return result


# ── 综合评分 ──────────────────────────────────────────────────────────────

def aggregate_score(product_name: str, platform_results: list) -> dict:
    """
    汇总各平台口碑，调用 LLM 进行综合情感分析。
    LLM 模式：将所有平台文本合并后做一次统一分析（更准确，节省 API 调用）。
    降级模式：每平台独立关键词分析后平均。
    """
    # 收集所有有效文本
    all_snippets = []
    for r in platform_results:
        all_snippets.extend(r.get("snippets", []))

    # 统一 LLM 分析（最准确的方式）
    llm_backend_available = any([
        bool(OPENAI_KEY),
        bool(DASHSCOPE_KEY),
        True,  # Ollama 本地尝试
    ])

    if all_snippets and llm_backend_available:
        overall_sentiment = llm_analyze_sentiment(product_name, all_snippets)
    else:
        overall_sentiment = {"score": 3.0, "positive_keywords": [], "negative_keywords": [],
                              "method": "no_data"}

    # 各平台也做情感分析（用于详情展示）
    for r in platform_results:
        if r.get("snippets") and r["status"] not in ("manual_required", "failed"):
            r["sentiment"] = llm_analyze_sentiment(product_name, r["snippets"])
        elif r.get("snippets"):
            r["sentiment"] = keyword_analyze_sentiment(r.get("raw_text", ""))

    # 典型评论摘录（各平台取第一条）
    typical_reviews = []
    for r in platform_results:
        if r.get("snippets"):
            typical_reviews.append({
                "platform": r["platform"],
                "text":     r["snippets"][0],
            })

    return {
        "overall_score":       overall_sentiment.get("score", 3.0),
        "positive_keywords":   overall_sentiment.get("positive_keywords", []),
        "negative_keywords":   overall_sentiment.get("negative_keywords", []),
        "sentiment_summary":   overall_sentiment.get("sentiment_summary", ""),
        "buy_advice":          overall_sentiment.get("buy_advice", ""),
        "reasoning":           overall_sentiment.get("reasoning", ""),
        "typical_positive":    overall_sentiment.get("typical_positive", ""),
        "typical_negative":    overall_sentiment.get("typical_negative", ""),
        "typical_reviews":     typical_reviews,
        "analysis_method":     overall_sentiment.get("method", "unknown"),
    }


# ── 主入口 ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="用户口碑聚合 Phase 2 - PriceHunter")
    parser.add_argument("--query", required=True, help="商品名称")
    parser.add_argument(
        "--sources",
        default="zhihu,jd,xiaohongshu,bilibili",
        help="口碑来源，逗号分隔",
    )
    args = parser.parse_args()

    # 打印 LLM 配置状态
    llm_configured = bool(OPENAI_KEY) or bool(DASHSCOPE_KEY)
    print(
        f"[review_summary] LLM 后端: {LLM_BACKEND}/{LLM_MODEL} "
        f"({'✓ 已配置' if llm_configured else '⚠ 未配置API密钥，尝试本地 Ollama / 降级关键词'})",
        file=sys.stderr,
    )

    sources = set(args.sources.split(","))
    fetchers = {
        "zhihu":       fetch_zhihu,
        "jd":          fetch_jd_reviews,
        "xiaohongshu": fetch_xiaohongshu,
        "bilibili":    fetch_bilibili,
    }

    platform_results = []
    for src_id, fn in fetchers.items():
        if src_id in sources:
            try:
                r = fn(args.query)
                platform_results.append(r)
            except Exception as e:
                platform_results.append({
                    "platform": src_id,
                    "status":   "error",
                    "error":    str(e),
                    "snippets": [],
                })

    summary = aggregate_score(args.query, platform_results)

    output = {
        "query":            args.query,
        "crawled_at":       datetime.now().isoformat(),
        "phase":            "2.0",
        "llm_backend":      f"{LLM_BACKEND}/{LLM_MODEL}",
        "summary":          summary,
        "platform_details": platform_results,
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
