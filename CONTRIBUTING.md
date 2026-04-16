# 贡献指南

## 开始前先读

- [README.md](/D:/Apps/Python/lab/personal_prompt/README.md)
- [docs/architecture.md](/D:/Apps/Python/lab/personal_prompt/docs/architecture.md)
- [TESTING.md](/D:/Apps/Python/lab/personal_prompt/TESTING.md)

## 项目边界

这是一个本地原型仓库。贡献应尽量保持在当前边界内。

不建议直接往主线里引入：

- 重型数据库
- Web 服务或 REST API
- 联网搜索
- 平台级重构
- 用户/权限系统

## 推荐的改动形状

- 改动保持小而清晰
- 不要把计划中的能力写成已实现事实
- 结构变更前先确认是否真的超出当前任务边界
- 命令、结构、schema、长期规则变了，就同步更新文档

## 最低验证要求

按改动范围运行最小相关集合：

```bash
python main.py --help
python test_extraction_schema.py
python -m unittest test_logging.py
python test_font_filtering.py
python main.py --skip-extraction
python main.py --stats
```

谨慎使用：

```bash
python main.py --init
```

更详细的验证路径见 [TESTING.md](/D:/Apps/Python/lab/personal_prompt/TESTING.md)。

## PR 应包含的信息

- 改了什么
- 为什么改
- 跑了哪些命令
- 哪些没有验证
- 更新了哪些文档，或者为什么没更新

## 哪些情况必须更新文档

以下内容发生变化时，应更新对应保留文档：

- 仓库入口命令或推荐运行方式
- 模块边界或数据流
- schema 或存储语义
- 验证流程
- 长期协作规则
