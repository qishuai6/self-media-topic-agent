# 常见调用方式

## 1. 给一个方向 + 一个内容文件夹

```bash
python3 /Users/qishuai/.codex/skills/self-media-topic-agent/scripts/run_topic_agent.py \
  --direction "AI 工作流" \
  --content-dir /absolute/path/to/content-folder
```

## 2. 给一个方向 + 多个内容来源

```bash
python3 /Users/qishuai/.codex/skills/self-media-topic-agent/scripts/run_topic_agent.py \
  --direction "老板管理" \
  --content-dir /absolute/path/to/articles \
  --content-file /absolute/path/to/one-note.md
```

## 3. 指定平台范围

```bash
python3 /Users/qishuai/.codex/skills/self-media-topic-agent/scripts/run_topic_agent.py \
  --direction "短视频变现" \
  --content-dir /absolute/path/to/content-folder \
  --platforms xiaohongshu,bilibili,zhihu
```

## 平台键

1. `xiaohongshu`
2. `bilibili`
3. `zhihu`
4. `weixin`
5. `web`

## 模型配置

默认读取：

1. `TOPIC_AGENT_API_KEY_ENV`
2. `TOPIC_AGENT_API_BASE`
3. `TOPIC_AGENT_MODEL`
4. 如果以上未配置，再回退到 `DEEPSEEK_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`

如果没有 key，脚本会退回本地 heuristics，仍然能产出一版样本、选题和初稿。
