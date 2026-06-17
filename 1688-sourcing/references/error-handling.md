# 错误处理和调试指南 (Local Path Edition)

## 错误日志格式

保存到 `memory/1688-error.json`:

```json
{
  "timestamp": "2026-03-14T17:18:00+08:00",
  "error_type": "missing_fields",
  "source_image": "https://images-na.ssl-images-amazon.com/images/I/71Tg1wI7YFL.jpg",
  "missing_fields": ["起订量", "发货履约率"],
  "action_taken": "skip_record"
}
```

### error_type 枚举值

| 值 | 说明 | 处理方式 |
|---|------|---------|
| `missing_fields` | 字段缺失 | HARD-GATE失败，记录到日志，暂停 |
| `browser_failed` | 浏览器打开失败 | 检查网络/代理，重试最多2次 |
| `no_results` | 1688页面无搜索结果 | 告知用户"该图片在 1688 无同款"，跳过 |
| `page_changed` | 页面结构变化 | 停止，提示需更新技能选择器 |
| `write_failed` | 文件保存失败 | 检查磁盘权限，重试1次，告知用户 |

## 重试策略

| 错误类型 | 重试次数 | 间隔 | 超过最大重试 |
|---------|---------|------|------------|
| 网络超时 | 3次 | 2秒 | 标记"处理失败"，记日志，继续 |
| 页面加载失败 | 2次 | 3秒 | 同上 |
| 文件写入失败 | 1次 | 1秒 | 同上 |

## 常见错误场景及处理

### 1. 浏览器无法打开

**错误信息**:
```
Error: Failed to navigate to URL
```

**处理流程**:
1. 检查网络连接
2. 重试（最多2次，间隔3秒）
3. 仍然失败 → 报告给用户

### 2. 商品图链接提取失败

**可能原因**:
- 页面未完全加载
- DOM 选择器不匹配
- 图片使用懒加载

**处理流程**:
1. 等待更长时间（5000ms→10000ms）
2. 尝试不同的选择器
3. 仍然失败 → HARD-GATE失败，记录日志

### 3. 文件保存失败

**错误信息**:
```
Error: Permission denied / Disk full
```

**处理流程**:
1. 检查路径是否正确
2. 检查写入权限
3. 仍然失败 → 提示用户手动提供可写入路径

## 调试技巧

### 1. 保存中间结果

```python
# 保存提取的原始数据
with open('products_raw.json', 'w') as f:
    json.dump(products, f, ensure_ascii=False, indent=2)
```

### 2. 浏览器开发者工具调试

在 Console 中执行:
```javascript
// 提取商品图链接
document.querySelector('td.ant-table-cell img')?.src
```
