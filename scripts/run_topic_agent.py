#!/usr/bin/env python3
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import re
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


USER_AGENT = "self-media-topic-agent/0.1 (+Codex skill)"
TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}
NOISE_KEYWORDS = {
    "小红书": ["闺蜜", "放假", "婚戒", "哈哈", "追剧", "腹肌奶茶", "穿搭", "沉香如屑", "氛围感", "恋爱", "宝宝"],
    "抖音": ["旅行", "穿搭", "世界杯", "婚礼", "大学生", "美食", "功夫女足", "溪降"],
}
PLATFORM_PRESETS = {
    "xiaohongshu": {
        "label": "小红书",
        "discovery": "xiaohongshu",
        "site_hint": "site:xiaohongshu.com/explore",
        "query_suffix": "小红书 爆款 收藏 评论",
    },
    "douyin": {
        "label": "抖音",
        "discovery": "douyin",
        "site_hint": "site:douyin.com",
        "query_suffix": "抖音 爆款 热门 点赞",
    },
    "bilibili": {
        "label": "B站",
        "discovery": "sogou",
        "site_hint": "site:bilibili.com/video",
        "query_suffix": "B站 热门 爆款 高播放",
    },
    "zhihu": {
        "label": "知乎",
        "discovery": "sogou",
        "site_hint": "site:zhihu.com",
        "query_suffix": "知乎 高赞 热门",
    },
    "weixin": {
        "label": "公众号",
        "discovery": "sogou",
        "site_hint": "site:mp.weixin.qq.com",
        "query_suffix": "公众号 爆文 阅读",
    },
    "web": {
        "label": "中文网页",
        "discovery": "sogou",
        "query_suffix": "案例 教程 趋势 热门",
    },
}


def main() -> int:
    args = parse_args()
    output_dir = resolve_output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    library = load_library(args.content_dir, args.content_file)
    if args.manual_text_file:
        library.extend(load_manual_text_file(args.manual_text_file))

    platforms = [part.strip() for part in args.platforms.split(",") if part.strip()]
    candidates = discover_candidates(args.direction, platforms, args.limit)

    llm_config = {
        "api_base": args.api_base,
        "api_key": os.environ.get(args.api_key_env, ""),
        "model": args.model,
    }

    topics = generate_topics(args.direction, library, candidates, llm_config)
    selected_topic = topics[min(max(args.draft_topic_index, 0), len(topics) - 1)] if topics else None
    draft = generate_draft(args.direction, selected_topic, library, candidates, llm_config) if selected_topic else {}

    write_json(output_dir / "library.json", library)
    write_json(output_dir / "viral_candidates.json", candidates)
    write_json(output_dir / "topics.json", topics)
    write_json(output_dir / "draft.json", draft)
    report_path = output_dir / "report.md"
    report_path.write_text(render_report(args.direction, library, candidates, topics, draft, llm_config), encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "direction": args.direction,
        "output_dir": str(output_dir),
        "library_count": len(library),
        "candidate_count": len(candidates),
        "topic_count": len(topics),
        "report_path": str(report_path),
        "draft_path": str(output_dir / "draft.json"),
        "used_llm": bool(llm_config["api_key"]),
    }, ensure_ascii=False, indent=2))
    return 0


