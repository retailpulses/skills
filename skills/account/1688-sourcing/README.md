# 1688-sourcing v6.0 技能包

## 技能概述

**1688 用照片筛同款** —— 通过图像搜索从 1688 找相似商品，结果默认保存到本地 CSV/JSON 文件。

**使用场景**:
- 亚马逊选品找 1688 货源
- 以图搜图找供应商
- 批量查询同款商品

## v6.0 版本核心变更

- ✅ **移除钉钉 AI 表格依赖** —— 不再需要 `dws aitable` CLI 与外部 BaseID/TableID
- ✅ **默认本地保存** —— 输出 `products_data_processed.csv` + `products_data_processed.json` 到脚本同目录 `output/`
- ✅ **CSV 使用 `utf-8-sig`** —— Excel 可直接打开中文不乱码
- ✅ **保留 19 字段 HARD-GATE** —— 字段缺失统一标记 `/`，不静默跳过
- ✅ **保留商品链接搜索回退** —— 商品名称构建 1688 站内搜索链接

## 文件结构

```
1688-sourcing/
├── SKILL.md                          # 技能主文件
├── README.md                         # 本文档
├── references/                       # 参考资料目录
│   ├── product-link-solution.md     # 商品链接搜索回退方案
│   ├── fixed-script.py               # 数据处理参考脚本（本地版）
│   ├── dom-selectors.md              # DOM 选择器详解
│   ├── field-mapping.md              # 19 字段映射规则
│   └── error-handling.md             # 错误码和调试
└── examples/                         # 示例文件
    ├── 1688_script.py                # 完整执行脚本（本地保存）
    └── products_data.json            # 示例数据（20 条记录）
```

## 使用方法

### 方式一：直接调用技能

当用户说:
- "帮我找这款商品的 1688 货源"
- "用这张图片在 1688 找同款"
- "以图搜图，找供应商"

技能自动执行:
1. 打开 1688 以图搜图页面
2. 提取 19 个字段的商品信息
3. 保存到本地 CSV / JSON
4. 返回完整文件路径

### 方式二：运行示例脚本

```bash
cd <你的本地路径>/1688-sourcing/examples
python3 1688_script.py
```

输出位置（脚本同目录的 `output/` 子目录）:
- `output/products_data_processed.json`
- `output/products_data_processed.csv`

### 方式三：在自己的代码里复用处理函数

```python
import sys
sys.path.insert(0, "<你的本地路径>/1688-sourcing/references")

from importlib import import_module
fixed_script = import_module("fixed-script")  # 文件名包含连字符，用 import_module

records = fixed_script.validate_products(
    products=[...],                  # 浏览器抓到的原始 dict 列表
    original_image_url="https://...", # 用户提供的原图 URL
)
fixed_script.save_results(records, output_dir="./my-output")
```

## 核心工作流

```
用户提供商品图片 URL
    ↓
打开 1688 以图搜图页面
    ↓
JavaScript 提取 19 个字段
    ↓
HARD-GATE 验证字段完整性
    ↓
构建商品搜索链接 (商品名称 → 1688 站内搜索 URL)
    ↓
写入本地 CSV + JSON 文件
    ↓
返回完整文件路径给用户
```

## 必填字段清单（19 个）

| 字段名 | 来源 | 验证规则 |
|--------|------|---------|
| 原始图片链接 | 用户提供 | 不能为空 |
| **1688 商品图链接** | `td:nth-of-type(1) img.src` | ⚠️ 必须提取，不能留空 |
| **商品链接** | 商品名称 → 搜索 URL | ⚠️ 不能为空，采用搜索替代 |
| 商品名称 | 单元格文本 | 截断至 200 字符 |
| 价格 / 销量 / 评分 等 | 对应列文本 | 缺失标记 `/` |

完整字段定义见 [`references/field-mapping.md`](./references/field-mapping.md)。

## HARD-GATE 机制

### Gate 1: 输入源确认
- ✅ 已确认输入模式（图片 URL or 本地图片）
- ✅ 已获取必要参数

