#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""下载博源化工3年一期的正式财务报告（最终版本）"""

import requests
import time
import os
from datetime import datetime

SAVE_DIR = os.path.join(os.path.dirname(__file__), "annual_reports")
CNINFO_DOWNLOAD_BASE = "http://static.cninfo.com.cn/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

def download_pdf(url: str, save_path: str) -> bool:
    """下载PDF"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=120, stream=True)
        resp.raise_for_status()
        
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        
        file_size = os.path.getsize(save_path)
        if file_size < 10240:
            os.remove(save_path)
            return False
        
        return True
    except Exception as e:
        print(f"下载失败: {e}")
        if os.path.exists(save_path):
            os.remove(save_path)
        return False

# 主程序
print("=" * 80)
print("博源化工（000683）财务报告下载 - 最终版本")
print("=" * 80)

stock_dir = os.path.join(SAVE_DIR, "000683_博源化工")
os.makedirs(stock_dir, exist_ok=True)

# 定义要下载的报告列表
# URL来自之前的查询结果
reports = [
    # 年度报告
    ("000683_博源化工_2024年年度报告.pdf", "http://static.cninfo.com.cn/finalpage/2024-03-28/1218858883.PDF"),
    ("000683_博源化工_2023年年度报告.pdf", "http://static.cninfo.com.cn/finalpage/2023-04-28/1215829346.PDF"),
    ("000683_博源化工_2022年年度报告.pdf", "http://static.cninfo.com.cn/finalpage/2023-04-15/1215693149.PDF"),
    # 中期报告（最近一期）
    ("000683_博源化工_2025年上半年中期报告.pdf", "http://static.cninfo.com.cn/finalpage/2025-08-08/1224424873.PDF"),
]

print("\n正在下载报告...\n")

downloaded_count = 0
for filename, url in reports:
    save_path = os.path.join(stock_dir, filename)
    
    # 检查是否已存在
    if os.path.exists(save_path) and os.path.getsize(save_path) > 10240:
        print(f"[skip] 已存在: {filename}")
        downloaded_count += 1
        continue
    
    print(f"[{downloaded_count + 1}/{len(reports)}] 下载: {filename}")
    
    if download_pdf(url, save_path):
        file_size = os.path.getsize(save_path) / (1024 * 1024)
        print(f"      [OK] 完成 ({file_size:.1f}MB)")
        downloaded_count += 1
    else:
        print(f"      [失败]")
    
    time.sleep(1.0)

print("\n" + "=" * 80)
print("下载完成！")
print(f"保存目录: {stock_dir}")
print(f"已下载: {downloaded_count}/{len(reports)} 份报告")
print("=" * 80)
