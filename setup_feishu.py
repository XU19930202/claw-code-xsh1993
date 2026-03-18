#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书配置一键脚本
快速配置 Webhook 地址到 cycle_stock_monitor.py
"""

import os
import sys

def configure_feishu_webhook():
    """一键配置飞书 Webhook"""
    
    print("\n" + "="*70)
    print("⚙️  周期股监控系统 - 飞书配置")
    print("="*70)
    
    script_path = "cycle_stock_monitor.py"
    
    # 检查脚本是否存在
    if not os.path.exists(script_path):
        print(f"\n❌ 找不到 {script_path}")
        print("请确保在项目目录下运行此脚本")
        return False
    
    print("\n📋 当前配置状态:")
    print(f"脚本位置: {os.path.abspath(script_path)}")
    
    # 读取当前配置
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()
        if "你的飞书Webhook地址" in content:
            print("飞书配置: ❌ 未配置（仍为占位符）")
        else:
            print("飞书配置: ✅ 已配置")
            return True
    
    print("\n" + "="*70)
    print("💡 获取 Webhook 地址步骤:")
    print("="*70)
    print("""
1. 打开飞书开放平台: https://open.feishu.cn
2. 左侧菜单 → 应用开发 → 创建应用
3. 选择自建应用，输入应用名称（如"周期股监控"）
4. 在开发配置或事件订阅中找到 Webhook 地址
5. 复制完整的 URL（以 https://open.feishu.cn/open-apis/bot/v2/hook/ 开头）

详细步骤: 打开 FEISHU_SETUP.md 查看详细配置指南
""")
    
    print("="*70)
    print("🔧 开始配置")
    print("="*70)
    
    webhook_url = input("\n请粘贴你的飞书 Webhook 地址:\n> ").strip()
    
    if not webhook_url:
        print("❌ 配置取消 - 未输入 Webhook 地址")
        return False
    
    if not webhook_url.startswith("https://open.feishu.cn/open-apis/bot/v2/hook/"):
        confirm = input("\n⚠️  警告: 地址格式可能不正确\n按 'y' 继续，其他键取消:\n> ").strip().lower()
        if confirm != 'y':
            print("❌ 配置取消")
            return False
    
    # 替换 Webhook 地址
    print("\n正在更新配置...")
    old_webhook = 'FEISHU_WEBHOOK = "你的飞书Webhook地址"'
    new_webhook = f'FEISHU_WEBHOOK = "{webhook_url}"'
    
    content = content.replace(old_webhook, new_webhook)
    
    # 写入文件
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ 配置已保存")
    
    print("\n" + "="*70)
    print("✨ 配置完成！")
    print("="*70)
    print("""
接下来的步骤:

1. ✅ 飞书 Webhook 已配置
   
2. ⏳ 激活自动化任务
   → 打开 WorkBuddy
   → 自动化 → 找「周期股买点监控」
   → 改为 ACTIVE 状态
   
3. 🚀 每个工作日下午 5:30，系统自动运行
   → 采集最新数据
   → 推送买点信号到飞书
   → 共监控 3 个标的：海螺水泥、合盛硅业、万华化学

📌 手动测试推送 (可选):
   python test_cycle_monitor.py

💬 需要帮助?
   查看 FEISHU_SETUP.md 或 QUICK_REFERENCE.md
""")
    
    return True

if __name__ == "__main__":
    try:
        success = configure_feishu_webhook()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  配置中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 出错: {str(e)}")
        sys.exit(1)
