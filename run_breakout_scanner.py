#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全市场突破扫描器 - 快速启动菜单
"""

import os
import sys
import subprocess
from datetime import datetime

def print_menu():
    """打印菜单"""
    os.system('cls' if os.name == 'nt' else 'clear')
    
    print("""
╔════════════════════════════════════════════════════════════════╗
║            🔍 全市场均线突破扫描器 - 快速启动                 ║
║                                                                ║
║  功能: 扫描全部A股，找出放量突破均线的股票                   ║
║  推送: 飞书 + 详细分析                                        ║
╚════════════════════════════════════════════════════════════════╝

📌 快速操作

  1. 🔍 扫描 MA20 突破（推荐短线）
  2. 📊 扫描 MA60 突破（推荐中线）
  3. 📈 扫描 MA120 突破（推荐长线）
  4. 🧪 测试扫描（仅打印，不推送）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  5. 📖 查看使用指南
  6. ⚙️  手动输入参数

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Q. 返回 | X. 退出

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

def run_scanner(ma_period, push=True):
    """运行扫描器"""
    print(f"\n▶️  启动扫描器...")
    print(f"   均线: MA{ma_period} | 推送: {'是' if push else '否'}")
    print(f"   预计耗时: 35-40 分钟\n")
    
    cmd = f"python breakout_scanner.py --ma {ma_period}"
    if not push:
        cmd += " --no-push"
    
    try:
        subprocess.run(cmd, shell=True)
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
    
    input("\n按 Enter 返回菜单...")

def main():
    """主函数"""
    while True:
        print_menu()
        choice = input("请选择 (1-6, Q, X): ").strip().upper()
        
        if choice == 'X':
            print("\n👋 再见！")
            sys.exit(0)
        
        elif choice == '1':
            run_scanner(20, push=True)
        
        elif choice == '2':
            run_scanner(60, push=True)
        
        elif choice == '3':
            run_scanner(120, push=True)
        
        elif choice == '4':
            run_scanner(20, push=False)
        
        elif choice == '5':
            os.system('code BREAKOUT_SCANNER_GUIDE.md' if os.name == 'nt' else 'open BREAKOUT_SCANNER_GUIDE.md')
            input("\n按 Enter 返回菜单...")
        
        elif choice == '6':
            ma = input("\n输入均线周期 (20/60/120): ").strip()
            if ma not in ['20', '60', '120']:
                print("❌ 无效输入")
                input("按 Enter 继续...")
                continue
            
            push = input("推送到飞书? (y/n, 默认y): ").strip().upper()
            push = push != 'N'
            
            run_scanner(int(ma), push=push)
        
        elif choice == 'Q':
            continue
        
        else:
            print("\n❌ 无效选择")
            input("按 Enter 继续...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 已退出")
        sys.exit(0)
