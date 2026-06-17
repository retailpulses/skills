# 19 字段映射规则 (Local Path Edition)

## 字段清单

|序号| 字段名 | 类型 | 提取方式 | 验证规则 |
|-----|--------|----|---------|---------|
|1|原始图片链接|URL|直接使用|不能为空|
|2|**1688 商品图链接**|URL|`td:nth-of-type(1) img.src`|⚠️必须提取，不能留空|
|3|**商品链接**|URL|构建搜索链接|⚠️不能为空，采用搜索替代|
|4|商品名称|文本|去除"预览"前缀|截断至 200 字符|
|5|价格|文本|直接提取|缺失标记 "/"|
|6|近 90 天销量|文本|直接提取|缺失标记 "/"|
|7|近 14 天销量|文本|直接提取|缺失标记 "/"|
|8|工厂年限|文本|直接提取|缺失标记 "/"|
|9|回头率|文本|直接提取|缺失标记 "/"|
|10|综合服务分|文本|直接提取|缺失标记 "/"|
|11|客服响应率|文本|直接提取|缺失标记 "/"|
|12|起订量|文本|直接提取|缺失标记 "/"|
|13|发货履约率|文本|直接提取|缺失标记 "/"|
|14|48h 揽收率|文本|直接提取|缺失标记 "/"|
|15|首次上架时间|文本|直接提取|缺失标记 "/"|
|16|评价数|文本|直接提取|缺失标记 "/"|
|17|源头厂家|文本|直接提取|缺失标记 "/"|
|18|供应商名称|文本|直接提取|缺失标记 "/"|
|19|发货地|文本|直接提取|缺失标记 "/"|

## 关键字段说明

### 1. 原始图片链接

**来源**: 用户提供的商品图片 URL

### 2. 1688 商品图链接 ⚠️

**来源**: 从 1688 对比表格第 1 列的 `<img>` 标签提取

**提取脚本**:
```javascript
const img = firstCell.querySelector('img');
const imgUrl = img ? (img.src || (img.dataset && img.dataset.src) || '') : '';
```

### 3. 商品链接 ⚠️

**来源**: 通过商品名称构建搜索链接（因为无法直接从页面提取）

**构建规则**:
```python
from urllib.parse import quote

def build_product_search_url(product_name: str) -> str:
    if not product_name or product_name == '/':
        return ""
    keyword = product_name[:50] if len(product_name) > 50 else product_name
    return f"https://s.1688.com/selloffer/offer_search.htm?keywords={quote(keyword)}"
```

### 4. 商品名称

**来源**: 第 1 列文本内容

**处理规则**:
```javascript
let productName = titleElement.textContent.trim().replace(/^预览\n/, '');
if (productName.length > 200) {
    productName = productName.substring(0, 200);
}
```

## 数据保存格式 (CSV/JSON)

在保存为本地文件前，必须验证:

- [ ] 所有 19 个字段都有值
- [ ] 商品图链接不是空字符串
- [ ] 商品链接不是空字符串（可以是搜索链接）
- [ ] 缺失字段标记为 "/" 而不是 null 或空字符串
- [ ] 商品名称长度不超过 200 字符
- [ ] CSV 编码建议使用 `utf-8-sig` 以支持中文在 Excel 中正常显示