### Gate 2: 字段完整性
```python
def validate_product(product, REQUIRED_FIELDS):
    missing = [f for f in REQUIRED_FIELDS if not product.get(f)]
    if missing:
        return False, f"缺少字段: {', '.join(missing)}"
    if not product.get("1688 商品图链接"):
        return False, "商品图链接提取失败"
    return True, "验证通过"
```

### Gate 3: 写入前确认
- ✅ 输出目录已确认（默认 `./output/`）
- ✅ 所有记录字段验证通过
- ✅ 数据格式符合 CSV/JSON 规范

### Gate 4: 交付确认
- ✅ 必须返回完整文件路径
- ❌ 禁止只返回相对路径或文件名

## 数据格式规范

### CSV 输出（推荐用于 Excel 查看）

- 编码: `utf-8-sig`（Excel 直接识别中文）
- 列顺序与 `REQUIRED_FIELDS` 一致
- URL 字段保存为纯字符串

### JSON 输出（推荐用于程序消费）

URL 字段以对象格式保存以便下游导入工具处理：

```json
[
  {
    "原始图片链接": {"link": "https://m.media-amazon.com/images/I/xxx.jpg", "text": ""},
    "1688 商品图链接": {"link": "https://cbu01.alicdn.com/O1CN01xxx.jpg", "text": ""},
    "商品链接": {"link": "https://s.1688.com/selloffer/offer_search.htm?keywords=...", "text": ""},
    "商品名称": "宠物垫子防水牛津布",
    "价格": "¥14.90",
    "起订量": "1",
    "供应商名称": "台前县车居汽车用品经营有限责任公司"
  }
]
```

## 错误处理

错误日志保存到 `memory/1688-error.json`:

```json
{
  "timestamp": "2026-04-27T17:18:00+08:00",
  "error_type": "missing_fields",
  "source_image": "https://...",
  "missing_fields": ["起订量", "发货履约率"],
  "action_taken": "skip_record"
}
```

### 重试策略

| 错误类型 | 重试次数 | 间隔 |
|---------|---------|------|
| 网络超时 | 3 次 | 2 秒 |
| 页面加载失败 | 2 次 | 3 秒 |
| 文件写入失败 | 1 次 | 1 秒 |

详见 [`references/error-handling.md`](./references/error-handling.md)。

## 验证方法

### 检查输出文件

```bash
ls -lh ./output/products_data_processed.*
head -2 ./output/products_data_processed.csv
jq '.[0]' ./output/products_data_processed.json
```

检查要点:
- ✅ 每条记录都有 1688 商品图链接
- ✅ 每条记录都有商品链接（搜索 URL 也算有效）
- ✅ 19 个字段全部有值（缺失值为 `/`）

## NEVER DO 约束

- ❌ 不要在不验证字段完整性的情况下继续执行
- ❌ 不要跳过浏览器打开步骤直接使用缓存数据
- ❌ 不要在页面未加载完成时提取数据
- ❌ 不要使用动态 class 选择器
- ❌ **不要在缺少商品图链接的情况下强行处理**
- ❌ **不要在商品链接为空时不告知用户**
- ❌ 不要只返回文件名，必须返回完整路径
- ❌ **不要再依赖任何外部表格服务（钉钉 AI 表格、飞书多维表等）—— 默认本地保存**

## 版本历史

| 版本 | 日期 | 核心优化 |
|------|------|---------|
| **v6.0** | 2026-04-27 | 移除钉钉 AI 表格依赖，默认输出本地 CSV+JSON |
| v5.2 | 2026-03-14 | 商品链接搜索替代方案、固定脚本 |
| v5.1 | 2026-03-13 | 错误日志格式、重试策略 |
| v5.0 | 2026-03-12 | dingtalk-neulink 标准版（≤150 行） |

## 相关资源

- [商品链接解决方案](./references/product-link-solution.md)
- [DOM 选择器详解](./references/dom-selectors.md)
- [字段映射规则](./references/field-mapping.md)
- [错误处理指南](./references/error-handling.md)

## 技术支持

遇到问题请查看:
1. 错误日志: `memory/1688-error.json`
2. 示例数据: `examples/products_data.json`
3. 参考脚本: `references/fixed-script.py`
