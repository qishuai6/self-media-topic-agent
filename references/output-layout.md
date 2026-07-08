# 输出结构

脚本默认输出到：

`outputs/topic-agent/<timestamp>/`

## 文件

1. `library.json`
   - 导入的个人内容库
   - 每条含 `id`、`title`、`path`、`excerpt`、`content`

2. `viral_candidates.json`
   - 当前方向抓到的样本池
   - 每条含 `platform`、`title`、`url`、`snippet`、`score`

3. `topics.json`
   - 生成后的选题清单
   - 每条含 `why_now`、`why_fit`、`own_angle`、`hook`、`outline`

4. `draft.json`
   - 当前默认选题对应的一版初稿

5. `report.md`
   - 适合直接读的 Markdown 总结

## 推荐使用方式

1. 先打开 `report.md` 看结论
2. 再用 `topics.json` / `draft.json` 做后续二次编辑
3. 如果用户要继续某一条题目，保留整个输出目录，避免重复抓样本