def parse_args():
    parser = argparse.ArgumentParser(description="Run the self-media topic agent workflow.")
    parser.add_argument("--direction", required=True, help="Content direction to analyze.")
    parser.add_argument("--content-dir", action="append", default=[], help="Folder containing markdown/text content.")
    parser.add_argument("--content-file", action="append", default=[], help="Single markdown/text file to import.")
    parser.add_argument("--manual-text-file", help="Path to a text file created from pasted content.")
    parser.add_argument("--platforms", default="xiaohongshu,douyin,weixin,web", help="Comma-separated platform keys.")
    parser.add_argument("--limit", type=int, default=12, help="Maximum viral candidates to keep.")
    parser.add_argument("--output-dir", help="Explicit output directory.")
    parser.add_argument(
        "--api-base",
        default=os.environ.get("TOPIC_AGENT_API_BASE") or os.environ.get("OPENAI_BASE_URL") or "https://api.deepseek.com",
        help="OpenAI-compatible base URL.",
    )
    parser.add_argument(
        "--api-key-env",
        default=os.environ.get("TOPIC_AGENT_API_KEY_ENV", "DEEPSEEK_API_KEY"),
        help="Environment variable holding the API key.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("TOPIC_AGENT_MODEL") or os.environ.get("OPENAI_MODEL") or "deepseek-chat",
        help="Model name.",
    )
    parser.add_argument("--draft-topic-index", type=int, default=0, help="Which generated topic to draft.")
    return parser.parse_args()


def resolve_output_dir(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    return Path.cwd() / "outputs" / "topic-agent" / timestamp


def load_library(content_dirs, content_files):
    entries = []
    for folder in content_dirs:
        root = Path(folder).expanduser().resolve()
        if not root.is_dir():
            raise SystemExit(f"内容文件夹不存在: {root}")
        for file_path in sorted(root.rglob("*")):
            if file_path.suffix.lower() not in TEXT_EXTENSIONS or not file_path.is_file():
                continue
            text = file_path.read_text(encoding="utf-8").strip()
            if not text:
                continue
            entries.append(make_library_entry(file_path.name, str(file_path), text, "content-dir"))
    for file_name in content_files:
        file_path = Path(file_name).expanduser().resolve()
        if not file_path.is_file():
            raise SystemExit(f"内容文件不存在: {file_path}")
        text = file_path.read_text(encoding="utf-8").strip()
        if text:
            entries.append(make_library_entry(file_path.name, str(file_path), text, "content-file"))
    return entries


def load_manual_text_file(file_name):
    file_path = Path(file_name).expanduser().resolve()
    text = file_path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [make_library_entry(file_path.name, str(file_path), text, "manual-text-file")]


def make_library_entry(title, path_value, content, source):
    return {
        "id": create_id("lib"),
        "title": title,
        "path": path_value,
        "source": source,
        "excerpt": content[:800],
        "content": content,
    }


def discover_candidates(direction, platforms, limit):
    all_candidates = []
    per_platform = max(3, int(limit / max(len(platforms), 1)) + 1)
    for platform_key in platforms:
        preset = PLATFORM_PRESETS.get(platform_key)
        if not preset:
            continue
        discovery = preset.get("discovery", "sogou")
        if discovery == "xiaohongshu":
            all_candidates.extend(fetch_xiaohongshu_samples(direction, platform_key, preset["label"], per_platform))
            continue
        if discovery == "douyin":
            all_candidates.extend(fetch_douyin_samples(direction, platform_key, preset["label"], per_platform))
            continue
        all_candidates.extend(fetch_sogou_samples(direction, platform_key, preset, per_platform))
    ranked = sorted(all_candidates, key=lambda item: item["score"], reverse=True)
    deduped = []
    seen = set()
    for item in ranked:
        key = (item["platform"], item["title"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:limit]


def fetch_xiaohongshu_samples(direction, platform_key, platform_label, limit):
    public_feed_url = "https://r.jina.ai/http://www.xiaohongshu.com/explore?channel_id=homefeed_recommend"
    try:
        markdown = fetch_text(public_feed_url)
    except urllib.error.URLError as exc:
        return [{
            "id": create_id("viral"),
            "direction": direction,
            "platform": platform_key,
            "platform_label": platform_label,
            "title": f"{platform_label} 抓取失败",
            "url": public_feed_url,
            "snippet": str(exc),
            "score": 0,
        }]
    items = []
    seen = set()
    for title, link in extract_markdown_links(markdown, domain_hint="xiaohongshu.com/explore"):
        title = cleanup_markdown_text(title)
        if not title or title.startswith("!") or "channel_id=" in link or "channel_type=" in link:
            continue
        relevance = keyword_relevance(direction, title, "小红书 公共推荐流", platform_label)
        if relevance < 2:
            continue
        key = (title, link)
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "id": create_id("viral"),
            "direction": direction,
            "platform": platform_key,
            "platform_label": platform_label,
            "title": title,
            "url": link,
            "snippet": "来自小红书公共推荐流的高曝光笔记样本。",
            "score": score_candidate(direction, title, "小红书 公共推荐流") + relevance,
        })
        if len(items) >= limit:
            break
    if len(items) >= max(2, min(4, limit)):
        return items
    fallback_preset = dict(PLATFORM_PRESETS["xiaohongshu"])
    fallback_preset["discovery"] = "sogou"
    fallback_items = fetch_sogou_samples(direction, platform_key, fallback_preset, limit, min_relevance=2)
    for item in fallback_items:
        key = (item["title"], item["url"])
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
        if len(items) >= limit:
            break
    return items


