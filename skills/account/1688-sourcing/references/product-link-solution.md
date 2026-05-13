#商品链接丢失问题解决方案

##问题说明

在1688对比表格页面中，商品信息通过JavaScript动态渲染，无法直接提取商品详情页链接。

##解决方案：搜索链接替代

###核心思路

使用商品名称在1688站内搜索，生成搜索结果页链接作为"商品链接"的替代。

###构建规则

```python
from urllib.parse import quote

def build_product_search_url(product_name: str) -> str:
    """
    使用商品名称构建1688 搜索链接
    
    Args:
        product_name:商品名称（可能很长）
    
    Returns:
        1688搜索页面URL，或空字符串
    """
    if not product_name or product_name == '/':
        return ""
    
    #截断过长的商品名（保留前50字符）
    keyword = product_name[:50] if len(product_name) > 50 else product_name
    
    #构建搜索 URL
    search_url = f"https://s.1688.com/selloffer/offer_search.htm?keywords={quote(keyword)}"
    
    return search_url
```

###示例

|商品名称 |商品链接|
|---------|---------|
|`Cross-Border Exclusive Dehumidifier Boxes...` | `https://s.1688.com/selloffer/offer_search.htm?keywords=Cross-Border+Exclusive+Dehumidifier+Boxes`|
|`Antifreeze Pag -37 ℃ Water Tank Coolant...` | `https://s.1688.com/selloffer/offer_search.htm?keywords=Antifreeze+Pag+-37+℃+Water+Tank+Coolant`|

###优势

1. ✅ **100%有值**：不会为空
2. ✅ **用户友好**：点击后可在搜索结果中找到对应商品
3. ✅ **实现简单**：无需复杂API调用
4. ✅ **稳定可靠**：不依赖页面结构变化

##完整数据处理流程

```python
def validate_and_enrich_products(products: list) -> list:
    """验证商品数据完整性并丰富信息"""
    validated = []
    
    for product in products:
        enriched =
        
        #处理URL字段
        enriched['原始图片链接'] = ORIGINAL_IMAGE_URL
        
        #商品图链接-必须提取
        img_link = product.get('商品图链接', '').strip()
        enriched['商品图链接'] = img_link if img_link else '/'
        
        #商品链接-通过搜索构建
        product_name = product.get('商品名称', '')
        detail_link = build_product_search_url(product_name)
        enriched['商品链接'] = detail_link if detail_link else '/'
        
        #处理其他字段
        other_fields = [
            '价格', '近 90 天销量', '近 14 天销量',
            '工厂年限', '回头率', '综合服务分', '客服响应率',
            '起订量', '发货履约率', '48h 揽收率', '首次上架时间',
            '评价数', '源头厂家', '供应商名称', '发货地'
        ]
        
        for field in other_fields:
            value = product.get(field, '').strip()
            enriched[field] = value if value else '/'
        
        validated.append(enriched)
    
    return validated
```

##固定脚本

完整实现见：`examples/1688_script.py`

使用方法:
```bash
cd <你的本地路径>/1688-sourcing/examples
python3 1688_script.py
```

## 验证方法

### 检查输出文件
```bash
# CSV: 字段顺序与 REQUIRED_FIELDS 一致，utf-8-sig 编码（Excel 兼容）
head -2 ./output/products_data_processed.csv

# JSON: 顶层是 list，每条记录 19 字段；URL 类字段为 {link, text} 对象
jq '.[0]' ./output/products_data_processed.json
```

预期 JSON 输出（一条记录摘录，字段名直接采用脚本 `REQUIRED_FIELDS` 的中文名）:
```json
[
  {
    "原始图片链接":   {"link": "https://m.media-amazon.com/images/I/xxx.jpg", "text": ""},
    "1688 商品图链接": {"link": "https://cbu01.alicdn.com/O1CN01xxx.jpg",     "text": ""},
    "商品链接":        {"link": "https://s.1688.com/selloffer/offer_search.htm?keywords=...", "text": ""},
    "商品名称": "宠物垫子防水牛津布",
    "价格":     "¥14.90",
    "起订量":   "1",
    "供应商名称": "台前县车居汽车用品经营有限责任公司"
    // ... 其余 12 个字段同样以中文名为 key，缺失值为 "/"
  }
]
```

### 数据完整性检查要点
- ✅ 每条记录都有商品图链接（URL 格式正确）
- ✅ 每条记录都有商品链接（搜索页面 URL 也算有效）
- ✅ 19 个字段全部有值（缺失字段标记 `/`，无空字符串/null）
