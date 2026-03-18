#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书推送测试脚本
用于快速测试 Webhook 配置是否正确
"""

import requests
import json
from datetime import datetime

def send_to_feishu(webhook_url, message):
    """发送消息到飞书"""
    headers = {
        'Content-Type': 'application/json',
    }
    
    payload = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": message["title"],
                    "content": message["content"]
                }
            }
        }
    }
    
    try:
        response = requests.post(webhook_url, headers=headers, json=payload, timeout=5)
        if response.status_code == 200:
            result = response.json()
            if result.get("StatusCode") == 0:
                return True, "✅ 消息已成功推送到飞书"
            else:
                return False, f"❌ 飞书返回错误: {result.get('StatusMessage', '未知错误')}"
        else:
            return False, f"❌ HTTP 错误 {response.status_code}: {response.text}"
    except Exception as e:
        return False, f"❌ 请求失败: {str(e)}"

def test_feishu_webhook():
    """测试飞书 Webhook"""
    
    print("\n" + "="*60)
    print("🤖 飞书 Webhook 推送测试")
    print("="*60)
    
    # 获取 Webhook 地址
    webhook_url = input("\n请输入你的飞书 Webhook 地址:\n> ").strip()
    
    if not webhook_url:
        print("❌ Webhook 地址不能为空")
        return
    
    if not webhook_url.startswith("https://"):
        print("❌ Webhook 地址必须以 https:// 开头")
        return
    
    print("\n正在测试连接...")
    
    # 准备测试消息
    test_message = {
        "title": "🎯 周期股买点监控 | 测试消息",
        "content": [
            [
                {
                    "tag": "text",
                    "text": "测试时间: "
                },
                {
                    "tag": "text",
                    "text": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "style": ["bold"]
                }
            ],
            [
                {
                    "tag": "text",
                    "text": "\n✅ 如果你在飞书中看到这条消息，说明 Webhook 配置成功！\n"
                }
            ],
            [
                {
                    "tag": "text",
                    "text": "📊 海螺水泥 (600585)\n",
                    "style": ["bold"]
                }
            ],
            [
                {
                    "tag": "text",
                    "text": "当前价: 25.07 元\nMA20: 25.23 元\n偏离: -0.63% (即将突破)\nPB值: 0.70 (历史 90% 分位)\n信号: 🟡 关注\n"
                }
            ],
            [
                {
                    "tag": "text",
                    "text": "\n💡 下一步:\n1. 复制你的 Webhook 地址\n2. 填入 cycle_stock_monitor.py 中的 FEISHU_WEBHOOK\n3. 自动化任务每日下午 17:30 自动推送实时监控结果\n"
                }
            ]
        ]
    }
    
    # 发送测试消息
    success, message = send_to_feishu(webhook_url, test_message)
    
    print(f"\n结果: {message}")
    
    if success:
        print("\n" + "="*60)
        print("🎉 Webhook 配置成功！")
        print("="*60)
        print("\n接下来的操作:")
        print("1. 复制这个 Webhook 地址")
        print("2. 编辑文件: cycle_stock_monitor.py")
        print("3. 找到第 21 行的 FEISHU_WEBHOOK")
        print("4. 替换为: FEISHU_WEBHOOK = \"" + webhook_url + "\"")
        print("5. 保存文件")
        print("6. WorkBuddy 自动化设置中激活「周期股买点监控」任务")
        print("\n之后每个工作日下午 5:30，系统会自动推送监控结果到飞书！\n")
    else:
        print("\n" + "="*60)
        print("❌ 配置失败，请检查:")
        print("="*60)
        print("1. Webhook 地址是否复制完整")
        print("2. 飞书应用权限是否设置正确")
        print("3. 机器人是否已加入目标群组")
        print("\n需要帮助? 查看 FEISHU_SETUP.md\n")

if __name__ == "__main__":
    test_feishu_webhook()
