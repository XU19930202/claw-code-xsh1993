#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import time
import os
from datetime import datetime
import sys
import io

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SAVE_DIR = os.path.join(os.path.dirname(__file__), "annual_reports", "000807_云铝股份")
os.makedirs(SAVE_DIR, exist_ok=True)

CNINFO_QUERY_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_DOWNLOAD_BASE = "http://static.cninfo.com.cn/"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "http://www.cninfo.com.cn",
    "Referer": "http://www.cninfo.com.cn/new/disclosure/stock",
}

def download_pdf(url, filename):
    """下载PDF文件"""
    try:
        print(f"  正在下载: {filename}")
        resp = requests.get(url, headers=headers, timeout=120, stream=True)
        resp.raise_for_status()
        
        save_path = os.path.join(SAVE_DIR, filename)
        with open(save_path, "wb") as f:
            total = 0
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    total += len(chunk)
        
        file_size = os.path.getsize(save_path) / (1024 * 1024)
        print(f"    [OK] 完成 ({file_size:.1f}MB)")
        return True
    except Exception as e:
        print(f"    [失败] {e}")
        return False

# 查询并下载报告
print("开始查询云铝股份中期报告...\n")

all_reports = []

for year in [2025, 2024, 2023]:
    print(f"查询 {year} 年中期报告:")
    
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    se_date = f"{start_date}~{end_date}"
    
    data = {
        "stock": "000807,gssz0000807",
        "tabName": "fulltext",
        "pageSize": 30,
        "pageNum": 1,
        "column": "szse",
        "category": "category_bgjz_szsh",
        "searchkey": "中期报告",
        "seDate": se_date,
        "plate": "",
        "secid": "",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    
    try:
        resp = requests.post(CNINFO_QUERY_URL, data=data, headers=headers, timeout=20)
        resp.raise_for_status()
        result = resp.json()
        
        announcements = result.get("announcements", [])
        print(f"  找到 {len(announcements)} 条公告")
        
        # 筛选正式报告（排除摘要）
        for ann in announcements:
            title = ann.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
            adjunct_url = ann.get("adjunctUrl", "")
            ann_time = ann.get("announcementTime", 0)
            
            # 排除摘要和审核意见
            if "摘要" in title or "审核意见" in title:
                continue
            
            if adjunct_url:
                date_str = datetime.fromtimestamp(ann_time/1000).strftime("%Y%m%d")
                filename = f"000807_云铝股份_{year}年半年度报告.pdf"
                
                # 清理文件名
                for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                    filename = filename.replace(char, '_')
                
                all_reports.append({
                    "year": year,
                    "title": title,
                    "url": CNINFO_DOWNLOAD_BASE + adjunct_url,
                    "filename": filename,
                    "date": date_str
                })
                print(f"  - {title}")
    
    except Exception as e:
        print(f"  查询失败: {e}")
    
    time.sleep(1)

# 下载报告
print(f"\n共找到 {len(all_reports)} 份报告，开始下载...\n")

for i, report in enumerate(all_reports, 1):
    print(f"[{i}/{len(all_reports)}] 下载 {report['year']} 年报告")
    download_pdf(report["url"], report["filename"])
    time.sleep(1)

print(f"\n下载完成！报告已保存到: {SAVE_DIR}")
