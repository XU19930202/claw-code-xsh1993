#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""演示过滤功能的实际效果"""

import sys
import io

# 处理 Windows 中文编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 模拟的搜索结果（来自真实数据）
search_results = [
    {'title': '保隆科技2025年半年度报告', 'date': '2025-08-29', 'code': '603197'},
    {'title': '保隆科技2025年半年度报告摘要', 'date': '2025-08-29', 'code': '603197'},
    {'title': '保隆科技2024年年度报告', 'date': '2025-04-30', 'code': '603197'},
    {'title': '保隆科技2024年年度报告摘要', 'date': '2025-04-30', 'code': '603197'},
    {'title': '保隆科技2024年半年度报告摘要', 'date': '2024-08-30', 'code': '603197'},
    {'title': '保隆科技2024年半年度报告', 'date': '2024-08-30', 'code': '603197'},
    {'title': '保隆科技2023年年度报告摘要', 'date': '2024-04-27', 'code': '603197'},
    {'title': '保隆科技2023年年度报告', 'date': '2024-04-27', 'code': '603197'},
    {'title': '上海保隆汽车科技股份有限公司向不特定对象发行可转换公司债券募集说明书', 'date': '2023-09-13', 'code': '603197'},
    {'title': '保隆科技2023年半年度报告摘要', 'date': '2023-08-30', 'code': '603197'},
    {'title': '保隆科技2023年半年度报告', 'date': '2023-08-30', 'code': '603197'},
]

from cninfo_downloader import should_download

# 测试各个过滤规则
test_cases = [
    ('all', '下载所有（排除摘要、募集说明书等）'),
    ('report', '只下载正式报告（年报、半年报、季报）'),
    ('annual', '只下载年度报告'),
    ('semi', '只下载半年度报告'),
]

print()
print('='*80)
print('实战演示：保隆科技财务报告下载过滤')
print('='*80)
print()

for filter_type, description in test_cases:
    filtered = [r for r in search_results if should_download(r['title'], filter_type)]
    
    print(f'命令: python cninfo_downloader.py -k "保隆科技年报" --filter {filter_type} --download')
    print(f'说明: {description}')
    print(f'结果: 原始 {len(search_results)} 条 → 过滤后 {len(filtered)} 条')
    print()
    
    for i, result in enumerate(filtered, 1):
        print(f'  {i:2}. [{result["code"]}] {result["date"]} | {result["title"]}')
    
    print()

print('='*80)
print('总结')
print('='*80)
print()
print('  使用过滤后的优势:')
print('  ✓ --filter report   下载最常用的正式报告（节省 36% 流量）')
print('  ✓ --filter annual   只获取完整年报（最详细的财务信息）')
print('  ✓ --filter semi     按需获取半年度报告')
print('  ✓ 自动排除摘要版本、募集说明书等无用文件')
print()