def fetch_douyin_samples(direction, platform_key, platform_label, limit):
    items = []
    seen = set()
    hot_quota = max(2, limit // 2)
    for item in fetch_douyin_hot_samples(direction, platform_key, platform_label, hot_quota):
        key = (item["title"], item["url"])
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
    search_quota = max(2, limit - len(items))
    for item in fetch_douyin_search_samples(direction, platform_key, platform_label, search_quota):
        key = (item["title"], item["url"])
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
        if len(items) >= limit:
            break
    return items[:limit]


def fetch_douyin_hot_samples(direction, platform_key, platform_label, limit):
    hot_url = "https://r.jina.ai/http://www.douyin.com/hot"
    try:
        markdown = fetch_text(hot_url)
    except urllib.error.URLError as exc:
        return [{
            "id": create_id("viral"),
            "direction": direction,
            "platform": platform_key,
            "platform_label": platform_label,
            "title": f"{platform_label} 抓取失败",
            "url": hot_url,
            "snippet": str(exc),
            "score": 0,
        }]
    items = []
    for rank, title, link, heat in extract_douyin_hot_items(markdown):
        title = cleanup_markdown_text(title)
        snippet = f"抖音热榜第{rank}名，热度 {heat}。" if heat else f"抖音热榜第{rank}名。"
        relevance = keyword_relevance(direction, title, snippet, platform_label)
        if relevance < 1 and contains_noise_keyword(title, platform_label):
            continue
        items.append({
            "id": create_id("viral"),
            "direction": direction,
            "platform": platform_key,
            "platform_label": platform_label,
            "title": title,
            "url": link,
            "snippet": snippet,
            "score": score_candidate(direction, title, snippet) + relevance,
        })
        if len(items) >= limit:
            break
    return items


def fetch_douyin_search_samples(direction, platform_key, platform_label, limit):
    preset = {
        "label": platform_label,
        "site_hint": PLATFORM_PRESETS["douyin"].get("site_hint", "site:douyin.com"),
        "query_suffix": "抖音",
    }
    items = fetch_sogou_samples(direction, platform_key, preset, limit, min_relevance=1)
    for item in items:
        item["snippet"] = trim(f"{item['snippet']} 渠道：抖音搜索结果。", 180)
        item["score"] += 1
    return items


def fetch_sogou_samples(direction, platform_key, preset, limit, min_relevance=0):
    platform_label = preset["label"]
    items = []
    seen = set()
    for query in build_platform_queries(direction, preset)[:3]:
        search_url = "https://r.jina.ai/http://www.sogou.com/web?query=" + urllib.parse.quote(query)
        try:
            markdown = fetch_text(search_url)
        except urllib.error.URLError:
            continue
        for item in extract_sogou_results(markdown, direction, platform_key, platform_label, min_relevance=min_relevance):
            key = (item["title"], item["url"])
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
            if len(items) >= limit:
                return items
    return items


def build_platform_queries(direction, preset):
    queries = []
    site_hint = preset.get("site_hint", "").strip()
    suffix = preset.get("query_suffix", "").strip()
    for variant in build_direction_variants(direction):
        query = " ".join(part for part in [site_hint, variant, suffix] if part).strip()
        if query and query not in queries:
            queries.append(query)
    return queries or [direction]


def build_direction_variants(direction):
    variants = []
    base = re.sub(r"\s+", " ", direction).strip()
    if base:
        variants.append(base)
    simplified = base
    for noise in ["怎么", "如何", "使用", "应用", "场景", "方案", "流程", "方法", "在", "的"]:
        simplified = simplified.replace(noise, " ")
    tokens = [token.strip() for token in re.split(r"[\s,，、/|]+", simplified) if token.strip()]
    if tokens:
        compact = " ".join(tokens)
        if compact not in variants:
            variants.append(compact)
        if len(tokens) >= 2:
            combos = [
                " ".join(tokens[:2]),
                " ".join(tokens[-2:]),
                "".join(tokens[:2]),
            ]
            for combo in combos:
                combo = combo.strip()
                if combo and combo not in variants:
                    variants.append(combo)
    return variants


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def extract_markdown_links(markdown, domain_hint=""):
    pattern = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s\)]+)\)")
    items = []
    for title, url in pattern.findall(markdown):
        if domain_hint and domain_hint not in url:
            continue
        items.append((title, url))
    return items


