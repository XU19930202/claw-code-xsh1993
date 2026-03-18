#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import re
from datetime import datetime

keywords = [
    '603197 年报',
    '保隆 年度报告',
    '保隆科技 年度',
    '保隆科技 2024',
]

url = 'http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Content-Type': 'application/x-www-form-urlencoded',
}

print("搜索保隆科技 2024 年报...")
print("=" * 80)

for keyword in keywords:
    data = {
        'searchkey': keyword,
        'pageNum': 1,
        'pageSize': 100,
        'column': 'szse',
        'tabName': 'fulltext',
    }
    
    try:
        resp = requests.post(url, data=data, headers=headers, timeout=15)
        result = resp.json()
        anns = result.get('announcements') or []
        
        for ann in anns:
            title = re.sub(r'<[^>]+>', '', ann.get('announcementTitle', ''))
            code = ann.get('secCode', '')
            
            # 找保隆科技的年报
            if '603197' in str(code) and '2024' in title and '年报' in title:
                date_ts = ann.get('announcementTime', 0)
                date_str = datetime.fromtimestamp(date_ts / 1000).strftime('%Y-%m-%d')
                url_pdf = 'http://static.cninfo.com.cn/' + ann.get('adjunctUrl', '')
                
                print(f"\n找到: {title}")
                print(f"日期: {date_str}")
                print(f"URL: {url_pdf}")
                
    except Exception as e:
        pass

print("\n" + "=" * 80)
