#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
周期股监控 - 配置向导
一步步配置 Token 和 Webhook，然后运行监控
"""

import os
import sys

def show_menu():
    print("\n" + "="*50)
    print("  周期股买点监控 - 配置向导")
    print("="*50)
    print("\n请选择操作：")
    print("  1. 配置 Tushare Token")
    print("  2. 配置 飞书 Webhook")
    print("  3. 运行监控脚本")
    print("  4. 查看部署指南")
    print("  5. 退出")
    print("\n" + "-"*50)
    return input("请输入选项 (1-5): ").strip()

def configure_tushare():
    print("\n【Tushare Token 配置】\n")
    print("获取步骤：")
    print("  1. 打开 https://tushare.pro")
    print("  2. 注册/登录账户")
    print("  3. 进入个人主页")
    print("  4. 复制 Token (类似: xxxxxxxxxxxxxxxxxxxxxx)")
    
    token = input("\n请输入你的 Tushare Token: ").strip()
    
    if len(token) < 20:
        print("\n⚠️  Token 格式不对，请重新检查")
        return None
    
    print(f"\n✓ Token 已配置: {token[:10]}...")
    return token

def configure_feishu():
    print("\n【飞书 Webhook 配置】\n")
    print("获取步骤：")
    print("  1. 打开飞书，进入某个群组")
    print("  2. 右上角 ⋯ -> 群组设置")
    print("  3. 左侧 '开发者工具' -> '机器人'")
    print("  4. 点击 '创建机器人'")
    print("  5. 配置机器人 -> 获取 Webhook URL")
    print("  6. 复制 Webhook 地址")
    
    webhook = input("\n请输入飞书 Webhook URL: ").strip()
    
    if not webhook.startswith("https://"):
        print("\n⚠️  URL 格式不对，请确保以 https:// 开头")
        return None
    
    print(f"\n✓ Webhook 已配置: {webhook[:50]}...")
    return webhook

def save_config(token, webhook):
    print("\n正在保存配置...")
    
    script_path = "cycle_stock_monitor.py"
    
    if not os.path.exists(script_path):
        print(f"\n❌ 找不到脚本文件: {script_path}")
        return False
    
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换 token 和 webhook
    content = content.replace(
        'TUSHARE_TOKEN = "你的Tushare_Token"',
        f'TUSHARE_TOKEN = "{token}"'
    )
    content = content.replace(
        'FEISHU_WEBHOOK = "你的飞书Webhook地址"',
        f'FEISHU_WEBHOOK = "{webhook}"'
    )
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✓ 配置已保存到 cycle_stock_monitor.py")
    return True

def run_monitor():
    print("\n【运行监控脚本】\n")
    print("正在启动周期股监控...\n")
    
    import subprocess
    
    try:
        result = subprocess.run(
            [sys.executable, "cycle_stock_monitor.py"],
            timeout=300
        )
        return result.returncode == 0
    except Exception as e:
        print(f"\n❌ 运行失败: {e}")
        return False

def show_guide():
    guide_path = "CYCLE_STOCK_DEPLOY.md"
    
    if not os.path.exists(guide_path):
        print(f"\n❌ 找不到指南文件: {guide_path}")
        return
    
    with open(guide_path, 'r', encoding='utf-8') as f:
        print("\n" + f.read())

def main():
    print("\n" + "="*50)
    print("  欢迎使用周期股买点监控系统 v1.0")
    print("="*50)
    
    token = None
    webhook = None
    
    while True:
        choice = show_menu()
        
        if choice == "1":
            token = configure_tushare()
        elif choice == "2":
            webhook = configure_feishu()
        elif choice == "3":
            if not token or not webhook:
                print("\n❌ 请先配置 Token 和 Webhook (选项 1 和 2)")
                continue
            
            if save_config(token, webhook):
                run_monitor()
            else:
                print("\n❌ 配置保存失败")
        elif choice == "4":
            show_guide()
        elif choice == "5":
            print("\n👋 再见！\n")
            break
        else:
            print("\n⚠️  无效的选项，请重试\n")

if __name__ == "__main__":
    main()