def extract_douyin_hot_items(markdown):
    items = []
    pattern = re.compile(
        r"^\*\s+(?:(\d+)|!\[Image[^\]]+\][^\n]*?)\s*### \[([^\]]+)\]\((https?://[^\)]+)\)(?:[^\n]*?(\d+(?:\.\d+)?K)\s*热度)?",
        re.M,
    )
    inferred_rank = 0
    for raw_rank, title, url, heat in pattern.findall(markdown):
        inferred_rank += 1
        rank = raw_rank or str(inferred_rank)
        items.append((rank, title, url, heat))
    return items


def extract_sogou_results(markdown, direction, platform_key, platform_label, min_relevance=0):
    heading_pattern = re.compile(r"^### \[([^\]]+)\]\((https?://[^\)]+)\)\s*$", re.M)
    items = []
    for match in heading_pattern.finditer(markdown):
        title = cleanup_markdown_text(match.group(1))
        url = match.group(2)
        if should_skip_sogou_title(title):
            continue
        if platform_label == "小红书" and should_skip_xiaohongshu_result(title, url):
            continue
        following = markdown[match.end():].splitlines()
        snippet_lines = []
        for line in following:
            line = cleanup_markdown_text(line)
            if not line:
                if snippet_lines:
                    break
                continue
            if line.startswith("### "):
                break
            if line.startswith("[") or line.startswith("!"):
                continue
            snippet_lines.append(line)
            if len(snippet_lines) >= 2:
                break
        snippet = trim(" ".join(snippet_lines), 180) or f"来自{platform_label}相关中文搜索结果。"
        relevance = keyword_relevance(direction, title, snippet, platform_label)
        if relevance < min_relevance:
            continue
        items.append({
            "id": create_id("viral"),
            "direction": direction,
            "platform": platform_key,
            "platform_label": platform_label,
            "title": title,
            "url": url,
            "snippet": snippet,
            "score": score_candidate(direction, title, snippet) + relevance,
        })
    return items


def should_skip_sogou_title(title):
    blacklist = [
        "在线协议",
        "高级搜索",
        "发现",
        "小红书招聘",
        "元宝",
        "Try Visual Search",
    ]
    return not title or any(word in title for word in blacklist)


