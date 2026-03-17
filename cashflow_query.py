#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
现金流三表查询 - 上市以来全部数据
用法: python cashflow_query.py 603197
输出: cashflow_{代码}.png
"""

import sys, os, warnings
warnings.filterwarnings('ignore')
import tushare as ts
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

TUSHARE_TOKEN = "a009b833ddc8257726296c9d51574cb6c18315e937eeeeb79ce4e61e"

def get_cn_font():
    for fp in ['/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
               '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
               'C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf',
               '/System/Library/Fonts/PingFang.ttc']:
        if os.path.exists(fp):
            return fm.FontProperties(fname=fp)
    return fm.FontProperties()

CN_FONT = get_cn_font()

def query_cashflow(ts_code):
    ts.set_token(TUSHARE_TOKEN)
    pro = ts.pro_api()

    # 获取公司名称
    try:
        info = pro.stock_basic(ts_code=ts_code, fields='name')
        name = info.iloc[0]['name'] if not info.empty else ts_code
    except:
        name = ts_code

    # 分段拉取上市以来全部现金流数据
    fields = 'ts_code,ann_date,end_date,n_cashflow_act,n_cashflow_inv_act,n_cash_flows_fnc_act,net_profit'
    dfs = []
    for start, end in [('19900101','20101231'), ('20110101','20201231'), ('20210101','20301231')]:
        try:
            tmp = pro.cashflow(ts_code=ts_code, start_date=start, end_date=end, fields=fields)
            if tmp is not None and not tmp.empty:
                dfs.append(tmp)
        except:
            pass

    if not dfs:
        print(f"未找到 {ts_code} 的现金流数据"); return None

    df = pd.concat(dfs).drop_duplicates(subset=['end_date']).sort_values('end_date')

    # 只保留年报数据(12月底) + 最新非年报季度
    annual = df[df['end_date'].str.endswith('1231')].copy()
    latest_annual_end = annual['end_date'].max() if not annual.empty else '00000000'
    newer = df[df['end_date'] > latest_annual_end]
    if not newer.empty:
        latest_q = newer.sort_values('end_date').iloc[-1:]
        display_df = pd.concat([annual, latest_q])
    else:
        display_df = annual

    display_df = display_df.sort_values('end_date').reset_index(drop=True)

    # 转换为亿元
    for col in ['n_cashflow_act','n_cashflow_inv_act','n_cash_flows_fnc_act','net_profit']:
        display_df[col] = display_df[col] / 1e8

    # 计算年报合计
    annual_only = display_df[display_df['end_date'].str.endswith('1231')]
    totals = {
        'oper': annual_only['n_cashflow_act'].sum(),
        'inv': annual_only['n_cashflow_inv_act'].sum(),
        'fin': annual_only['n_cash_flows_fnc_act'].sum(),
        'np': annual_only['net_profit'].sum(),
    }

    # 绘图
    fig, ax = plt.subplots(figsize=(max(14, len(display_df)*1.2), max(8, len(display_df)*0.4+3)))
    ax.axis('off')

    title = f"{name}({ts_code}) 现金流三表 | 上市以来 | 合计为年报口径"
    fig.text(0.5, 0.97, title, fontproperties=CN_FONT, fontsize=14, ha='center', va='top', fontweight='bold')

    headers = ['报告期', '经营活动CF(亿)', '投资活动CF(亿)', '筹资活动CF(亿)', '净利润(亿)']
    col_widths = [0.12, 0.22, 0.22, 0.22, 0.22]

    rows = []
    for _, r in display_df.iterrows():
        ed = r['end_date']
        month = ed[4:6]
        year = ed[:4]
        label_map = {'03': f'{year}Q1', '06': f'{year}H1', '09': f'{year}Q3', '12': f'{year}'}
        label = label_map.get(month, ed)
        rows.append([label,
            f"{r['n_cashflow_act']:.2f}", f"{r['n_cashflow_inv_act']:.2f}",
            f"{r['n_cash_flows_fnc_act']:.2f}", f"{r['net_profit']:.2f}"])

    # 合计行
    rows.append([f"合计(年报)", f"{totals['oper']:.2f}", f"{totals['inv']:.2f}",
                 f"{totals['fin']:.2f}", f"{totals['np']:.2f}"])

    table = ax.table(cellText=rows, colLabels=headers, colWidths=col_widths,
                     loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.4)

    # 样式
    for (row, col), cell in table.get_celld().items():
        cell.set_text_props(fontproperties=CN_FONT)
        if row == 0:
            cell.set_facecolor('#1565c0')
            cell.set_text_props(color='white', fontweight='bold', fontproperties=CN_FONT)
        elif row == len(rows):  # 合计行
            cell.set_facecolor('#e3f2fd')
            cell.set_text_props(fontweight='bold', fontproperties=CN_FONT)
        else:
            cell.set_facecolor('#f5f5f5' if row % 2 == 0 else 'white')
            # 数值着色
            if col > 0:
                try:
                    val = float(cell.get_text().get_text())
                    cell.set_text_props(color='#c62828' if val < 0 else '#2e7d32')
                except:
                    pass

    output = f"cashflow_{ts_code.replace('.','_')}.png"
    plt.savefig(output, dpi=150, bbox_inches='tight', facecolor='white', pad_inches=0.1)
    plt.close()
    print(f"已生成: {output}")
    return output

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python cashflow_query.py 603197"); sys.exit(1)
    tc = sys.argv[1].strip().upper()
    if not tc.endswith(('.SH','.SZ','.BJ')):
        c = tc.replace('.','')
        tc = c + ('.SH' if c[0] in '69' else '.SZ' if c[0] in '032' else '.BJ' if c[0] in '48' else '.SH')
    query_cashflow(tc)
