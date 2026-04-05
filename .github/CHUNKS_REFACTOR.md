# Chunks 表职责简化说明

## 变更目标

简化 `chunks` 表的职责，明确其只负责保存正文切分结果，不承载文档级 metadata。

## 职责边界

### documents 表（文档级 metadata）
负责保存文档级别的元信息：
- `path` - 文档路径
- `title` - 文档标题
- `modified_time` - 修改时间
- `content_hash` - 内容哈希
- `status` - 处理状态
- `created_at` / `updated_at` - 时间戳

### chunks 表（正文切分结果）
只负责保存文档正文的切分片段：
- `id` - 主键
- `document_id` - 关联到 documents 表
- `chunk_index` - 片段序号
- `text` - 片段文本内容
- `start_offset` - 在原文中的起始位置（可选，用于追溯）
- `end_offset` - 在原文中的结束位置（可选，用于追溯）
- `token_estimate` - token 估算（可空）
- `section_label` - 所属章节标签（可选，预留用于未来章节识别）
- `created_at` - 创建时间

## Schema 变更

```sql
-- 新增字段
ALTER TABLE chunks ADD COLUMN start_offset INTEGER;
ALTER TABLE chunks ADD COLUMN end_offset INTEGER;
ALTER TABLE chunks ADD COLUMN section_label TEXT;

-- token_estimate 改为可空（schema 中已经是可空）
```

## 代码变更

### 1. Chunk 数据类
```python
@dataclass  
class Chunk:
    text: str
    index: int
    token_estimate: Optional[int] = None      # 改为可选
    start_offset: Optional[int] = None        # 新增
    end_offset: Optional[int] = None          # 新增
    section_label: Optional[str] = None       # 新增
```

### 2. 切分逻辑
`chunk_document()` 函数现在会：
- 计算每个 chunk 在原文中的 `start_offset` 和 `end_offset`
- 保留追溯原文的能力
- 为未来的章节识别预留 `section_label` 字段

### 3. 数据库插入
更新 INSERT 语句包含新字段。

## 设计原则

1. **单一职责**：chunks 只管切分，不管文档属性
2. **可追溯性**：通过 offset 可以定位到原文
3. **可扩展性**：预留 section_label 但不强制使用
4. **简单优先**：不引入复杂的 chunk_type 系统

## 验证结果

✅ Schema 正确创建所有字段  
✅ offset 计算准确，可以还原原文  
✅ 向后兼容：token_estimate 和 section_label 可为空  
✅ 测试通过

## Migration 影响

对于现有数据库：
- 需要运行 `python main.py --init` 重建数据库
- 或手动执行 ALTER TABLE 添加新字段（已有数据的 offset 会是 NULL）

---

日期：2026-04-05  
变更类型：refactor (schema)