def should_skip_xiaohongshu_result(title, url):
    blacklist = [
        "专业号登录",
        "千帆PC端",
        "电商官网",
        "商家",
        "官网",
    ]
    if any(word in title for word in blacklist):
        return True
    return "xiaohongshu.com/explore" not in url and "sogou.com/link" in url


def score_candidate(direction, title, description):
    text = f"{title} {description}"
    score = 0.0
    for token in build_direction_variants(direction):
        token = token.strip()
        if token and token.lower() in text.lower():
            score += 2
    for signal in ["爆款", "热门", "高赞", "收藏", "评论", "涨粉", "工作流", "教程", "案例"]:
        if signal in text:
            score += 1
    return score


def keyword_relevance(direction, title, description, platform_label=""):
    text = cleanup_markdown_text(f"{title} {description}")
    score = 0.0
    for token in build_direction_variants(direction):
        token = token.strip()
        if not token or len(token) <= 1:
            continue
        if token.lower() in text.lower():
            score += 1.5 if len(token) <= 3 else 2
    for token in split_direction_keywords(direction):
        if token and token in text:
            score += 1
    if contains_noise_keyword(text, platform_label):
        score -= 2
    return score


def split_direction_keywords(direction):
    raw = re.split(r"[\s,，、/|]+", re.sub(r"[^\w\u4e00-\u9fff]+", " ", direction))
    keywords = []
    for token in raw:
        token = token.strip()
        if len(token) <= 1:
            continue
        if token not in keywords:
            keywords.append(token)
    return keywords


def contains_noise_keyword(text, platform_label):
    return any(keyword in text for keyword in NOISE_KEYWORDS.get(platform_label, []))


def generate_topics(direction, library, candidates, llm_config):
    if llm_config["api_key"]:
        try:
            return generate_topics_with_llm(direction, library, candidates, llm_config)
        except Exception:
            pass
    return generate_topics_fallback(direction, library, candidates)


def generate_draft(direction, selected_topic, library, candidates, llm_config):
    if llm_config["api_key"]:
        try:
            return generate_draft_with_llm(direction, selected_topic, library, candidates, llm_config)
        except Exception:
            pass
    return generate_draft_fallback(direction, selected_topic, library, candidates)


def generate_topics_with_llm(direction, library, candidates, llm_config):
    library_digest = [{"id": item["id"], "title": item["title"], "excerpt": item["excerpt"]} for item in library[:8]]
    candidate_digest = [{
        "id": item["id"],
        "platform": item["platform_label"],
        "title": item["title"],
        "url": item["url"],
        "snippet": item["snippet"][:500],
    } for item in candidates[:12]]
    user_prompt = "\n".join([
        f"目标方向：{direction}",
        "创作者自己的内容摘要：",
        json.dumps(library_digest, ensure_ascii=False),
        "抓到的爆款样本：",
        json.dumps(candidate_digest, ensure_ascii=False),
        textwrap.dedent("""
        输出 JSON 对象：
        {
          "topics": [
            {
              "title": "选题标题",
              "why_now": "为什么现在值得做",
              "why_fit": "为什么适合这个创作者",
              "target_audience": "目标受众",
              "own_angle": "这个创作者自己的切入角度",
              "hook": "开头钩子",
              "outline": ["要点1","要点2","要点3"],
              "reference_ids": ["viral_xxx","lib_xxx"],
              "risk_note": "风险提示"
            }
          ]
        }
        产出 5 条题目。
        """).strip(),
    ])
    payload = llm_json(
        llm_config,
        system="你是中文自媒体选题总编。你的任务是基于爆款样本和创作者自己的内容，产出真正适合他的选题。只返回 JSON。",
        user=user_prompt,
    )
    topics = payload.get("topics") if isinstance(payload, dict) else None
    if not isinstance(topics, list):
        raise ValueError("LLM topics invalid")
    return [normalize_topic(item) for item in topics[:5]]


