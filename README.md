# 自媒体选题 Agent

这是一个给 Codex 使用的本地 skill，用来把这条链路直接跑通：

1. 抓某个内容方向的公开爆款/热门样本
2. 读取创作者自己的文章、笔记、口播稿
3. 结合“方向样本 + 个人内容”生成选题
4. 继续产出一版内容初稿

它适合下面这类需求：

- 帮我找这个方向的爆款选题
- 结合我自己的内容，做更适合我的题目
- 不要只给灵感，要给我能继续写的题目和初稿
- 把整个自媒体选题流程直接跑一遍

## 目录说明

- `SKILL.md`：给 Codex 读取的核心工作流说明
- `scripts/run_topic_agent.py`：执行完整流程的主脚本
- `references/call-patterns.md`：常见调用方式
- `references/output-layout.md`：输出目录和结果文件说明
- `agents/openai.yaml`：skill 的 UI 元数据

## 安装方式

如果你是把这个 skill 放到本机给 Codex 用，推荐直接放进：

```bash
~/.codex/skills/self-media-topic-agent
```

如果已经 clone 到本地，也可以直接在当前目录使用，不一定非要重新安装。

## 基本用法

### 1. 给一个方向 + 一个内容文件夹

```bash
python3 scripts/run_topic_agent.py \
  --direction "AI 工作流" \
  --content-dir /absolute/path/to/content-folder
```

### 2. 给一个方向 + 单个内容文件

```bash
python3 scripts/run_topic_agent.py \
  --direction "老板管理" \
  --content-file /absolute/path/to/article.md
```

### 3. 指定平台范围

```bash
python3 scripts/run_topic_agent.py \
  --direction "短视频变现" \
  --content-dir /absolute/path/to/content-folder \
  --platforms xiaohongshu,bilibili,zhihu
```

## 输出结果

脚本默认会在当前工作目录创建：

```bash
outputs/topic-agent/<timestamp>/
```

里面通常会有：

- `library.json`
- `viral_candidates.json`
- `topics.json`
- `draft.json`
- `report.md`

最适合先读的是 `report.md`。

## 模型配置

这个 skill 支持本地环境变量配置模型，不把 key 写进仓库。

优先读取：

- `TOPIC_AGENT_API_KEY_ENV`
- `TOPIC_AGENT_API_BASE`
- `TOPIC_AGENT_MODEL`

如果这些没配，再回退到常见的 OpenAI 兼容变量。

如果没有可用 key，脚本仍然会走 fallback 流程，先产出一版样本、选题和初稿，只是质量会弱一些。

## 设计原则

这个 skill 的核心不是“抄爆款”，而是：

- 借爆款结构
- 保留创作者自己的表达
- 输出更适合这个人去讲的话题和内容

所以它更像一个“选题工作流 skill”，不是单纯的热搜抓取器，也不是自动洗稿工具。
