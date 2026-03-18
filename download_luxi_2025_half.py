#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import os
import sys
import io

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SAVE_DIR = os.path.join(os.path.dirname(__file__), "annual_reports", "000830_鲁西化工")
os.makedirs(SAVE_DIR, exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# 2025年上半年报告
url = "http://static.cninfo.com.cn/finalpage/2025-08-22/1224532281.PDF"
filename = "000830_鲁西化工_2025年上半年度报告.pdf"

print(f"下载: {filename}")

try:
    resp = requests.get(url, headers=headers, timeout=120, stream=True)
    resp.raise_for_status()
    
    save_path = os.path.join(SAVE_DIR, filename)
    with open(save_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    
    file_size = os.path.getsize(save_path) / (1024 * 1024)
    print(f"[OK] 完成 ({file_size:.1f}MB)")
    
except Exception as e:
    print(f"[失败] {e}")
