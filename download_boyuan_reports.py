#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""下载博源化工（000683）的年度报告和半年度报告"""

import requests
import time
import os
import re
from datetime import datetime

# 配置
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

def query_annual_reports(stock_code: str, org_id: str, plate: str):
    """查询年度报告"""
    all_announcements = []
    page = 1
    
    while page <= 20:
        data = {
            "stock": f"{stock_code},{org_id}",
            "tabName": "fulltext",
            "pageSize": 30,
            "pageNum": page,
            "column": plate,
            "category": "category_ndbg",  # 年度报告分类
            "plate": "",
            "seDate": "",
            "searchkey": "",
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
            print(f"查询年报失败: {e}")
            break
    
    return all_announcements

def query_half_year_reports(stock_code: str, org_id: str, plate: str):
    """查询半年度报告"""
    all_announcements = []
    page = 1
    
    while page <= 20:
        data = {
            "stock": f"{stock_code},{org_id}",
            "tabName": "fulltext",
            "pageSize": 30,
            "pageNum": page,
            "column": plate,
            "category": "category_bgjz_szsh",  # 中期报告分类
            "plate": "",
            "seDate": "",
            "searchkey": "",
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
            print(f"查询半年报失败: {e}")
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
        if file_size < 10240:  # 小于10KB则删除
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
plate = "szse"  # 深交所

# 创建保存目录
stock_dir = os.path.join(SAVE_DIR, "000683_博源化工")
os.makedirs(stock_dir, exist_ok=True)

# 下载年报
print("\n[1/2] 查询年度报告...")
annual_reports = query_annual_reports(stock_code, org_id, plate)
print(f"找到 {len(annual_reports)} 条年度报告相关公告")

# 过滤正式年报（不包含摘要、更正等）
filtered_annual = []
for ann in annual_reports:
    title = ann.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
    
    # 必须包含"年度报告"
    if "年度报告" not in title:
        continue
    
    # 排除摘要等
    if any(kw in title for kw in ["摘要", "更正", "补充", "英文", "English"]):
        continue
    
    filtered_annual.append(ann)

# 按时间排序并取最近3年
filtered_annual.sort(key=lambda x: x.get("announcementTime", 0), reverse=True)
filtered_annual = filtered_annual[:3]  # 只要最近3年

print(f"筛选出 {len(filtered_annual)} 份正式年度报告")

# 下载年报
print("\n正在下载年度报告...")
for i, report in enumerate(filtered_annual, 1):
    title = report.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
    adjunct_url = report.get("adjunctUrl", "")
    
    if not adjunct_url:
        continue
    
    # 从标题提取年份
    match = re.search(r"(\d{4})", title)
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

# 下载半年报
print("\n[2/2] 查询半年度报告...")
half_year_reports = query_half_year_reports(stock_code, org_id, plate)
print(f"找到 {len(half_year_reports)} 条半年度报告相关公告")

# 过滤正式半年报
filtered_half = []
for ann in half_year_reports:
    title = ann.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
    
    # 必须包含"中期报告"或"半年报"
    if "中期报告" not in title and "半年报" not in title:
        continue
    
    # 排除摘要等
    if any(kw in title for kw in ["摘要", "更正", "补充", "英文", "English"]):
        continue
    
    filtered_half.append(ann)

# 按时间排序并取最近1期
filtered_half.sort(key=lambda x: x.get("announcementTime", 0), reverse=True)
filtered_half = filtered_half[:1]  # 只要最近1期

print(f"筛选出 {len(filtered_half)} 份正式半年度报告")

# 下载半年报
print("\n正在下载半年度报告...")
for i, report in enumerate(filtered_half, 1):
    title = report.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
    adjunct_url = report.get("adjunctUrl", "")
    
    if not adjunct_url:
        continue
    
    # 从标题提取年份
    match = re.search(r"(\d{4})", title)
    year = match.group(1) if match else "unknown"
    
    # 判断是上半年还是下半年
    period = "上半年" if "上" in title or "一" in title or "中" in title else "下半年"
    
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
