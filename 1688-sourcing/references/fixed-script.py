#!/usr/bin/env python3
"""
1688 同款商品数据处理脚本 v6.0 (Local Path Edition)
用于 1688-sourcing v6.0 技能

核心功能:
1. 从 JSON 文件读取浏览器提取的商品数据
2. 验证 19 个字段完整性
3. 构建商品搜索链接
4. 保存结果为本地 CSV 和 JSON 文件
"""

import json
import csv
import os
from urllib.parse import quote

# ========== 配置区域 ==========
OUTPUT_FILENAME = "1688-sourcing-results"
REQUIRED_FIELDS = [
    '原始图片链接', '1688 商品图链接', '商品链接', '商品名称', '价格',
    '近 90 天销量', '近 14 天销量', '工厂年限', '回头率', '综合服务分',
    '客服响应率', '起订量', '发货履约率', '48h 揽收率', '首次上架时间',
    '评价数', '源头厂家', '供应商名称', '发货地'
]

def build_product_search_url(product_name: str) -> str:
    """使用商品名称构建 1688 搜索链接"""
    if not product_name or product_name == '/':
        return ""
    keyword = product_name[:50] if len(product_name) > 50 else product_name
    return f"https://s.1688.com/selloffer/offer_search.htm?keywords={quote(keyword)}"

def validate_products(products: list, original_image_url: str) -> list:
    """验证商品数据完整性"""
    validated = []
    
    for product in products:
        enriched = {'原始图片链接': original_image_url}
        
        # 1688 商品图链接
        img_link = product.get('商品图链接', '').strip()
        enriched['1688 商品图链接'] = img_link if img_link else '/'
        
        # 商品名称
        product_name = product.get('商品名称', '').strip()
        enriched['商品名称'] = product_name if product_name else '/'
        
        # 商品链接 - 通过搜索构建
        detail_link = build_product_search_url(product_name)
        enriched['商品链接'] = detail_link if detail_link else '/'
        
        # 其他字段
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

def save_to_json(data: list, path: str):
    """保存为 JSON 文件"""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON 数据已保存至: {path}")

def save_to_csv(data: list, path: str):
    """保存为 CSV 文件"""
    if not data:
        return
    
    keys = data[0].keys()
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(data)
    print(f"✅ CSV 数据已保存至: {path}")

def main(data_file: str, original_image_url: str, output_dir: str = "."):
    """主函数"""
    print("=" * 60)
    print("1688 同款商品数据处理脚本 v6.0 (Local Path Edition)")
    print("=" * 60)
    
    # 读取数据
    try:
        if not os.path.exists(data_file):
            print(f"❌ 找不到数据文件：{data_file}")
            return
            
        with open(data_file, 'r', encoding='utf-8') as f:
            products = json.load(f)
        print(f"📊 已加载 {len(products)} 条商品记录")
    except json.JSONDecodeError:
        print(f"❌ 数据文件格式错误：{data_file}")
        return
    
    # 验证和丰富数据
    print("\n🔍 验证数据完整性...")
    validated_products = validate_products(products, original_image_url)
    
    # 确保输出目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 保存结果
    json_path = os.path.join(output_dir, f"{OUTPUT_FILENAME}.json")
    csv_path = os.path.join(output_dir, f"{OUTPUT_FILENAME}.csv")
    
    save_to_json(validated_products, json_path)
    save_to_csv(validated_products, csv_path)
    
    print("\n" + "=" * 60)
    print("✅ 任务完成！")
    print("=" * 60)
    print(f"📝 记录数量：{len(validated_products)}")
    print(f"🏷️ 字段数量：19")
    print(f"📂 保存路径：{os.path.abspath(output_dir)}")
    print("=" * 60)

if __name__ == "__main__":
    import sys
    # 参数: [脚本] [输入JSON路径] [原始图片URL] [可选: 输出目录]
    if len(sys.argv) >= 3:
        input_json = sys.argv[1]
        img_url = sys.argv[2]
        out_dir = sys.argv[3] if len(sys.argv) > 3 else "."
        main(input_json, img_url, out_dir)
    else:
        print("用法: python fixed-script.py <input_json> <original_image_url> [output_dir]")
