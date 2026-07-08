---
name: self-media-topic-agent
description: 把“找爆款方向、结合创作者自己的内容、生成适合他的选题和内容初稿”做成一条可执行链路。用于“帮我找这个方向的爆款选题”“结合我自己的文章、笔记、口播稿做选题”“别只给我灵感，要给我能写的题目和初稿”“把这个自媒体选题流程直接跑一遍”等任务。支持读取本地 markdown 或 txt 内容库，抓取小红书、抖音、公众号、知乎、B站、中文网页相关样本，并输出样本池、选题清单、内容初稿和 Markdown 报告。
---

# 自媒体选题 Agent

## 概述

这个 skill 的目标不是做一个 UI，而是让 Codex 能直接把整套选题流程跑完。

默认交付 4 类产物：

1. 样本池：当前方向抓到的爆款/热门信号
2. 选题清单：结合你的内容后筛出来的 5 条题目
3. 内容初稿：至少 1 条可直接改写的成稿
4. 报告文件：保存在 workspace 里，方便后续复盘和复用

## 什么时候直接用

以下情况直接走这个 skill，不要先拆成网页或手工研究：

1. 用户已经给了明确方向，比如“AI 工作流”“老板管理”“短视频变现”
2. 用户说要结合“我自己的内容”“我过去写过的东西”“我的口播稿”
3. 用户要的不是泛泛 brainstorm，而是“跑一遍流程，给我结果”
4. 用户接受先用公开样本信号跑一版，而不是必须走平台后台接口或登录态

## 工作流

### 1. 先补齐最小输入

至少拿到下面 2 项：

1. `direction`：用户想做的内容方向
2. 个人内容来源：
   - 本地文件夹
   - 单个本地文件
   - 用户直接粘贴的一段内容

如果用户没给内容来源，但明确说“结合我的内容”，先追问内容位置。  
如果用户只是想先看一版方向结果，可以先跑样本池和兜底选题，再提醒他补个人内容会更准。

### 2. 跑脚本，不手工拼流程

主入口脚本：

```bash
python3 /Users/qishuai/.codex/skills/self-media-topic-agent/scripts/run_topic_agent.py \
  --direction "AI 工作流" \
  --content-dir /absolute/path/to/content-folder
```

如果用户给的是单文件：

```bash
python3 /Users/qishuai/.codex/skills/self-media-topic-agent/scripts/run_topic_agent.py \
  --direction "AI 工作流" \
  --content-file /absolute/path/to/article.md
```

如果用户只给了一段文字，先写到当前 workspace 的临时文件，再传给脚本，不要把大段正文硬塞进命令行。

### 3. 默认输出

脚本默认在当前 workspace 下创建：

`outputs/topic-agent/<timestamp>/`

里面至少包含：

1. `library.json`
2. `viral_candidates.json`
3. `topics.json`
4. `draft.json`
5. `report.md`

除非用户明确说不要落盘，否则保留这些文件，方便后续继续做。

### 4. 输出给用户时的口径

最终回复不要变成脚本运行日志。默认按这个顺序返回：

1. 这次抓了哪些平台、拿到了多少样本
2. 最值得做的 3-5 条选题
3. 你推荐先写哪一条，为什么
4. 初稿已经保存在哪里

如果脚本走的是无模型兜底结果，要明确说这是 fallback 结果，并提示用户配置本地模型环境变量后可得到更强版本。

当前默认抓取层说明：

1. `xiaohongshu`：抓小红书公共推荐流里的真实笔记标题和 URL，并做方向关键词相关性过滤
2. `douyin`：抓抖音热榜，同时补抖音搜索结果渠道，双通道合并
3. `weixin` / `web` / `zhihu` / `bilibili`：走搜狗中文搜索结果，适合中文行业话题补样本

## 关键约束

1. 这个 skill 的核心是“借爆款结构，不抄爆款文案”。
2. 选题必须同时满足：
   - 当前方向有人做
   - 适合这个创作者讲
   - 有明确切入角度
3. 不要把“平台样本标题”直接当最终选题交付。
4. 没有个人内容时，可以先出方向版选题，但要主动提示“像不像你”这一步还没做满。

## 参数补充

常用可选参数：

```bash
--platforms xiaohongshu,douyin,weixin,web
--limit 12
--output-dir /absolute/path/to/output
--model glm-4-flash
--api-key-env GLM_API_KEY
```

平台键见 [references/call-patterns.md](./references/call-patterns.md)。

## 资源

1. `scripts/run_topic_agent.py`：跑完整链路
2. [references/call-patterns.md](./references/call-patterns.md)：常见调用方式和参数
3. [references/output-layout.md](./references/output-layout.md)：输出文件结构和字段说明