def generate_draft_with_llm(direction, selected_topic, library, candidates, llm_config):
    references = collect_references(selected_topic, library, candidates)
    user_prompt = "\n".join([
        f"目标方向：{direction}",
        f"最终选题：{json.dumps(selected_topic, ensure_ascii=False)}",
        "可参考的个人内容与爆款材料：",
        json.dumps(references, ensure_ascii=False),
        textwrap.dedent("""
        输出 JSON：
        {
          "title_options": ["标题1","标题2","标题3"],
          "cover_angle": "首图角度",
          "opening_hook": "开头钩子",
          "outline": ["段落1","段落2","段落3"],
          "draft": "完整初稿",
          "cta": "互动引导",
          "reuse_notes": "哪些地方借了爆款结构，哪些地方用了创作者自己的材料"
        }
        """).strip(),
    ])
    payload = llm_json(
        llm_config,
        system="你是中文内容操盘手。不是复写爆款，而是借它们的结构，写出更像这个创作者自己会发的内容。只返回 JSON。",
        user=user_prompt,
    )
    if not isinstance(payload, dict):
        raise ValueError("LLM draft invalid")
    payload["id"] = create_id("draft")
    payload["topic_id"] = selected_topic["id"]
    payload["direction"] = direction
    return payload


def generate_topics_fallback(direction, library, candidates):
    angles = ["反常识拆解", "实操清单", "避坑复盘", "案例对照", "工具工作流"]
    topics = []
    for idx, angle in enumerate(angles):
        candidate = candidates[idx % max(len(candidates), 1)] if candidates else None
        own = library[idx % max(len(library), 1)] if library else None
        topics.append({
            "id": create_id("topic"),
            "title": f"{direction}：用{angle}做出你的版本",
            "why_now": f"最近样本里反复出现「{trim(candidate['title'], 24)}」这类内容，说明这个方向正在被讨论。" if candidate else "这个方向最近有持续热度，值得先做一版验证。",
            "why_fit": f"你自己的内容里已经有「{own['title']}」这类材料，可以直接拿来讲更强的结论。" if own else "先跑一版方向选题，后续补个人内容会更准。",
            "target_audience": f"对「{direction}」感兴趣，但缺少具体方法的人",
            "own_angle": f"不要泛讲趋势，优先用你自己的「{own['title']}」经验来落地。" if own else "不要只讲概念，优先写成可执行步骤。",
            "hook": f"别再只看别人怎么火了，{direction} 这个方向你其实可以这样做。",
            "outline": [
                "先讲这个方向里现在最容易被讨论的点",
                "再讲你自己的真实经验或案例",
                "最后给一个普通人能立刻照做的方法",
            ],
            "reference_ids": [value for value in [candidate["id"] if candidate else "", own["id"] if own else ""] if value],
            "risk_note": "注意不要变成泛泛工具盘点，要尽量带自己的结论。",
        })
    return topics


def generate_draft_fallback(direction, selected_topic, library, candidates):
    references = collect_references(selected_topic, library, candidates)
    support_line = references[0]["excerpt"] if references else "这里补一个你自己的真实案例。"
    return {
        "id": create_id("draft"),
        "topic_id": selected_topic["id"],
        "direction": direction,
        "title_options": [
            selected_topic["title"],
            f"{direction} 别再空讲了，直接这样做",
            f"我怎么把 {direction} 这件事做成可复制流程",
        ],
        "cover_angle": "强调不是追爆款，而是把爆款结构变成自己的表达。",
        "opening_hook": selected_topic.get("hook", f"很多人看了很多 {direction} 的爆款，最后还是不会做。"),
        "outline": selected_topic.get("outline", []),
        "draft": "\n".join([
            selected_topic.get("hook", f"很多人看了很多 {direction} 的内容，但问题一直没解决。"),
            "",
            f"我最近看了一圈这个方向的爆款，发现它们真正有效的不是某个标题，而是它们都在帮用户快速跨过第一步。",
            "",
            "所以如果让我做，我不会再重复讲趋势，我会直接讲我自己怎么做，哪里踩过坑，最后怎么把事情跑顺。",
            "",
            support_line,
            "",
            "如果你也想试，最小动作不是把所有工具装一遍，而是先选一个你今天就能动手的场景，先把它做通。",
            "",
            "等第一步跑通，再往后加自动化、加模板、加复盘。",
        ]),
        "cta": "如果你正在做这个方向，卡住的是哪一步？",
        "reuse_notes": "当前是无模型兜底稿，结构参考了样本池，但表达尽量保留你的个人视角。",
    }


