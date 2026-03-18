#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
巨潮资讯网下载器 - 依赖检查和快速测试
"""

import sys
import subprocess

def check_dependencies():
    """检查所需依赖"""
    print("=" * 60)
    print("  巨潮资讯网下载器 - 环境检查")
    print("=" * 60)
    
    required = {
        'requests': '请求库（网络通信）',
        'yaml': 'YAML库（配置文件）',
    }
    
    missing = []
    
    for module, desc in required.items():
        try:
            __import__(module)
            print(f"  [OK] {module:15} - {desc}")
        except ImportError:
            print(f"  [X]  {module:15} - {desc} [缺失]")
            missing.append(module)
    
    print("=" * 60)
    
    if missing:
        print(f"\n警告: 缺失依赖包: {', '.join(missing)}")
        print("\n请运行以下命令安装:\n")
        print(f"  pip install {' '.join(missing)}")
        return False
    else:
        print("\n[OK] 所有依赖已安装，可以开始使用!\n")
        return True


def quick_test():
    """快速功能测试"""
    try:
        import requests
        print("测试网络连接...")
        
        resp = requests.head("http://www.cninfo.com.cn/", timeout=5)
        if resp.status_code < 400:
            print("  [OK] 网络连接正常")
            return True
        else:
            print(f"  [X]  网站响应异常 (HTTP {resp.status_code})")
            return False
    except Exception as e:
        print(f"  [X]  网络连接失败: {e}")
        print("    请检查网络连接和防火墙设置")
        return False


def main():
    print()
    
    # 检查依赖
    if not check_dependencies():
        print("请先安装缺失的依赖包后再使用\n")
        sys.exit(1)
    
    # 网络测试
    if not quick_test():
        print()
        print("⚠️  网络连接可能存在问题，但不影响本地功能")
        print()
    
    print("\n" + "=" * 60)
    print("  快速开始")
    print("=" * 60)
    print("""
1. 交互模式 (推荐)
    python cninfo_downloader.py

2. 查询贵州茅台最新公告
    python cninfo_downloader.py -c 600519 -n 10

3. 查询所有重大资产重组事件
    python cninfo_downloader.py -k 重大资产重组 -n 20

4. 搜索并下载年报
    python cninfo_downloader.py -c 600900 -k 年报 --download

5. 查看详细文档
    cat CNINFO_USAGE.md

""")
    print("=" * 60)


if __name__ == "__main__":
    main()
