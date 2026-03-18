#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import time
from datetime import datetime
import sys
import io
import os

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SAVE_DIR = os.path.join(os.path.dirname(__file__), "annual_reports", "000830_鲁西化工")
os.makedirs(SAVE_DIR, exist_ok=True)

CNINFO_QUERY_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_DOWNLOAD_BASE = "http://static.cninfo.com.cn/"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
}

def download_pdf(url, filename):
    """下载PDF文件"""
    try:
        print(f"  正在下载: {filename}")
        resp = requests.get(url, headers=headers, timeout=120, stream=True)
        resp.raise_for_status()
        
        save_path = os.path.join(SAVE_DIR, filename)
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        file_size = os.path.getsize(save_path) / (1024 * 1024)
        print(f"    [OK] 完成 ({file_size:.1f}MB)")
        return True
    except Exception as e:
        print(f"    [失败] {e}")
        return False

print("=" * 70)
print(" 鲁西化工 财务报告下载器")
print("=" * 70)

all_reports = []

# 查询三种报告类型
report_types = [
    ("category_ndbg_szsh", "年报", [2024, 2023]),
    ("category_bndbg_szsh", "半年报", [2025]),
]

print("\n[第1步] 查询报告列表...\n")

for category, report_name, years in report_types:
    for year in years:
        print(f"查询 {year}年{report_name}:")
        
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        se_date = f"{start_date}~{end_date}"
        
        data = {
            "stock": "000830,gssz0000830",
            "tabName": "fulltext",
            "pageSize": 30,
            "pageNum": 1,
            "column": "szse",
            "category": category,
            "searchkey": report_name,
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
            
            if not result:
                print(f"  无结果")
                time.sleep(1)
                continue
            
            announcements = result.get("announcements", [])
            print(f"  找到 {len(announcements)} 条公告")
            
            for ann in announcements:
                title = ann.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
                adjunct_url = ann.get("adjunctUrl", "")
                
                # 只要正式报告，排除摘要、审核意见
                if "摘要" in title or "审核意见" in title:
                    continue
                
                if adjunct_url:
                    print(f"    找到: {title}")
                    
                    # 生成文件名
                    if report_name == "年报":
                        filename = f"000830_鲁西化工_{year}年年度报告.pdf"
                    else:  # 半年报
                        filename = f"000830_鲁西化工_{year}年上半年度报告.pdf"
                    
                    all_reports.append({
                        "title": title,
                        "filename": filename,
                        "url": CNINFO_DOWNLOAD_BASE + adjunct_url,
                    })
                    break  # 找到正式报告后就停止
        
        except Exception as e:
            print(f"  查询出错: {e}")
        
        time.sleep(1)

# 下载
print(f"\n[第2步] 开始下载 {len(all_reports)} 份报告...\n")

for i, report in enumerate(all_reports, 1):
    print(f"[{i}/{len(all_reports)}] {report['filename']}")
    download_pdf(report["url"], report["filename"])
    time.sleep(1)

print(f"\n" + "=" * 70)
print(f"下载完成!")
print(f"保存目录: {SAVE_DIR}")
print("=" * 70)
