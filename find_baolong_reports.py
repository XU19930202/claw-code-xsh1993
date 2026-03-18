#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查找保隆科技的 2024 年报、2025 半年报和三季报
"""
import requests
import re
from datetime import datetime

def search_announcements(keyword, page=1):
    """搜索公告"""
    url = 'http://www.cninfo.com.cn/new/hisAnnouncement/query'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    
    data = {
        'searchkey': keyword,
        'pageNum': page,
        'pageSize': 100,
        'column': 'szse',
        'tabName': 'fulltext',
    }
    
    try:
        resp = requests.post(url, data=data, headers=headers, timeout=15)
        result = resp.json()
        return result.get('announcements', []) or [], result.get('totalAnnouncement', 0)
    except Exception as e:
        print(f"  错误: {e}")
        return [], 0

# 搜索关键词
search_terms = [
    '保隆科技 2024年度报告',
    '保隆科技 2025年半年度报告',
    '保隆科技 2025年三季度报告',
]

print("=" * 80)
print("查找保隆科技财务报告")
print("=" * 80)

all_reports = []

for keyword in search_terms:
    print(f"\n搜索: {keyword}")
    anns, total = search_announcements(keyword)
    print(f"找到 {len(anns)} 条记录\n")
    
    for i, ann in enumerate(anns):
        title = re.sub(r'<[^>]+>', '', ann.get('announcementTitle', ''))
        date_ts = ann.get('announcementTime', 0)
        date_str = datetime.fromtimestamp(date_ts / 1000).strftime("%Y-%m-%d") if date_ts else "N/A"
        code = ann.get('secCode', '')
        
        if code == '603197':  # 保隆科技
            url = 'http://static.cninfo.com.cn/' + ann.get('adjunctUrl', '')
            
            print(f"  [{i+1}] {title}")
            print(f"      日期: {date_str}")
            print(f"      URL: {url}")
            
            all_reports.append({
                'title': title,
                'date': date_str,
                'url': url,
                'keyword': keyword
            })

print("\n" + "=" * 80)
print(f"总共找到 {len(all_reports)} 份报告")
print("=" * 80)

# 保存 URL 列表
if all_reports:
    print("\n下载 URL 列表:\n")
    for report in all_reports:
        print(f"# {report['keyword']}")
        print(f"# 日期: {report['date']}")
        print(f"{report['url']}\n")
