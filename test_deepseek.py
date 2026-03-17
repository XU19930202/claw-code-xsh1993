#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试 DeepSeek API"""
import requests
from config import DEEPSEEK_API_KEY

headers = {
    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    "Content-Type": "application/json",
}

payload = {
    "model": "deepseek-chat",
    "messages": [
        {"role": "user", "content": "你好，请用一句话回复。"}
    ],
    "temperature": 0.1,
    "max_tokens": 50,
}

try:
    resp = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=30
    )
    resp.raise_for_status()
    result = resp.json()
    print("API 调用成功！")
    print("回复:", result["choices"][0]["message"]["content"])
except Exception as e:
    print("API 调用失败:", e)
    print("状态码:", resp.status_code if 'resp' in locals() else "N/A")
