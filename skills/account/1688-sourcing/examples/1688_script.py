#!/usr/bin/env python3
"""
1688 同款商品数据完整提取脚本 v6.0 (Local Path Edition)

变更说明:
- 移除钉钉 AI 表格依赖 (dws aitable CLI)
- 默认保存为本地 CSV + JSON 双格式
- 保留 19 字段完整性验证 (HARD-GATE)
- 保留商品链接搜索构建逻辑

工作流:
1. 从 JSON 文件读取浏览器提取的原始商品数据
2. 验证字段完整性，缺失字段标记 "/"
3. 通过商品名称构建 1688 站内搜索链接（替代直接商品详情页）
4. 输出到脚本同目录 output/ 子目录:
   - products_data_processed.json
   - products_data_processed.csv (utf-8-sig 编码，Excel 可直接打开)
"""

import json
import csv
import sys
import re
from pathlib import Path
from urllib.parse import quote

# ========== 配置区域 ==========
ORIGINAL_IMAGE_URL = "https://images-na.ssl-images-amazon.com/images/I/71Tg1wI7YFL._AC_UL900_SR900,600_.jpg"

# 19 个必填字段（与 references/field-mapping.md 对齐）
REQUIRED_FIELDS = [
    "原始图片链接", "1688 商品图链接", "商品链接", "商品名称", "价格",
    "近 90 天销量", "近 14 天销量", "工厂年限", "回头率", "综合服务分",
    "客服响应率", "起订量", "发货履约率", "48h 揽收率", "首次上架时间",
    "评价数", "源头厂家", "供应商名称", "发货地"
]

# URL 类型字段（CSV 中以纯字符串保存；JSON 中以 {"link":..,"text":""} 保存以兼容下游）
URL_FIELDS = {"原始图片链接", "1688 商品图链接", "商品链接"}


def build_product_search_url(product_name: str) -> str:
    """
    通过商品名称构建 1688 站内搜索链接。
    由于无法直接从对比表格反推商品详情页 ID，用搜索结果页作为可点击替代。
    """
    if not product_name or product_name == "/":
        return ""
    keyword = product_name[:50]
    return f"https://s.1688.com/selloffer/offer_search.htm?keywords={quote(keyword)}"


def validate_and_enrich_products(products: list) -> list:
    """
    校验字段完整性并补齐:
    - 缺失字段统一记 "/"
    - 商品图链接强制非空（HARD-GATE）
    - 商品链接通过搜索 URL 构建
    """
    validated = []
    for i, product in enumerate(products):
        enriched = {"原始图片链接": ORIGINAL_IMAGE_URL}

        img_link = (product.get("商品图链接") or "").strip()
        if not img_link:
            print(f"⚠️  记录 {i+1} 缺少 1688 商品图链接，已标记为 '/'")
        enriched["1688 商品图链接"] = img_link if img_link else "/"

        product_name = (product.get("商品名称") or "").strip()
        detail_link = build_product_search_url(product_name)
        enriched["商品链接"] = detail_link if detail_link else "/"

        for field in REQUIRED_FIELDS:
            if field in enriched:
                continue
            value = (product.get(field) or "").strip() if isinstance(product.get(field), str) else product.get(field)
            enriched[field] = value if value not in (None, "", []) else "/"

        validated.append(enriched)

        if i < 3:
            preview_name = enriched["商品名称"][:50] if enriched["商品名称"] != "/" else "/"
            print(f"📝 记录 {i+1} 预览: {preview_name}…")

    return validated


def save_as_json(records: list, output_path: Path) -> None:
    """JSON 输出: URL 字段使用 {link, text} 对象格式以兼容下游导入工具。"""
    payload = []
    for r in records:
        item = {}
        for field in REQUIRED_FIELDS:
            value = r.get(field, "/")
            if field in URL_FIELDS:
                item[field] = {"link": value if value != "/" else "", "text": ""}
            else:
                item[field] = value
        payload.append(item)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_as_csv(records: list, output_path: Path) -> None:
    """CSV 输出: 全部以纯字符串列保存，使用 utf-8-sig 让 Excel 直接识别中文。"""
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REQUIRED_FIELDS)
        writer.writeheader()
        for r in records:
            writer.writerow({field: r.get(field, "/") for field in REQUIRED_FIELDS})


def main():
    print("=" * 60)
    print("1688 同款商品数据提取脚本 v6.0 (Local Path Edition)")
    print("=" * 60)

    script_dir = Path(__file__).resolve().parent
    data_file = script_dir / "products_data.json"
    output_dir = script_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 步骤 1: 读取原始数据
    if not data_file.exists():
        print(f"❌ 找不到数据文件: {data_file}")
        print("请先运行浏览器提取脚本生成 products_data.json")
        sys.exit(1)

    try:
        products = json.loads(data_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"❌ 数据文件格式错误: {e}")
        sys.exit(1)

    print(f"📊 已加载 {len(products)} 条商品记录")

    # 步骤 2: 验证 + 补齐
    print("\n🔍 验证字段完整性 + 构建商品搜索链接…")
    validated = validate_and_enrich_products(products)

    # 步骤 3: 输出本地文件
    json_path = output_dir / "products_data_processed.json"
    csv_path = output_dir / "products_data_processed.csv"
    save_as_json(validated, json_path)
    save_as_csv(validated, csv_path)

    print("\n" + "=" * 60)
    print("✅ 任务完成")
    print("=" * 60)
    print(f"📝 记录数量: {len(validated)}")
    print(f"🏷️  字段数量: {len(REQUIRED_FIELDS)}")
    print(f"💾 JSON 输出: {json_path}")
    print(f"💾 CSV  输出: {csv_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
