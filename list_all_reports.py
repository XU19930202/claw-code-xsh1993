import requests
import time
from datetime import datetime
import sys
import io

# 修复Windows编码问题
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
}

# 多页查询所有中期报告
all_reports = []
for page in range(1, 5):
    data = {
        "stock": "000807,gssz0000807",
        "tabName": "fulltext",
        "pageSize": 30,
        "pageNum": page,
        "column": "szse",
        "category": "category_bgjz_szsh",
        "searchkey": "",
        "seDate": "",
        "plate": "",
        "secid": "",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    
    url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    
    try:
        resp = requests.post(url, data=data, headers=headers, timeout=20)
        resp.raise_for_status()
        result = resp.json()
        
        announcements = result.get("announcements", [])
        if not announcements:
            print(f"第{page}页无数据")
            break
        
        print(f"第{page}页找到 {len(announcements)} 条")
        all_reports.extend(announcements)
        
    except Exception as e:
        print(f"第{page}页查询失败: {e}")
        break
    
    time.sleep(1)

print(f"\n总共找到 {len(all_reports)} 条中期报告\n")

# 按时间倒序，显示最新的10条
all_reports.sort(key=lambda x: x.get("announcementTime", 0), reverse=True)

for i, ann in enumerate(all_reports[:15], 1):
    title = ann.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
    ann_time = ann.get("announcementTime", 0)
    adjunct_url = ann.get("adjunctUrl", "")
    
    date_str = datetime.fromtimestamp(ann_time/1000).strftime("%Y-%m-%d") if ann_time else "unknown"
    
    print(f"[{i}] {date_str} - {title}")
    if "2025" in title or "2024" in title or "2023" in title:
        print(f"    [OK] 需要的报告")
        if adjunct_url:
            print(f"    URL: http://static.cninfo.com.cn/{adjunct_url}")
    print()
