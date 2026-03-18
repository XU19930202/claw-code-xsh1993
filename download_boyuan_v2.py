#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""下载博源化工3年一期的正式财务报告"""

import requests
import time
import os
import re
from datetime import datetime

SAVE_DIR = os.path.join(os.path.dirname(__file__), "annual_reports")
CNINFO_QUERY_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_DOWNLOAD_BASE = "http://static.cninfo.com.cn/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "http://www.cninfo.com.cn",
    "Referer": "http://www.cninfo.com.cn/new/disclosure/stock",
}

def query_reports_with_keyword(stock_code: str, org_id: str, plate: str, keyword: str, page_limit=5):
    """用关键字查询报告"""
    all_announcements = []
    page = 1
    
    while page <= page_limit:
        data = {
            "stock": f"{stock_code},{org_id}",
            "tabName": "fulltext",
            "pageSize": 30,
            "pageNum": page,
            "column": plate,
            "category": "",
            "plate": "",
            "seDate": "",
            "searchkey": keyword,
            "secid": "",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        
        try:
            resp = requests.post(CNINFO_QUERY_URL, data=data, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            result = resp.json()
            
            announcements = result.get("announcements", [])
            if not announcements:
                break
            
            all_announcements.extend(announcements)
            
            total_pages = result.get("totalpages", 1)
            if page >= total_pages:
                break
            
            page += 1
            time.sleep(0.5)
        
        except Exception as e:
            print(f"查询失败: {e}")
            break
    
    return all_announcements

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
print("博源化工（000683）财务报告下载")
print("=" * 80)

stock_code = "000683"
org_id = "gssz0000683"
plate = "szse"

# 创建保存目录
stock_dir = os.path.join(SAVE_DIR, "000683_博源化工")
os.makedirs(stock_dir, exist_ok=True)

# 下载年报（关键字搜索"年度报告"）
print("\n[1/2] 查询年度报告...")
annual_reports = query_reports_with_keyword(stock_code, org_id, plate, "年度报告", page_limit=3)
print(f"找到 {len(annual_reports)} 条年度报告")

# 过滤：必须是"年度报告"且不是摘要或其他变体
filtered_annual = []
for ann in annual_reports:
    title = ann.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
    
    # 必须包含"年度报告"
    if "年度报告" not in title:
        continue
    
    # 排除摘要、更正等
    if any(kw in title for kw in ["摘要", "更正", "补充", "英文", "English", "draft", "草案"]):
        continue
    
    # 排除股东大会、中期等非年报
    if any(kw in title for kw in ["股东大会", "中期", "一季", "三季"]):
        continue
    
    filtered_annual.append(ann)

# 按时间排序，取年份范围在2022-2024的
filtered_annual.sort(key=lambda x: x.get("announcementTime", 0), reverse=True)

# 提取年份并过滤出2024、2023、2022三年的年报
target_annual = []
years_found = set()

for ann in filtered_annual:
    title = ann.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
    
    # 从标题中提取年份
    match = re.search(r"(202[0-4])", title)
    if not match:
        continue
    
    year = match.group(1)
    
    # 只收集2022-2024的年报，每年只要一份
    if year in ["2024", "2023", "2022"] and year not in years_found:
        target_annual.append(ann)
        years_found.add(year)
    
    # 如果收集够了3年就停止
    if len(target_annual) >= 3:
        break

print(f"筛选出 {len(target_annual)} 份正式年度报告：{', '.join(sorted(years_found, reverse=True))}")

# 下载年报
print("\n正在下载年度报告...")
for i, report in enumerate(target_annual, 1):
    title = report.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
    adjunct_url = report.get("adjunctUrl", "")
    
    if not adjunct_url:
        print(f"  [{i}] 跳过: {title}（无附件）")
        continue
    
    # 从标题提取年份
    match = re.search(r"(202[0-4])", title)
    year = match.group(1) if match else "unknown"
    
    filename = f"000683_博源化工_{year}年年度报告.pdf"
    save_path = os.path.join(stock_dir, filename)
    
    # 检查是否已存在
    if os.path.exists(save_path) and os.path.getsize(save_path) > 10240:
        print(f"  [{i}] 已存在: {filename}")
        continue
    
    # 下载
    download_url = CNINFO_DOWNLOAD_BASE + adjunct_url
    print(f"  [{i}] 下载: {filename}")
    
    if download_pdf(download_url, save_path):
        file_size = os.path.getsize(save_path) / (1024 * 1024)
        print(f"      [OK] 完成 ({file_size:.1f}MB)")
    else:
        print(f"      [失败]")
    
    time.sleep(1.5)

# 下载半年报（中期报告）
print("\n[2/2] 查询中期报告...")
half_year_reports = query_reports_with_keyword(stock_code, org_id, plate, "中期报告", page_limit=3)
print(f"找到 {len(half_year_reports)} 条中期报告")

# 过滤：正式的中期报告
filtered_half = []
for ann in half_year_reports:
    title = ann.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
    
    # 必须包含"中期报告"
    if "中期报告" not in title:
        continue
    
    # 排除摘要、更正等
    if any(kw in title for kw in ["摘要", "更正", "补充", "英文", "English", "draft", "草案"]):
        continue
    
    filtered_half.append(ann)

# 按时间排序，取最新的一份
filtered_half.sort(key=lambda x: x.get("announcementTime", 0), reverse=True)
filtered_half = filtered_half[:1]

print(f"筛选出 {len(filtered_half)} 份正式中期报告")

# 下载半年报
print("\n正在下载中期报告...")
for i, report in enumerate(filtered_half, 1):
    title = report.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
    adjunct_url = report.get("adjunctUrl", "")
    
    if not adjunct_url:
        print(f"  [{i}] 跳过: {title}（无附件）")
        continue
    
    # 从标题提取年份
    match = re.search(r"(202[0-9])", title)
    year = match.group(1) if match else "unknown"
    
    # 判断是上半年还是下半年
    period = "上半年" if "上" in title or "一" in title else "下半年"
    
    filename = f"000683_博源化工_{year}年{period}中期报告.pdf"
    save_path = os.path.join(stock_dir, filename)
    
    # 检查是否已存在
    if os.path.exists(save_path) and os.path.getsize(save_path) > 10240:
        print(f"  [{i}] 已存在: {filename}")
        continue
    
    # 下载
    download_url = CNINFO_DOWNLOAD_BASE + adjunct_url
    print(f"  [{i}] 下载: {filename}")
    
    if download_pdf(download_url, save_path):
        file_size = os.path.getsize(save_path) / (1024 * 1024)
        print(f"      [OK] 完成 ({file_size:.1f}MB)")
    else:
        print(f"      [失败]")
    
    time.sleep(1.5)

print("\n" + "=" * 80)
print("下载完成！")
print(f"保存目录: {stock_dir}")
print("=" * 80)
