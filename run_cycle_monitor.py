#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
周期股买点监控 — 启动菜单
快速选择运行模式
"""

import sys
import os
import subprocess

print("""
╔════════════════════════════════════════════════════════╗
║         周期股买点监控系统 — 启动菜单                   ║
║                                                        ║
║     合盛硅业 | 海螺水泥 | 万华化学                      ║
╚════════════════════════════════════════════════════════╝
""")

print("请选择运行模式:\n")
print("1. [演示模式] 模拟数据 — 无需配置，立即演示")
print("   运行: demo_cycle_monitor.py")
print("   特点: 用模拟数据展示功能，适合快速了解系统\n")

print("2. [测试模式] 真实数据 — 需要Tushare Token")
print("   运行: test_cycle_monitor.py")
print("   特点: 使用真实市场数据，验证实际效果\n")

print("3. [查看文档] 浏览指南和结果")
print("   查看: TEST_GUIDE.md / TEST_RESULT.md\n")

print("4. [生产模式] 配置并启用监控")
print("   运行: cycle_stock_monitor.py")
print("   特点: 需要完整配置（Token+飞书）\n")

print("0. [退出]\n")

choice = input("请输入选项 (0-4): ").strip()

if choice == "1":
    print("\n" + "="*60)
    print("启动演示模式 — 模拟数据测试")
    print("="*60 + "\n")
    subprocess.run([sys.executable, "demo_cycle_monitor.py"])

elif choice == "2":
    print("\n" + "="*60)
    print("启动测试模式 — 真实数据测试")
    print("="*60)
    print("\n⚠️  注意: 需要配置 Tushare Token")
    print("   如果还没有Token，请访问: https://tushare.pro\n")
    
    confirm = input("确认已配置Token? (y/n): ").strip().lower()
    if confirm == 'y':
        print()
        subprocess.run([sys.executable, "test_cycle_monitor.py"])
    else:
        print("\n请先配置Token后再运行")
        print("编辑 test_cycle_monitor.py，修改第16行:")
        print('  TUSHARE_TOKEN = "你的真实Token"\n')

elif choice == "3":
    print("\n" + "="*60)
    print("📖 可用文档")
    print("="*60 + "\n")
    
    docs = [
        ("TEST_GUIDE.md", "快速开始指南"),
        ("TEST_RESULT.md", "测试结果总结"),
        ("CYCLE_STOCK_DEPLOY.md", "部署详细指南"),
        ("cycle_stock_monitor.conf", "配置说明"),
    ]
    
    for i, (filename, desc) in enumerate(docs, 1):
        print(f"{i}. {filename:30} - {desc}")
    
    doc_choice = input("\n请选择查看 (1-4, 0返回): ").strip()
    
    if doc_choice in ["1", "2", "3", "4"]:
        filename = docs[int(doc_choice)-1][0]
        filepath = os.path.join(os.getcwd(), filename)
        if os.path.exists(filepath):
            print(f"\n打开 {filename}...\n")
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                print(content)
            input("\n按Enter返回菜单...")
        else:
            print(f"\n文件不存在: {filename}")
    else:
        print("\n已取消")

elif choice == "4":
    print("\n" + "="*60)
    print("启动生产模式 — 配置监控")
    print("="*60)
    print("\n⚠️  注意: 需要完整配置")
    print("   1. Tushare Token (必须)")
    print("   2. 飞书Webhook (可选)\n")
    
    print("配置步骤:")
    print("  1. 编辑 cycle_stock_monitor.py")
    print("     - 第20行: TUSHARE_TOKEN = '你的Token'")
    print("     - 第21行: FEISHU_WEBHOOK = '你的飞书Webhook'")
    print("  2. 保存后运行此脚本")
    print("  3. 在WorkBuddy自动化中启用任务\n")
    
    confirm = input("确认已配置? (y/n): ").strip().lower()
    if confirm == 'y':
        print()
        subprocess.run([sys.executable, "cycle_stock_monitor.py"])
    else:
        print("\n请完成配置后再运行")

elif choice == "0":
    print("\n已退出")

else:
    print("\n❌ 无效选项，请输入0-4\n")
