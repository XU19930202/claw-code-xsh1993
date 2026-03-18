#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
周期股监控系统 - 快速启动菜单
一站式管理所有操作
"""

import os
import sys
import subprocess

def print_menu():
    """打印主菜单"""
    os.system('cls' if os.name == 'nt' else 'clear')
    
    print("""
╔════════════════════════════════════════════════════════════════╗
║         🎯 周期股买点监控系统 - 快速启动菜单                  ║
║                                                                ║
║  监控标的: 海螺水泥 | 合盛硅业 | 万华化学                     ║
║  实时推送: 飞书 Webhook                                       ║
╚════════════════════════════════════════════════════════════════╝

📌 主菜单

  1. 📊 运行监控（采集最新数据，推送信号）
  2. ⚙️  配置飞书 Webhook（一键设置推送地址）
  3. 🧪 测试飞书推送（验证 Webhook 是否正常）
  4. 📖 查看文档

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Q. 返回上级菜单
  X. 退出

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

def print_doc_menu():
    """打印文档菜单"""
    print("""
╔════════════════════════════════════════════════════════════════╗
║                    📖 文档中心                                 ║
╚════════════════════════════════════════════════════════════════╝

  1. ⭐ QUICK_REFERENCE.md - 快速参考卡（推荐先看）
  2. 🚀 PRODUCTION_READY.md - 生产部署说明
  3. 🤖 FEISHU_SETUP.md - 飞书配置详细指南
  4. 📊 REALTIME_ANALYSIS_20260318.md - 今日市场实时分析
  5. ✅ FINAL_CHECKLIST.md - 最终交付清单
  6. 🧪 TEST_RESULT.md - 系统测试报告

  Q. 返回主菜单
  X. 退出

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

def open_doc(filename):
    """打开文档"""
    if not os.path.exists(filename):
        print(f"\n❌ 找不到文件: {filename}")
        input("按 Enter 继续...")
        return
    
    # Windows 用默认应用打开
    if os.name == 'nt':
        os.startfile(filename)
    else:
        os.system(f"open {filename}")
    
    print(f"\n✅ 已打开: {filename}")
    input("按 Enter 返回菜单...")

def run_script(script_name, description):
    """运行脚本"""
    print(f"\n▶️  运行: {description}")
    print("="*60)
    
    try:
        if script_name == "cycle_stock_monitor.py":
            result = subprocess.run(
                [sys.executable, script_name],
                capture_output=False,
                text=True
            )
        else:
            result = subprocess.run(
                [sys.executable, script_name],
                capture_output=False,
                text=True
            )
        
        print("\n" + "="*60)
        print("✅ 执行完成")
    except Exception as e:
        print(f"\n❌ 执行失败: {str(e)}")
    
    input("按 Enter 返回菜单...")

def main():
    """主函数"""
    while True:
        print_menu()
        choice = input("请选择操作 (1-4, Q, X): ").strip().upper()
        
        if choice == 'X':
            print("\n👋 再见！祝投资顺利！")
            sys.exit(0)
        
        elif choice == '1':
            run_script(
                "cycle_stock_monitor.py",
                "周期股买点监控 - 实时数据采集与分析"
            )
        
        elif choice == '2':
            run_script(
                "setup_feishu.py",
                "飞书配置 - 一键设置 Webhook 地址"
            )
        
        elif choice == '3':
            run_script(
                "test_feishu_webhook.py",
                "飞书测试 - 验证 Webhook 连接"
            )
        
        elif choice == '4':
            doc_loop()
        
        elif choice == 'Q':
            continue
        
        else:
            print("\n❌ 无效选择，请重试")
            input("按 Enter 继续...")

def doc_loop():
    """文档菜单循环"""
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_doc_menu()
        
        choice = input("请选择文档 (1-6, Q, X): ").strip().upper()
        
        if choice == 'X':
            print("\n👋 再见！")
            sys.exit(0)
        
        elif choice == 'Q':
            break
        
        elif choice == '1':
            open_doc("QUICK_REFERENCE.md")
        elif choice == '2':
            open_doc("PRODUCTION_READY.md")
        elif choice == '3':
            open_doc("FEISHU_SETUP.md")
        elif choice == '4':
            open_doc("REALTIME_ANALYSIS_20260318.md")
        elif choice == '5':
            open_doc("FINAL_CHECKLIST.md")
        elif choice == '6':
            open_doc("TEST_RESULT.md")
        else:
            print("\n❌ 无效选择")
            input("按 Enter 继续...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 已退出")
        sys.exit(0)
