# DOM 选择器详解

## 1688对比表格页面结构

###页面URL模板

```
https://air.1688.com/app/1688-lp/landing-page/comparison-table.html?bizType=browser&currency=CNY&customerId=dingtalk&outImageAddress=<图片 URL>
```

###表格结构

```html
<table>
  <thead>
    <tr>
      <th>商品名称</th>
      <th>价格</th>
      <th>近90 天销量</th>
      <th>近14 天销量</th>
      <th>工厂年限</th>
      <th>回头率</th>
      <th>综合服务分</th>
      <th>客服响应率</th>
      <th>起订量</th>
      <th>发货履约率</th>
      <th>48h 揽收率</th>
      <th>首次上架时间</th>
      <th>评价数</th>
      <th>源头厂家</th>
      <th>供应商名称</th>
      <th>发货地</th>
    </tr>
  </thead>
  <tbody>
    <tr class="ant-table-row">
      <td class="ant-table-cell">...</td>
      ... (共16列)
    </tr>
  </tbody>
</table>
```

## JavaScript 提取脚本

###固定版（推荐）

```javascript
() => {
    const rows = document.querySelectorAll('tr.ant-table-row');
    const products = [];
    
    rows.forEach((row, index) => {
        const cells = row.querySelectorAll('td.ant-table-cell');
        
        if (cells.length >= 16) {
            const firstCell = cells[0];
            
            // ⚠️关键：提取商品图片 URL
            const img = firstCell.querySelector('img');
            const imgUrl = img ? (img.src || (img.dataset && img.dataset.src) || '') : '';
            
            //提取商品名称
            const titleElement = firstCell.querySelector('.aibuy-product-title') || 
                               firstCell.querySelector('span') || firstCell;
            let productName = titleElement.textContent.trim().replace(/^预览\n/, '');
            if (productName.length > 200) {
                productName = productName.substring(0, 200);
            }
            
            //收集所有字段
            products.push({
                '商品名称': productName,
                '商品图链接': imgUrl,  // ✅必须提取
                '商品链接': '',  //暂时留空，后续构建搜索链接
                '价格': cells[1]?.textContent.trim() || '/',
                '近 90 天销量': cells[2]?.textContent.trim() || '/',
                '近 14 天销量': cells[3]?.textContent.trim() || '/',
                '工厂年限': cells[4]?.textContent.trim() || '/',
                '回头率': cells[5]?.textContent.trim() || '/',
                '综合服务分': cells[6]?.textContent.trim() || '/',
                '客服响应率': cells[7]?.textContent.trim() || '/',
                '起订量': cells[8]?.textContent.trim() || '/',
                '发货履约率': cells[9]?.textContent.trim() || '/',
                '48h 揽收率': cells[10]?.textContent.trim() || '/',
                '首次上架时间': cells[11]?.textContent.trim() || '/',
                '评价数': cells[12]?.textContent.trim() || '/',
                '源头厂家': cells[13]?.textContent.trim() || '/',
                '供应商名称': cells[14]?.textContent.trim() || '/',
                '发货地': cells[15]?.textContent.trim() || '/'
            });
        }
    });
    
    console.log(`✅ 成功提取${products.length}条商品记录`);
    return products;
}
```

###选择器说明

|选择器|用途|备注|
|--------|----|-----|
|`tr.ant-table-row` |选择数据行|固定class，不依赖动态值|
|`td.ant-table-cell` |选择单元格|固定class|
|`td:nth-of-type(1)` |第一列（商品名称+图片）|使用nth-of-type避免索引问题|
|`td:nth-of-type(1) img` |商品图片|提取src或dataset.src|
|`.aibuy-product-title` |商品标题|优先选择器|

## 常见错误及解决方案

### 错误1:商品图链接为空

**原因**:
-图片未加载完成
- 使用了错误的选择器

**解决方案**:
```javascript
//等待5000ms后再执行提取
const img = firstCell.querySelector('img');
const imgUrl = img ? (img.src || (img.dataset && img.dataset.src) || '') : '';
```

### 错误2:字段数量不对

**原因**:
-页面结构变化
-某些列被隐藏

**解决方案**:
```javascript
if (cells.length >= 16) {
    //确保至少16列才处理
}
```

### 错误3:商品名包含"预览"前缀

**解决方案**:
```javascript
const productName = titleElement.textContent.trim().replace(/^预览\n/, '');
```

##测试验证

###在浏览器控制台测试

1.打开1688以图搜图页面
2.按F12打开开发者工具
3.在Console中粘贴提取脚本
4.检查输出结果

###预期输出

```javascript
[
  {
    "商品名称": "Cross-Border Exclusive Dehumidifier Boxes...",
    "商品图链接": "https://cbu01.alicdn.com/O1CN01xxx.jpg",
    "价格": "¥68.60",
    ...
  },
  ...
]
```

##性能优化

###批量处理

当有大量商品时（如100+），分批提取:

```javascript
const BATCH_SIZE = 20;
for (let i = 0; i< rows.length; i += BATCH_SIZE) {
    const batch = rows.slice(i, i + BATCH_SIZE);
    //处理当前批次
}
```

###延迟执行

确保页面完全加载:

```javascript
setTimeout(() => {
    //执行提取逻辑
}, 5000);
```
