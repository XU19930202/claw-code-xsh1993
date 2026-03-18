#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
突破交易系统 - 快速启动菜单
==========================
方便快速调用各个功能模块
"""

import os
import sys
import subprocess
import time
from datetime import datetime

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    print("\n" + "="*60)
    print("  🚀 突破交易系统 - 快速启动菜单")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*60)

def print_menu():
    print("""
  【扫描系列】
    1. 扫描 MA20 突破（短期）
    2. 扫描 MA60 突破（中期）
    3. 扫描 MA120 突破（长期）
    4. 一键三层扫描（MA20+60+120）

  【追踪系列】
    5. 追踪昨天的突破信号
    6. 完整流程（扫描+追踪）

  【高级选项】
    7. 查看信号历史
    8. 手动测试买点决策树
    9. 配置 Webhook 地址

  【文档】
    10. 查看系统指南
    11. 查看快速参考

  【其他】
    0. 退出
    """)

def run_scanner(ma_type=20):
    print(f"\n正在启动 MA{ma_type} 突破扫描...")
    print("-" * 60)
    cmd = f"python breakout_scanner.py --ma {ma_type}"
    subprocess.run(cmd, shell=True)

def run_tracker():
    print("\n正在追踪昨天的突破信号...")
    print("-" * 60)
    cmd = "python breakout_decision_tree.py"
    subprocess.run(cmd, shell=True)

def run_integrated():
    print("\n正在运行完整流程（扫描→追踪）...")
    print("-" * 60)
    cmd = "python integrated_breakout_system.py"
    subprocess.run(cmd, shell=True)

def run_three_scanners():
    print("\n正在运行三层扫描（MA20→MA60→MA120）...")
    print("-" * 60)
    
    for ma in [20, 60, 120]:
        print(f"\n>>> 扫描 MA{ma} ...")
        run_scanner(ma)
        time.sleep(2)
    
    print("\n✓ 三层扫描完成")

def view_signal_history():
    import pandas as pd
    
    if not os.path.exists("breakout_signals_history.csv"):
        print("\n⚠️ 信号历史文件不存在")
        return
    
    print("\n加载信号历史...")
    df = pd.read_csv("breakout_signals_history.csv")
    
    print(f"\n【信号历史】总计 {len(df)} 条记录")
    print("-" * 60)
    print(df.to_string(index=False))
    
    # 统计
    print("\n【统计】")
    print(f"  最近7日: {len(df[df['breakout_date'] >= str(int(df['breakout_date'].max()) - 6)])} 条")
    print(f"  MA20: {len(df[df['ma_type'] == 20])} 条")
    print(f"  MA60: {len(df[df['ma_type'] == 60])} 条")
    print(f"  MA120: {len(df[df['ma_type'] == 120])} 条")

def test_decision_tree():
    print("\n【手动测试决策树】")
    print("-" * 60)
    
    ts_code = input("输入股票代码 (如 688757.SH): ").strip()
    breakout_date = input("输入突破日期 (如 20260318): ").strip()
    stock_name = input("输入股票名称 (可选): ").strip()
    
    if not ts_code or not breakout_date:
        print("❌ 代码或日期不能为空")
        return
    
    print(f"\n正在分析 {stock_name or ts_code}...")
    
    from breakout_decision_tree import DataFetcher, BreakoutDecisionTree, format_result
    
    TUSHARE_TOKEN = "a009b833ddc8257726296c9d51574cb6c18315e937eeeeb79ce4e61e"
    
    fetcher = DataFetcher(TUSHARE_TOKEN)
    engine = BreakoutDecisionTree(fetcher)
    result = engine.analyze_stock(ts_code, breakout_date, stock_name)
    print(format_result(result))

def configure_webhook():
    print("\n【配置飞书 Webhook】")
    print("-" * 60)
    
    current_webhook = "https://open.feishu.cn/open-apis/bot/v2/hook/ee48166c-c506-46f0-b73a-36fcbbcd0ac6"
    print(f"当前 Webhook: {current_webhook[:50]}...")
    
    new_webhook = input("\n输入新的 Webhook 地址 (留空保持不变): ").strip()
    
    if new_webhook:
        # 更新所有脚本中的 Webhook
        files_to_update = [
            "breakout_scanner.py",
            "breakout_decision_tree.py",
            "integrated_breakout_system.py"
        ]
        
        for filename in files_to_update:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                content = content.replace(
                    f'FEISHU_WEBHOOK = "{current_webhook}"',
                    f'FEISHU_WEBHOOK = "{new_webhook}"'
                )
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print(f"  ✓ 更新 {filename}")
        
        print("✓ Webhook 配置完成")
    else:
        print("保持不变")

def view_guide():
    if os.path.exists("BREAKOUT_SYSTEM_INTEGRATION_GUIDE.md"):
        os.system("more BREAKOUT_SYSTEM_INTEGRATION_GUIDE.md" if os.name == 'nt' else "less BREAKOUT_SYSTEM_INTEGRATION_GUIDE.md")
    else:
        print("⚠️ 指南文件不存在")

def main():
    while True:
        clear_screen()
        print_header()
        print_menu()
        
        choice = input("请选择操作 (0-11): ").strip()
        
        try:
            if choice == '0':
                print("\n👋 再见！")
                break
            elif choice == '1':
                run_scanner(20)
            elif choice == '2':
                run_scanner(60)
            elif choice == '3':
                run_scanner(120)
            elif choice == '4':
                run_three_scanners()
            elif choice == '5':
                run_tracker()
            elif choice == '6':
                run_integrated()
            elif choice == '7':
                view_signal_history()
            elif choice == '8':
                test_decision_tree()
            elif choice == '9':
                configure_webhook()
            elif choice == '10':
                view_guide()
            elif choice == '11':
                print("\n【快速参考】")
                print("""
    📊 扫描: 发现放量突破信号
       python breakout_scanner.py --ma 20

    🎯 追踪: 追踪突破后的走势
       python breakout_decision_tree.py

    🚀 完整: 一键扫描→追踪→推送
       python integrated_breakout_system.py

    📈 买入信号:
       🟢 BUY - 可以立即买入
       🟡 PULLBACK_WAIT - 等待回踩
       🔴 ABANDON - 放弃，虚假突破
                """)
            else:
                print("❌ 选择无效，请重试")
            
            input("\n按 Enter 继续...")
        
        except KeyboardInterrupt:
            print("\n\n👋 已取消")
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            input("\n按 Enter 继续...")

if __name__ == '__main__':
    main()
