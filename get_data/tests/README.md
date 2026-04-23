# 测试运行说明

## 目录结构

```
tests/
├── __init__.py
├── crawler/           # 爬虫测试
│   ├── __init__.py
│   └── test_attachment_extract.py  # 附件链接提取测试
├── etl/               # 数据抽取测试
│   ├── __init__.py
│   ├── test_structured_extract.py  # LLM 结构化抽取测试
│   └── test_chunks_generation.py   # Chunks 生成测试
└── utils/             # 工具函数测试
    └── __init__.py
```

## 运行测试

### 运行单个测试文件

```bash
# 附件链接提取测试
python tests/crawler/test_attachment_extract.py

# LLM 结构化抽取测试
python tests/etl/test_structured_extract.py

# Chunks 生成测试
python tests/etl/test_chunks_generation.py
```

### 运行所有测试

```bash
# 使用 unittest
python -m unittest discover -s tests

# 或使用 pytest（如果安装）
pytest tests/
```

## 测试覆盖

| 模块 | 测试文件 | 说明 |
|------|----------|------|
| crawler | test_attachment_extract.py | 测试 bizDownload 链接的 UUID 提取和下载链接生成 |
| etl | test_structured_extract.py | 测试 LLM 结构化输出格式、contact_chunk、requirement_chunks |
| etl | test_chunks_generation.py | 测试 tender_chunks 的 chunk_type 和元数据格式 |

## 添加新测试

1. 在对应目录下创建 `test_*.py` 文件
2. 测试函数命名为 `test_*` 开头
3. 使用 `assert` 进行断言
4. 在文件末尾添加 `run_all_tests()` 函数

示例：
```python
def test_example():
    """测试示例"""
    assert 1 + 1 == 2
    print("[OK] test_example 通过")
```