def collect_references(selected_topic, library, candidates):
    wanted = set(selected_topic.get("reference_ids", []))
    references = []
    for item in library + candidates:
        if item["id"] not in wanted:
            continue
        references.append({
            "id": item["id"],
            "title": item["title"],
            "source": item.get("source") or item.get("platform_label", ""),
            "excerpt": item.get("excerpt") or item.get("snippet", ""),
            "url": item.get("url", ""),
        })
    return references


def llm_json(llm_config, system, user):
    url = llm_config["api_base"].rstrip("/") + "/chat/completions"
    payload = {
        "model": llm_config["model"],
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {llm_config['api_key']}",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


def render_report(direction, library, candidates, topics, draft, llm_config):
    lines = [
        f"# 自媒体选题 Agent 报告",
        "",
        f"- 方向：`{direction}`",
        f"- 个人内容条数：`{len(library)}`",
        f"- 样本池条数：`{len(candidates)}`",
        f"- 选题条数：`{len(topics)}`",
        f"- 是否使用模型：`{'是' if llm_config['api_key'] else '否，当前为 fallback'}`",
        "",
        "## 推荐选题",
        "",
    ]
    for idx, topic in enumerate(topics[:5], start=1):
        lines.extend([
            f"### {idx}. {topic['title']}",
            "",
            f"- 为什么现在做：{topic.get('why_now', '')}",
            f"- 为什么适合你：{topic.get('why_fit', '')}",
            f"- 你的角度：{topic.get('own_angle', '')}",
            f"- 钩子：{topic.get('hook', '')}",
            f"- 风险：{topic.get('risk_note', '')}",
            "",
        ])
    if draft:
        lines.extend([
            "## 初稿",
            "",
            f"### 标题备选",
            "",
            *[f"- {title}" for title in draft.get("title_options", [])],
            "",
            "### 正文",
            "",
            draft.get("draft", ""),
            "",
        ])
    return "\n".join(lines).strip() + "\n"


def normalize_topic(item):
    return {
        "id": create_id("topic"),
        "title": str(item.get("title", "")).strip() or "未命名选题",
        "why_now": str(item.get("why_now", "")).strip(),
        "why_fit": str(item.get("why_fit", "")).strip(),
        "target_audience": str(item.get("target_audience", "")).strip(),
        "own_angle": str(item.get("own_angle", "")).strip(),
        "hook": str(item.get("hook", "")).strip(),
        "outline": item.get("outline", []) if isinstance(item.get("outline", []), list) else [],
        "reference_ids": item.get("reference_ids", []) if isinstance(item.get("reference_ids", []), list) else [],
        "risk_note": str(item.get("risk_note", "")).strip(),
    }


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def cleanup_markdown_text(text):
    text = strip_html(text)
    text = re.sub(r"!\[[^\]]*\]", " ", text)
    text = re.sub(r"\[[^\]]+\]\([^\)]+\)", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def text_or_empty(node):
    return node.text if node is not None and node.text is not None else ""


def trim(text, max_len):
    text = text or ""
    return text if len(text) <= max_len else text[:max_len] + "…"


def create_id(prefix):
    now = dt.datetime.now().strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}_{now}"


if __name__ == "__main__":
    sys.exit(main())
