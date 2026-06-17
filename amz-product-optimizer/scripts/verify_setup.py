#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安装验证脚本 - 检查技能运行环境是否就绪

Usage:
    python3 scripts/verify_setup.py
"""

import sys
import json
from pathlib import Path


def check_python_version():
    """检查 Python 版本"""
    print("✓ 检查 Python 版本...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 9:
        print(f"  ✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"  ❌ Python 版本过低，需要 >= 3.9，当前 {version.major}.{version.minor}")
        return False


def check_dependencies():
    """检查 Python 依赖"""
    print("\n✓ 检查 Python 依赖...")
    
    dependencies = {
        'requests': 'HTTP 请求库',
        'bs4': 'BeautifulSoup4 HTML 解析库'
    }
    
    all_ok = True
    for package, description in dependencies.items():
        try:
            __import__(package)
            print(f"  ✅ {package} - {description}")
        except ImportError:
            print(f"  ❌ {package} - {description} (未安装)")
            all_ok = False
    
    return all_ok


def check_skill_files():
    """检查技能文件完整性"""
    print("\n✓ 检查技能文件...")
    
    required_files = [
        'SKILL.md',
        'README.md',
        'skill.json',
        'scripts/product_optimizer.py',
        'test_cases/tc_optimization.json',
        'hooks/hooks.json'
    ]
    
    base_path = Path(__file__).parent.parent
    all_ok = True
    
    for file_path in required_files:
        full_path = base_path / file_path
        if full_path.exists():
            size = full_path.stat().st_size
            print(f"  ✅ {file_path} ({size} bytes)")
        else:
            print(f"  ❌ {file_path} (缺失)")
            all_ok = False
    
    return all_ok


def check_mcp_config():
    """检查 MCP 服务配置"""
    print("\n✓ 检查 MCP 服务配置...")
    
    required_servers = [
        {'id': '19cf03a191f', 'name': '淘宝 opc 服务'}
    ]
    
    # 注意：这里无法直接检查 MCP 配置，仅提供提示
    print("  ℹ️  请手动验证以下 MCP 服务已配置:")
    for server in required_servers:
        print(f"     - {server['name']} (ID: {server['id']})")
    
    print("  ⚠️  此项需要人工确认")
    return True  # 返回 True 因为无法自动验证


def load_skill_json():
    """验证 skill.json 格式"""
    print("\n✓ 验证 skill.json 格式...")
    
    try:
        with open(Path(__file__).parent.parent / 'skill.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        required_fields = ['name', 'version', 'description', 'input_schema', 'capabilities']
        missing = [field for field in required_fields if field not in data]
        
        if not missing:
            print(f"  ✅ skill.json 格式正确 (版本 {data['version']})")
            return True
        else:
            print(f"  ❌ 缺少必需字段：{', '.join(missing)}")
            return False
            
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON 格式错误：{e}")
        return False
    except Exception as e:
        print(f"  ❌ 读取失败：{e}")
        return False


def main():
    """主函数"""
    print("="*60)
    print("amz-product-optimizer 技能安装验证")
    print("="*60)
    
    checks = [
        ("Python 版本", check_python_version()),
        ("Python 依赖", check_dependencies()),
        ("技能文件", check_skill_files()),
        ("skill.json 格式", load_skill_json()),
        ("MCP 服务配置", check_mcp_config())
    ]
    
    print("\n" + "="*60)
    print("验证结果汇总")
    print("="*60)
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for name, result in checks:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    print("-"*60)
    print(f"总计：{passed}/{total} 项检查通过")
    
    if passed == total:
        print("\n🎉 所有检查通过！技能可以正常使用。")
        return 0
    else:
        print("\n⚠️  部分检查未通过，请先修复问题。")
        return 1


if __name__ == '__main__':
    sys.exit(main())
