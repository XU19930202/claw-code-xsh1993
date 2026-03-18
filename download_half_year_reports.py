#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载中期（半年度）报告
"""

import os
import sys
import json
import time
import random
import requests
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

def get_stock_org_id(stock_code: str):
    """获取股票的orgId"""
    url = "http://www.cninfo.com.cn/new/information/topSearch/query"
    data = {"keyWord": stock_code, "maxNum": 5}
    
    try:
        resp = requests.post(url, data=data, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        
        if not result:
            return None
        
        for item in result:
            if item.get("code") == stock_code:
                return {
                    "orgId": item.get("orgId"),
                    "code": item.get("code"),
                    "name": item.get("zwjc", ""),
                    "category": item.get("category", ""),
                }
        
        first = result[0]
        return {
            "orgId": first.get("orgId"),
            "code": first.get("code"),
            "name": first.get("zwjc", ""),
            "category": first.get("category", ""),
        }
    except Exception as e:
        print(f"查询失败: {e}")
        return None

def query_half_year_reports(stock_code: str, org_id: str, plate: str = ""):
    """查询半年度报告"""
    all_announcements = []
    page = 1
    
    while page <= 20:
        data = {
            "stock": f"{stock_code},{org_id}",
            "tabName": "fulltext",
            "pageSize": 30,
            "pageNum": page,
            "column": plate if plate else "szse",
            "category": "category_bgjz_szsh",
            "plate": "",
            "seDate": "",
            "searchkey": "",
            "secid": "",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        
        try:
            resp = requests.post(
                CNINFO_QUERY_URL, data=data, headers=HEADERS, timeout=20
            )
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
            time.sleep(random.uniform(0.5, 1.0))
        
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
if __name__ == "__main__":
    stock_code = sys.argv[1] if len(sys.argv) > 1 else "000807"
    
    print(f"正在查询{stock_code}的中期报告...")
    
    stock_info = get_stock_org_id(stock_code)
    if not stock_info:
        print("未找到股票信息")
        sys.exit(1)
    
    print(f"公司: {stock_info['name']} ({stock_info['code']})")
    
    time.sleep(1)
    
    # 查询中期报告
    announcements = query_half_year_reports(stock_info["code"], stock_info["orgId"], "szse")
    print(f"找到 {len(announcements)} 条中期报告相关公告")
    
    # 过滤正式中期报告
    filtered = []
    for ann in announcements:
        title = ann.get("announcementTitle", "")
        
        if "中期报告" not in title and "半年报" not in title and "中报" not in title:
            continue
        
        if any(kw in title for kw in ["摘要", "更正", "补充", "说明", "意见", "英文", "English"]):
            continue
        
        filtered.append(ann)
    
    filtered.sort(key=lambda x: x.get("announcementTime", 0))
    
    print(f"筛选出 {len(filtered)} 份正式中期报告")
    
    if not filtered:
        print("未找到有效的中期报告")
        sys.exit(0)
    
    # 创建保存目录
    stock_dir = os.path.join(SAVE_DIR, f"{stock_info['code']}_{stock_info['name']}")
    os.makedirs(stock_dir, exist_ok=True)
    
    # 下载
    print("\n开始下载...")
    success_count = 0
    
    for i, report in enumerate(filtered, 1):
        title = report.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
        adjunct_url = report.get("adjunctUrl", "")
        ann_time = report.get("announcementTime", 0)
        
        if not adjunct_url:
            continue
        
        # 从标题提取年份
        match = re.search(r"(\d{4})", title)
        year = match.group(1) if match else "unknown"
        
        # 判断是上半年还是下半年
        period = "上半年" if "上" in title or "一" in title else "下半年"
        
        filename = f"{stock_info['code']}_{stock_info['name']}_{year}年{period}中期报告.pdf"
        
        # 清理文件名
        for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
            filename = filename.replace(char, '_')
        
        save_path = os.path.join(stock_dir, filename)
        
        # 检查是否已存在
        if os.path.exists(save_path) and os.path.getsize(save_path) > 10240:
            print(f"  [{i}/{len(filtered)}] 已存在，跳过")
            continue
        
        # 下载
        download_url = CNINFO_DOWNLOAD_BASE + adjunct_url
        print(f"  [{i}/{len(filtered)}] 下载: {filename}")
        
        if download_pdf(download_url, save_path):
            file_size = os.path.getsize(save_path) / (1024 * 1024)
            print(f"           [OK] 完成 ({file_size:.1f}MB)")
            success_count += 1
        else:
            print(f"           [失败]")
        
        time.sleep(random.uniform(1.5, 3.0))
    
    print(f"\n下载完成! 成功{success_count}份")
    print(f"保存目录: {stock_dir}")
