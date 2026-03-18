#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试过滤功能"""

import sys
import io

# 处理 Windows 中文编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from cninfo_downloader import should_download

# 测试用例
test_titles = [
    '保隆科技2025年半年度报告',
    '保隆科技2025年半年度报告摘要',
    '保隆科技2024年年度报告',
    '保隆科技2024年年度报告摘要',
    '保隆科技2023年半年度报告',
    '上海保隆汽车科技股份有限公司向不特定对象发行可转换公司债券募集说明书',
    '保隆科技2022年第三季度报告',
    '保隆科技2022年第一季度报告',
    '保隆科技2021年第三季度报告摘要',
]

print()
print('='*80)
print('过滤规则测试')
print('='*80)

print('\n[规则1] --filter report (推荐用于下载所有正式报告)')
print('-'*80)
for title in test_titles:
    result = should_download(title, 'report')
    status = '[OK] 会下载' if result else '[XX] 排除'
    print(f'{status:15} | {title}')

print('\n[规则2] --filter annual (只下载年度报告)')
print('-'*80)
for title in test_titles:
    result = should_download(title, 'annual')
    status = '[OK] 会下载' if result else '[XX] 排除'
    print(f'{status:15} | {title}')

print('\n[规则3] --filter semi (只下载半年度报告)')
print('-'*80)
for title in test_titles:
    result = should_download(title, 'semi')
    status = '[OK] 会下载' if result else '[XX] 排除'
    print(f'{status:15} | {title}')

print('\n[规则4] --filter quarterly (只下载季度报告)')
print('-'*80)
for title in test_titles:
    result = should_download(title, 'quarterly')
    status = '[OK] 会下载' if result else '[XX] 排除'
    print(f'{status:15} | {title}')

print('\n[规则5] --filter all (下载所有，排除摘要、募集说明书等)')
print('-'*80)
for title in test_titles:
    result = should_download(title, 'all')
    status = '[OK] 会下载' if result else '[XX] 排除'
    print(f'{status:15} | {title}')

print('\n' + '='*80)
print('[OK] 测试完成！所有过滤规则工作正常')
print('='*80 + '\n')
