# 自媒体选题 Agent

这是一个给 Codex 用的本地 skill，目标不是“查几个热搜词”，而是把一整条内容策划链路跑完：

1. 抓某个方向正在被讨论的公开样本
2. 读取创作者自己的文章、笔记、口播稿
3. 把“公开样本 + 个人内容”合在一起做选题判断
4. 产出 5 条可做选题和 1 条内容初稿

它适合下面这类任务：

- 帮我找这个方向的爆款选题
- 结合我自己的内容，给我更适合我的题目
- 不要只给灵感，要给我能继续写的题目和初稿
- 把整个自媒体选题流程直接跑一遍

## 这个 skill 现在能抓什么

当前版本的公开样本层分成 4 类：

1. 小红书：公共推荐流里的真实笔记标题和 URL
2. 抖音热榜：热榜话题、热度
3. 抖音搜索：通过中文搜索结果补抖音相关结果，和热榜一起组成“双通道”
4. 中文行业样本：公众号、中文网页、知乎、B 站等公开结果

这版专门加了两个控制：

1. 小红书关键词相关性过滤  
   用方向关键词给笔记打分，尽量把明显的泛娱乐、情绪化、穿搭类噪音拦在样本池外。

2. 抖音双通道  
   不再只看热榜，还会补“搜索结果渠道”，避免只抓到社会热点、抓不到垂类方向。

## 仓库结构

- `SKILL.md`：给 Codex 读取的主说明
- `scripts/run_topic_agent.py`：执行完整流程的主脚本
- `references/call-patterns.md`：常见调用方式
- `references/output-layout.md`：输出目录和字段说明
- `agents/openai.yaml`：skill UI 元数据

## 安装方式

如果你是给 Codex 本机安装，推荐直接放到：

```bash
~/.codex/skills/self-media-topic-agent
```

如果你只是想单独运行脚本，也可以直接 clone 这个仓库到任意目录后使用。

## 环境要求

- Python 3.10+
- 能访问公开网页
- 可选：一个 OpenAI 兼容模型 API

脚本本身只依赖 Python 标准库，不需要额外 pip 安装。

## 模型配置

这个 skill 支持本地环境变量配置，不把 key 写进仓库。

优先读取下面 3 个变量：

- `TOPIC_AGENT_API_KEY_ENV`
- `TOPIC_AGENT_API_BASE`
- `TOPIC_AGENT_MODEL`

其中 `TOPIC_AGENT_API_KEY_ENV` 的值是“真正存放 API Key 的环境变量名”。

例如用 GLM：

```bash
export GLM_API_KEY="你的key"
export TOPIC_AGENT_API_KEY_ENV="GLM_API_KEY"
export TOPIC_AGENT_API_BASE="https://open.bigmodel.cn/api/coding/paas/v4"
export TOPIC_AGENT_MODEL="glm-5.2"
```

如果这些没配，脚本会再回退到常见的 OpenAI 兼容变量。

如果完全没有可用 key，脚本仍然会产出结果，只是会走 fallback 逻辑，选题和初稿质量会弱一些。

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

### 3. 给一个方向 + 用户手动整理的一段文字

```bash
python3 scripts/run_topic_agent.py \
  --direction "物业 AI" \
  --manual-text-file /absolute/path/to/source.md
```

### 4. 指定平台范围

```bash
python3 scripts/run_topic_agent.py \
  --direction "短视频变现" \
  --content-dir /absolute/path/to/content-folder \
  --platforms xiaohongshu,douyin,weixin,web
```

### 5. 指定输出目录

```bash
python3 scripts/run_topic_agent.py \
  --direction "物业 AI" \
  --manual-text-file /absolute/path/to/source.md \
  --output-dir /absolute/path/to/output-folder
```

## 常用参数

- `--direction`：必填，内容方向
- `--content-dir`：可重复传入，读取整个内容文件夹
- `--content-file`：可重复传入，读取单个内容文件
- `--manual-text-file`：读取人工整理的一段文本
- `--platforms`：平台范围，默认 `xiaohongshu,douyin,weixin,web`
- `--limit`：样本池保留上限，默认 `12`
- `--output-dir`：显式指定输出目录
- `--api-key-env`：指定真实 API key 所在的环境变量名
- `--api-base`：OpenAI 兼容接口地址
- `--model`：模型名

## 输出结果

脚本默认会在当前工作目录创建：

```bash
outputs/topic-agent/<timestamp>/
```

里面通常会有：

- `library.json`：导入的个人内容
- `viral_candidates.json`：样本池
- `topics.json`：5 条候选选题
- `draft.json`：1 条内容初稿
- `report.md`：最适合直接看的汇总报告

建议优先看 `report.md`，再根据需要打开 `viral_candidates.json` 检查样本质量。

## 一个真实使用方式

比如你要做“物业做 AI，先从报事报修和反馈汇总开始”这个方向：

1. 先把你已有的观点、采访记录、文章片段整理成一个 `source.md`
2. 运行：

```bash
python3 scripts/run_topic_agent.py \
  --direction "AI 在物业场景的使用" \
  --manual-text-file /absolute/path/to/source.md
```

3. 打开 `report.md`
4. 看样本池是不是足够相关
5. 从 5 条题目里选一条继续写口播稿、图文稿或视频脚本

## 当前边界

这版是“公开网页信号优先”的方案，不是平台登录态深爬版本，所以你要知道三个边界：

1. 小红书公开搜索登录墙比较重  
   当前主要依赖公共推荐流，再加关键词过滤，不保证每个垂类词都能拿到很多强相关小红书样本。

2. 抖音搜索结果通道当前是公开网页检索补样本  
   它能明显改善纯热榜的泛热点问题，但还不是登录态下的完整抖音站内搜索。

3. 如果方向特别垂直  
   公开样本可能仍然偏少，这时最好补自己的素材库，让后面的选题更准。

## 设计原则

这个 skill 的核心不是“抄爆款”，而是：

- 借爆款结构
- 保留创作者自己的表达
- 优先让内容更像“你会发的”，而不是“平台上已经有的”

所以它更像一个“选题工作流 skill”，不是单纯的热搜抓取器，也不是自动洗稿工具。
