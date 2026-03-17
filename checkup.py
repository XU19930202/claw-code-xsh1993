#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公司财务体检报告
四维度：现金流能力、资产负债/杠杆、利润增长、估值水平
自动评分 + 数据卡 + 文字结论

用法: python checkup.py 603197
输出: checkup_{代码}.png
"""

import sys, os, warnings, time
warnings.filterwarnings('ignore')
import tushare as ts
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

TUSHARE_TOKEN = "a009b833ddc8257726296c9d51574cb6c18315e937eeeeb79ce4e61e"
YEARS_BACK = 3

def get_cn_font():
    for fp in ['/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
               '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
               'C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf',
               '/System/Library/Fonts/PingFang.ttc']:
        if os.path.exists(fp):
            return fm.FontProperties(fname=fp)
    return fm.FontProperties()

CN_FONT = get_cn_font()

def safe(val):
    if val is None or (isinstance(val, float) and np.isnan(val)): return None
    return val

def collect_data(ts_code):
    ts.set_token(TUSHARE_TOKEN)
    pro = ts.pro_api()
    data = {"ts_code": ts_code}

    # 公司名称
    try:
        info = pro.stock_basic(ts_code=ts_code, fields='name,list_date')
        data["name"] = info.iloc[0]['name'] if not info.empty else ts_code
        data["list_date"] = info.iloc[0]['list_date'] if not info.empty else None
    except:
        data["name"] = ts_code; data["list_date"] = None

    now_str = pd.Timestamp.now().strftime('%Y%m%d')
    start = str(int(now_str[:4]) - YEARS_BACK) + '0101'

    # 1. 现金流（上市以来）
    try:
        dfs = []
        for s, e in [('19900101','20101231'),('20110101','20201231'),('20210101','20301231')]:
            tmp = pro.cashflow(ts_code=ts_code, start_date=s, end_date=e,
                fields='end_date,n_cashflow_act,n_cashflow_inv_act,n_cash_flows_fnc_act,net_profit')
            if tmp is not None and not tmp.empty: dfs.append(tmp)
            time.sleep(0.3)
        if dfs:
            cf = pd.concat(dfs).drop_duplicates('end_date').sort_values('end_date')
            annual_cf = cf[cf['end_date'].str.endswith('1231')]
            data["cum_oper_cf"] = annual_cf['n_cashflow_act'].sum() / 1e8
            data["cum_inv_cf"] = annual_cf['n_cashflow_inv_act'].sum() / 1e8
            data["cum_fin_cf"] = annual_cf['n_cash_flows_fnc_act'].sum() / 1e8
            data["cum_np"] = annual_cf['net_profit'].sum() / 1e8
            data["oper_cf_ratio"] = data["cum_oper_cf"] / data["cum_np"] if data["cum_np"] != 0 else 0
            # 近3年经营CF趋势
            recent_cf = annual_cf.tail(3)['n_cashflow_act'].values
            data["oper_cf_trend"] = "持续为正" if all(v > 0 for v in recent_cf) else "波动" if any(v > 0 for v in recent_cf) else "持续为负"
            # 资金用途判断
            if abs(data["cum_inv_cf"]) > abs(data["cum_oper_cf"]) * 0.8:
                data["fund_pattern"] = "成长扩张型"
            elif data["cum_inv_cf"] > 0:
                data["fund_pattern"] = "收缩型"
            else:
                data["fund_pattern"] = "稳健经营型"
    except Exception as e:
        print(f"现金流数据异常: {e}")

    # 2. 资产负债
    try:
        bs = pro.balancesheet(ts_code=ts_code, start_date=start,
            fields='end_date,total_assets,total_liab,goodwill,fix_assets,total_cur_assets')
        if bs is not None and not bs.empty:
            bs = bs.sort_values('end_date')
            latest = bs.iloc[-1]
            data["debt_ratio"] = safe(latest['total_liab'] / latest['total_assets'] * 100) if latest['total_assets'] else None
            data["goodwill"] = safe(latest['goodwill'] / 1e8) if latest['goodwill'] else 0
            data["asset_type"] = "重资产" if latest['fix_assets'] and latest['total_assets'] and latest['fix_assets']/latest['total_assets'] > 0.3 else "轻资产"
        time.sleep(0.3)
    except: pass

    # 3. 利润增长
    try:
        inc = pro.income(ts_code=ts_code, start_date=start,
            fields='end_date,revenue,n_income_attr_p,dedu_profit')
        if inc is not None and not inc.empty:
            inc = inc.sort_values('end_date')
            # 单季度数据
            annual_inc = inc[inc['end_date'].str.endswith('1231')].tail(4)
            if len(annual_inc) >= 2:
                revs = annual_inc['revenue'].values
                data["rev_yoy_avg"] = ((revs[-1]/revs[0])**(1/(len(revs)-1)) - 1) * 100 if revs[0] > 0 else 0
                data["latest_rev"] = revs[-1] / 1e8
                data["latest_rev_yoy"] = (revs[-1]/revs[-2] - 1) * 100 if revs[-2] > 0 else 0
            if len(annual_inc) >= 2:
                deds = annual_inc['dedu_profit'].values
                data["latest_ded_yoy"] = (deds[-1]/deds[-2] - 1) * 100 if deds[-2] and deds[-2] > 0 else 0
                data["dedu_vs_np"] = deds[-1]/annual_inc['n_income_attr_p'].values[-1]*100 if annual_inc['n_income_attr_p'].values[-1] else 0
        time.sleep(0.3)
    except: pass

    # 4. 估值
    try:
        daily = pro.daily_basic(ts_code=ts_code, fields='trade_date,pe_ttm,pb,total_mv')
        if daily is not None and not daily.empty:
            daily = daily.sort_values('trade_date')
            latest = daily.iloc[-1]
            data["pe_ttm"] = safe(latest['pe_ttm'])
            data["pb"] = safe(latest['pb'])
            data["total_mv"] = safe(latest['total_mv'] / 1e4) if latest['total_mv'] else None  # 亿
            # PE历史分位
            pe_series = daily['pe_ttm'].dropna()
            pe_series = pe_series[(pe_series > 0) & (pe_series < 500)]
            if len(pe_series) > 20 and data["pe_ttm"] and data["pe_ttm"] > 0:
                data["pe_pct"] = int((pe_series < data["pe_ttm"]).sum() / len(pe_series) * 100)
            # PEG
            if data.get("pe_ttm") and data.get("rev_yoy_avg") and data["rev_yoy_avg"] > 0:
                data["peg"] = data["pe_ttm"] / data["rev_yoy_avg"]
    except: pass

    return data

def score_cashflow(data):
    s = 0
    if data.get("oper_cf_ratio") and data["oper_cf_ratio"] > 1: s += 2
    elif data.get("oper_cf_ratio") and data["oper_cf_ratio"] > 0.7: s += 1
    if data.get("oper_cf_trend") == "持续为正": s += 2
    elif data.get("oper_cf_trend") == "波动": s += 1
    if data.get("fund_pattern") == "成长扩张型": s += 1
    return min(s, 5)

def score_balance(data):
    s = 3
    dr = data.get("debt_ratio", 50)
    if dr and dr < 40: s += 1
    elif dr and dr > 70: s -= 1
    if data.get("goodwill", 0) > 10: s -= 1
    if data.get("oper_cf_trend") == "持续为正" and dr and dr > 50: s += 1  # 好杠杆
    return max(0, min(s, 5))

def score_growth(data):
    s = 0
    ryoy = data.get("rev_yoy_avg", 0)
    if ryoy and ryoy > 30: s += 3
    elif ryoy and ryoy > 15: s += 2
    elif ryoy and ryoy > 5: s += 1
    dyoy = data.get("latest_ded_yoy", 0)
    if dyoy and dyoy > 30: s += 2
    elif dyoy and dyoy > 0: s += 1
    return min(s, 5)

def score_valuation(data):
    s = 3
    pe = data.get("pe_ttm")
    peg = data.get("peg")
    pct = data.get("pe_pct")
    if peg and peg < 1: s += 2
    elif peg and peg < 1.5: s += 1
    elif peg and peg > 3: s -= 1
    if pct and pct < 30: s += 1
    elif pct and pct > 80: s -= 1
    return max(0, min(s, 5))

def draw_report(data):
    s_cf = score_cashflow(data)
    s_bs = score_balance(data)
    s_gr = score_growth(data)
    s_va = score_valuation(data)
    total = s_cf + s_bs + s_gr + s_va

    fig = plt.figure(figsize=(16, 12))
    fig.patch.set_facecolor('white')

    name = data.get("name", data["ts_code"])
    mv_str = f" | 市值{data['total_mv']:.0f}亿" if data.get("total_mv") else ""
    fig.text(0.5, 0.97, f"{name}({data['ts_code']}) 财务体检报告{mv_str}",
             fontproperties=CN_FONT, fontsize=16, ha='center', va='top', fontweight='bold')
    fig.text(0.5, 0.945, f"综合评分: {total}/20 | CF:{s_cf} 负债:{s_bs} 增长:{s_gr} 估值:{s_va}",
             fontproperties=CN_FONT, fontsize=11, ha='center', va='top', color='#1565c0')

    def draw_block(x, y, w, h, title, score, items, conclusion):
        ax = fig.add_axes([x, y, w, h])
        ax.set_xlim(0, 10); ax.set_ylim(0, 10)
        ax.axis('off')
        # 标题栏
        ax.fill_between([0,10], [9.5,9.5], [10,10], color='#1565c0', alpha=0.9)
        ax.text(0.3, 9.75, f"{title} ({score}/5)", fontproperties=CN_FONT,
                fontsize=11, color='white', fontweight='bold', va='center')
        # 数据项
        for i, (label, value, color) in enumerate(items):
            if not label: continue
            row_y = 8.5 - i * 1.2
            ax.text(0.3, row_y, label, fontproperties=CN_FONT, fontsize=9, color='#666')
            ax.text(6.5, row_y, str(value), fontproperties=CN_FONT, fontsize=10, color=color, fontweight='bold')
        # 结论
        ax.text(0.3, 1.0, conclusion, fontproperties=CN_FONT, fontsize=8, color='#333',
                style='italic', wrap=True, va='top')
        ax.add_patch(plt.Rectangle((0,0), 10, 10, fill=False, edgecolor='#e0e0e0', linewidth=1))

    # 现金流
    cf_ratio = data.get("oper_cf_ratio", 0)
    cf_judge = "赚真钱" if cf_ratio > 1 else "关注回款" if cf_ratio > 0.7 else "利润含金量低"
    draw_block(0.05, 0.5, 0.43, 0.42, "现金流能力", s_cf, [
        ("累计经营CF", f"{data.get('cum_oper_cf',0):.1f}亿", "#2e7d32" if data.get('cum_oper_cf',0)>0 else "#c62828"),
        ("累计净利润", f"{data.get('cum_np',0):.1f}亿", "#333"),
        ("经营CF/净利润", f"{cf_ratio:.2f} ({cf_judge})", "#2e7d32" if cf_ratio>1 else "#f57f17"),
        ("近3年CF趋势", data.get("oper_cf_trend","-"), "#2e7d32" if data.get("oper_cf_trend")=="持续为正" else "#c62828"),
        ("资金用途模式", data.get("fund_pattern","-"), "#1565c0"),
    ], f"{'经营CF>净利润，赚的是真金白银' if cf_ratio>1 else '经营CF<净利润，关注应收账款质量'}；{data.get('fund_pattern','')}")

    # 资产负债
    dr = data.get("debt_ratio", 0)
    gw = data.get("goodwill", 0)
    leverage = "好杠杆" if dr and dr > 50 and data.get("oper_cf_trend")=="持续为正" else "需关注" if dr and dr > 60 else "稳健"
    draw_block(0.52, 0.5, 0.43, 0.42, "资产负债", s_bs, [
        ("资产负债率", f"{dr:.1f}%" if dr else "-", "#c62828" if dr and dr>60 else "#2e7d32"),
        ("商誉", f"{gw:.1f}亿", "#c62828" if gw>10 else "#2e7d32"),
        ("资产类型", data.get("asset_type","-"), "#333"),
        ("杠杆性质", leverage, "#2e7d32" if leverage=="好杠杆" else "#f57f17"),
    ], f"负债率{dr:.0f}%{'，经营CF为正属好杠杆' if leverage=='好杠杆' else ''}；商誉{'低' if gw<5 else '偏高需关注'}；{data.get('asset_type','')}")

    # 利润增长
    draw_block(0.05, 0.05, 0.43, 0.42, "利润增长", s_gr, [
        ("近3年平均营收增速", f"{data.get('rev_yoy_avg',0):+.1f}%", "#c62828" if data.get('rev_yoy_avg',0)>15 else "#333"),
        ("最新年度营收同比", f"{data.get('latest_rev_yoy',0):+.1f}%", "#2e7d32" if data.get('latest_rev_yoy',0)>0 else "#c62828"),
        ("最新扣非同比", f"{data.get('latest_ded_yoy',0):+.1f}%", "#2e7d32" if data.get('latest_ded_yoy',0)>0 else "#c62828"),
        ("扣非/归母占比", f"{data.get('dedu_vs_np',0):.0f}%", "#2e7d32" if data.get('dedu_vs_np',0)>80 else "#f57f17"),
    ], f"{'高增长' if data.get('rev_yoy_avg',0)>30 else '稳健增长' if data.get('rev_yoy_avg',0)>10 else '低增长'}；利润质量{'好' if data.get('dedu_vs_np',0)>80 else '一般'}")

    # 估值
    pe = data.get("pe_ttm", 0)
    peg = data.get("peg", 0)
    pct = data.get("pe_pct", 50)
    draw_block(0.52, 0.05, 0.43, 0.42, "估值水平", s_va, [
        ("PE(TTM)", f"{pe:.1f}x" if pe else "-", "#333"),
        ("PB", f"{data.get('pb',0):.1f}x" if data.get('pb') else "-", "#333"),
        ("PEG", f"{peg:.2f}" if peg else "-", "#2e7d32" if peg and peg<1 else "#c62828" if peg and peg>2 else "#333"),
        ("PE历史分位", f"{pct}%" if pct else "-", "#2e7d32" if pct and pct<30 else "#c62828" if pct and pct>70 else "#333"),
    ], f"PE {pe:.0f}x {'偏低' if pct and pct<30 else '中位' if pct and pct<70 else '偏高'}；PEG {'<1低估' if peg and peg<1 else '合理' if peg and peg<1.5 else '偏高' if peg else '-'}")

    fig.text(0.98, 0.002, "数据来源:Tushare | 仅供参考",
             fontproperties=CN_FONT, fontsize=7, ha='right', color='#bbb')

    out = f"checkup_{data['ts_code'].replace('.','_')}.png"
    plt.savefig(out, dpi=150, bbox_inches='tight', facecolor='white', pad_inches=0.2)
    plt.close()
    print(f"已生成: {out}")
    return out

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python checkup.py 603197"); sys.exit(1)
    tc = sys.argv[1].strip().upper()
    if not tc.endswith(('.SH','.SZ','.BJ')):
        c = tc.replace('.','')
        tc = c + ('.SH' if c[0] in '69' else '.SZ' if c[0] in '032' else '.BJ' if c[0] in '48' else '.SH')
    print(f"正在采集 {tc} ...")
    data = collect_data(tc)
    if data:
        print("生成体检报告...")
        draw_report(data)
    else:
        print(f"未找到 {tc} 的数据")
