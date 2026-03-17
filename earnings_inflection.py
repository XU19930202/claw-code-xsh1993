#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
业绩拐点筛选器 —— 一季报扣非净利润拐点筛选
模式A（亏转盈）: 上年Q1亏损 → 本年Q1大幅转正
模式B（加速增长）: 前年Q1刚转正/基数低 → 上年Q1同比暴增200%+
适配 Tushare Pro API，一季报披露期（4月）每日运行可持续刷新
支持飞书推送
"""

import tushare as ts
import pandas as pd
import numpy as np
import datetime
import time
import argparse
import os
import sys
import requests
import yaml
import logging
from pathlib import Path

# ========== 配置区 ==========
SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "config.yaml"

def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {"feishu_webhook": "", "llm": {}}

CONFIG = load_config()
FEISHU_WEBHOOK = CONFIG.get("feishu_webhook", "")

TUSHARE_TOKEN = "a009b833ddc8257726296c9d51574cb6c18315e937eeeeb79ce4e61e"
ts.set_token(TUSHARE_TOKEN)
pro = ts.pro_api()

# ---------- 通用参数 ----------
EXCLUDE_ST = True
EXCLUDE_NEW_DAYS = 180      # 排除上市不满半年的
MIN_MV = 30                 # 最低市值（亿）
MAX_MV = 3000               # 最高市值（亿）

# ---------- 模式A参数（亏转盈）----------
A_LOSS_YEAR = '2025'        # 亏损的那个Q1年份
A_PROFIT_YEAR = '2026'      # 转正的那个Q1年份
A_MIN_PROFIT = 500          # 转正后扣非净利润最低值（万元）
A_MIN_IMPROVE = 1000        # 扣非改善额最低值（万元）

# ---------- 模式B参数（加速增长）----------
B_BASE_YEAR = '2024'        # 基数年Q1
B_GROWTH_YEAR = '2025'      # 增长年Q1
B_BASE_MAX_PROFIT = 5000    # 基数年Q1扣非上限（万元）
B_MIN_GROWTH_PCT = 200      # 增长年Q1扣非同比增速下限（%）
B_MIN_PROFIT = 1000         # 增长年Q1扣非净利润最低值（万元）

# 日志配置
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def get_stock_pool():
    """获取A股股票池"""
    df = pro.stock_basic(exchange='', list_status='L',
                         fields='ts_code,symbol,name,area,industry,market,list_date')
    if EXCLUDE_ST:
        df = df[~df['name'].str.contains('ST', na=False)]
    if EXCLUDE_NEW_DAYS > 0:
        cutoff = (datetime.date.today() - datetime.timedelta(days=EXCLUDE_NEW_DAYS)).strftime('%Y%m%d')
        df = df[df['list_date'] <= cutoff]
    df = df[df['ts_code'].str.endswith(('.SH', '.SZ'))]
    return df


def fetch_q1_fina(period, stock_codes):
    """
    获取某Q1季度的财务指标数据
    period: 如 '20260331'
    stock_codes: 股票代码列表
    """
    logger.info(f"拉取 {period} 财务指标...")
    all_data = []
    
    # 分批获取（每批50个）
    batch_size = 50
    for i in range(0, len(stock_codes), batch_size):
        batch = stock_codes[i:i+batch_size]
        try:
            df = pro.fina_indicator(ts_code=','.join(batch), period=period,
                                    fields='ts_code,ann_date,end_date,'
                                           'profit_dedt,'           # 扣非净利润
                                           'dt_netprofit_yoy,'      # 扣非净利润同比增长率
                                           'netprofit_yoy,'         # 归母净利润同比
                                           'revenue,'               # 营业收入
                                           'op_yoy,'                # 营收同比
                                           'roe_dt,'                # 扣非ROE
                                           'grossprofit_margin')    # 毛利率
            if df is not None and len(df) > 0:
                all_data.append(df)
            time.sleep(0.3)
        except Exception as e:
            logger.warning(f"批次 {i//batch_size + 1} 获取失败: {e}")
            time.sleep(0.5)
        
        if i % 500 == 0 and i > 0:
            logger.info(f"已处理 {i}/{len(stock_codes)} 只股票...")
    
    if all_data:
        result = pd.concat(all_data, ignore_index=True)
        result = result.sort_values('ann_date', ascending=False).drop_duplicates('ts_code', keep='first')
        logger.info(f"获取 {len(result)} 家公司数据")
        return result
    else:
        logger.warning(f"{period} 暂无数据（可能还未到披露期）")
        return pd.DataFrame()


def fetch_income_q1(period, stock_codes):
    """备选：用利润表获取Q1数据"""
    logger.info(f"拉取 {period} 利润表...")
    all_data = []
    
    batch_size = 50
    for i in range(0, len(stock_codes), batch_size):
        batch = stock_codes[i:i+batch_size]
        try:
            df = pro.income(ts_code=','.join(batch), period=period, report_type='1',
                            fields='ts_code,ann_date,end_date,'
                                   'revenue,operate_profit,total_profit,n_income,'
                                   'n_income_attr_p,dt_profit')
            if df is not None and len(df) > 0:
                all_data.append(df)
            time.sleep(0.3)
        except Exception as e:
            logger.warning(f"批次 {i//batch_size + 1} 获取失败: {e}")
            time.sleep(0.5)
    
    if all_data:
        result = pd.concat(all_data, ignore_index=True)
        result = result.sort_values('ann_date', ascending=False).drop_duplicates('ts_code', keep='first')
        logger.info(f"获取 {len(result)} 家")
        return result
    else:
        return pd.DataFrame()


def fetch_daily_basic_latest():
    """获取最新交易日的市值数据"""
    today = datetime.date.today().strftime('%Y%m%d')
    cal = pro.trade_cal(exchange='SSE', start_date='20260101', end_date=today,
                        fields='cal_date,is_open')
    cal = cal[cal['is_open'] == 1].sort_values('cal_date', ascending=False)
    if cal.empty:
        return pd.DataFrame()
    latest = cal.iloc[0]['cal_date']
    logger.info(f"获取 {latest} 市值数据...")
    try:
        df = pro.daily_basic(trade_date=latest,
                             fields='ts_code,close,total_mv,circ_mv,pe_ttm,pb')
        if df is not None:
            df['total_mv_yi'] = (df['total_mv'] / 10000).round(1)
        return df
    except:
        return pd.DataFrame()


def screen_mode_a(stock_pool):
    """
    模式A：亏转盈
    筛选条件：
    1. A_LOSS_YEAR Q1 扣非净利润 < 0（亏损）
    2. A_PROFIT_YEAR Q1 扣非净利润 > A_MIN_PROFIT（转正且有一定规模）
    3. 改善额 > A_MIN_IMPROVE
    """
    logger.info(f"模式A：亏转盈筛选 - {A_LOSS_YEAR}Q1亏损 → {A_PROFIT_YEAR}Q1扣非转正")
    logger.info(f"转正门槛: >{A_MIN_PROFIT}万 | 改善额: >{A_MIN_IMPROVE}万")
    
    period_loss = f"{A_LOSS_YEAR}0331"
    period_profit = f"{A_PROFIT_YEAR}0331"
    
    stock_codes = stock_pool['ts_code'].tolist()
    
    df_loss = fetch_q1_fina(period_loss, stock_codes)
    df_profit = fetch_q1_fina(period_profit, stock_codes)
    
    if df_loss.empty:
        logger.warning(f"{period_loss} 数据为空，尝试用利润表...")
        df_loss_inc = fetch_income_q1(period_loss, stock_codes)
        if not df_loss_inc.empty:
            df_loss = df_loss_inc.rename(columns={'dt_profit': 'profit_dedt'})
    
    if df_profit.empty:
        logger.warning(f"{period_profit} 数据为空（可能尚未披露）")
        logger.info("提示：一季报披露期为4月1日-4月30日，请在此期间运行")
        return pd.DataFrame()
    
    if df_loss.empty:
        logger.warning(f"{period_loss} 数据为空")
        return pd.DataFrame()
    
    valid_codes = set(stock_codes)
    
    df_loss = df_loss[df_loss['ts_code'].isin(valid_codes)][['ts_code', 'profit_dedt']].copy()
    df_loss.columns = ['ts_code', 'profit_dedt_prev']
    
    df_profit = df_profit[df_profit['ts_code'].isin(valid_codes)][['ts_code', 'profit_dedt']].copy()
    
    merged = df_profit.merge(df_loss, on='ts_code', how='inner')
    
    # 核心筛选
    merged = merged[merged['profit_dedt_prev'] < 0]
    merged = merged[merged['profit_dedt'] > A_MIN_PROFIT]
    merged['improve'] = merged['profit_dedt'] - merged['profit_dedt_prev']
    merged = merged[merged['improve'] > A_MIN_IMPROVE]
    merged['improve_pct'] = (merged['improve'] / merged['profit_dedt_prev'].abs() * 100).round(1)
    merged = merged.sort_values('improve', ascending=False).reset_index(drop=True)
    merged = merged.merge(stock_pool[['ts_code', 'name', 'industry']], on='ts_code', how='left')
    
    logger.info(f"模式A筛出 {len(merged)} 只亏转盈标的")
    return merged


def screen_mode_b(stock_pool):
    """
    模式B：加速增长（新易盛模式）
    筛选条件：
    1. B_BASE_YEAR Q1 扣非净利润 > 0 但 < B_BASE_MAX_PROFIT
    2. B_GROWTH_YEAR Q1 扣非净利润 > B_MIN_PROFIT 且同比增速 > B_MIN_GROWTH_PCT
    """
    logger.info(f"模式B：加速增长筛选 - {B_BASE_YEAR}Q1小基数 → {B_GROWTH_YEAR}Q1爆发")
    logger.info(f"基数上限: {B_BASE_MAX_PROFIT}万 | 增速下限: >{B_MIN_GROWTH_PCT}%")
    
    period_base = f"{B_BASE_YEAR}0331"
    period_growth = f"{B_GROWTH_YEAR}0331"
    
    stock_codes = stock_pool['ts_code'].tolist()
    
    df_base = fetch_q1_fina(period_base, stock_codes)
    df_growth = fetch_q1_fina(period_growth, stock_codes)
    
    if df_base.empty:
        df_base_inc = fetch_income_q1(period_base, stock_codes)
        if not df_base_inc.empty:
            df_base = df_base_inc.rename(columns={'dt_profit': 'profit_dedt'})
    
    if df_growth.empty:
        logger.warning(f"{period_growth} 数据为空（可能尚未披露）")
        return pd.DataFrame()
    
    if df_base.empty:
        logger.warning(f"{period_base} 数据为空")
        return pd.DataFrame()
    
    valid_codes = set(stock_codes)
    
    df_base = df_base[df_base['ts_code'].isin(valid_codes)][['ts_code', 'profit_dedt']].copy()
    df_base.columns = ['ts_code', 'profit_dedt_base']
    
    df_growth = df_growth[df_growth['ts_code'].isin(valid_codes)][['ts_code', 'profit_dedt']].copy()
    
    merged = df_growth.merge(df_base, on='ts_code', how='inner')
    
    # 核心筛选
    merged = merged[(merged['profit_dedt_base'] > 0) & (merged['profit_dedt_base'] <= B_BASE_MAX_PROFIT)]
    merged = merged[merged['profit_dedt'] > B_MIN_PROFIT]
    merged['yoy_pct'] = ((merged['profit_dedt'] - merged['profit_dedt_base']) / merged['profit_dedt_base'] * 100).round(1)
    merged = merged[merged['yoy_pct'] >= B_MIN_GROWTH_PCT]
    merged['growth_x'] = (merged['profit_dedt'] / merged['profit_dedt_base']).round(1)
    merged = merged.sort_values('yoy_pct', ascending=False).reset_index(drop=True)
    merged = merged.merge(stock_pool[['ts_code', 'name', 'industry']], on='ts_code', how='left')
    
    logger.info(f"模式B筛出 {len(merged)} 只加速增长标的")
    return merged


def add_market_data(df):
    """合并市值、PE等市场数据"""
    if df.empty:
        return df
    
    df_basic = fetch_daily_basic_latest()
    if df_basic is not None and not df_basic.empty:
        df = df.merge(
            df_basic[['ts_code', 'close', 'total_mv_yi', 'pe_ttm', 'pb']],
            on='ts_code', how='left'
        )
        df = df[(df['total_mv_yi'] >= MIN_MV) & (df['total_mv_yi'] <= MAX_MV)]
    
    return df


def send_to_feishu(title, content):
    """发送消息到飞书群"""
    if not FEISHU_WEBHOOK:
        logger.warning("飞书Webhook未配置，跳过推送")
        return False
    
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title
                },
                "template": "green"
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": content
                }
            ]
        }
    }
    
    try:
        response = requests.post(FEISHU_WEBHOOK, json=payload, timeout=30)
        result = response.json()
        if result.get("StatusCode") == 0:
            logger.info("飞书推送成功")
            return True
        else:
            logger.error(f"飞书推送失败: {result}")
            return False
    except Exception as e:
        logger.error(f"飞书推送异常: {e}")
        return False


def generate_feishu_content(df_a, df_b):
    """生成飞书推送内容"""
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    lines = [f"📅 **{today_str}**\n"]
    
    # 模式A
    if df_a is not None and not df_a.empty:
        lines.append(f"**💰 亏转盈（{A_LOSS_YEAR}Q1亏→{A_PROFIT_YEAR}Q1盈）: {len(df_a)}只**")
        for _, row in df_a.head(15).iterrows():
            imp_str = f"{row['improve']/10000:.1f}亿" if row['improve'] >= 10000 else f"{row['improve']:.0f}万"
            curr_str = f"{row['profit_dedt']/10000:.1f}亿" if row['profit_dedt'] >= 10000 else f"{row['profit_dedt']:.0f}万"
            mv_str = f"{row['total_mv_yi']:.0f}亿" if pd.notna(row.get('total_mv_yi')) else ''
            lines.append(
                f"  • {row.get('name','')} ({row['ts_code'][:6]}) "
                f"扣非{curr_str} | 改善{imp_str} | {mv_str}"
            )
    else:
        lines.append(f"**💰 亏转盈: 暂无数据**")
    
    lines.append("")
    
    # 模式B
    if df_b is not None and not df_b.empty:
        lines.append(f"**🚀 加速增长（{B_BASE_YEAR}Q1小基数→{B_GROWTH_YEAR}Q1爆发）: {len(df_b)}只**")
        for _, row in df_b.head(15).iterrows():
            grow_str = f"{row['profit_dedt']/10000:.1f}亿" if row['profit_dedt'] >= 10000 else f"{row['profit_dedt']:.0f}万"
            mv_str = f"{row['total_mv_yi']:.0f}亿" if pd.notna(row.get('total_mv_yi')) else ''
            lines.append(
                f"  • {row.get('name','')} ({row['ts_code'][:6]}) "
                f"扣非{grow_str} | +{row['yoy_pct']:.0f}%({row['growth_x']:.1f}x) | {mv_str}"
            )
    else:
        lines.append(f"**🚀 加速增长: 暂无数据**")
    
    lines.append("")
    lines.append("---")
    lines.append("💡 说明:")
    lines.append(f"• 模式A: {A_LOSS_YEAR}Q1亏损→{A_PROFIT_YEAR}Q1转正")
    lines.append(f"• 模式B: {B_BASE_YEAR}Q1小基数→{B_GROWTH_YEAR}Q1爆发(增速>{B_MIN_GROWTH_PCT}%)")
    lines.append("• 数据来源: Tushare 一季报财务指标")
    
    return '\n'.join(lines)


def print_results_a(df):
    """打印模式A结果"""
    if df.empty:
        print("\n模式A：无符合条件的亏转盈标的")
        return
    
    print(f"\n{'='*100}")
    print(f"  模式A：亏转盈 —— {A_LOSS_YEAR}Q1亏损→{A_PROFIT_YEAR}Q1转正 | 共 {len(df)} 只")
    print(f"{'='*100}")
    print(f"\n{'序号':>4} | {'代码':<10} | {'名称':<10} | {'行业':<8} | "
          f"{'去年Q1扣非':>12} | {'今年Q1扣非':>12} | {'改善额':>10} | {'改善%':>7} | "
          f"{'市值(亿)':>8} | {'PE':>7}")
    print('-' * 120)
    
    for i, row in df.iterrows():
        pe_str = f"{row['pe_ttm']:.1f}" if pd.notna(row.get('pe_ttm')) else 'N/A'
        mv_str = f"{row['total_mv_yi']:.0f}" if pd.notna(row.get('total_mv_yi')) else 'N/A'
        prev_str = f"{row['profit_dedt_prev']/10000:.2f}亿" if abs(row['profit_dedt_prev']) >= 10000 else f"{row['profit_dedt_prev']:.0f}万"
        curr_str = f"{row['profit_dedt']/10000:.2f}亿" if row['profit_dedt'] >= 10000 else f"{row['profit_dedt']:.0f}万"
        imp_str = f"{row['improve']/10000:.2f}亿" if row['improve'] >= 10000 else f"{row['improve']:.0f}万"
        
        print(f"{i+1:>4} | {row['ts_code']:<10} | {row.get('name',''):<10} | {row.get('industry',''):<8} | "
              f"{prev_str:>12} | {curr_str:>12} | {imp_str:>10} | {row['improve_pct']:>6.0f}% | "
              f"{mv_str:>8} | {pe_str:>7}")


def print_results_b(df):
    """打印模式B结果"""
    if df.empty:
        print("\n模式B：无符合条件的加速增长标的")
        return
    
    print(f"\n{'='*100}")
    print(f"  模式B：加速增长 —— {B_BASE_YEAR}Q1小基数→{B_GROWTH_YEAR}Q1爆发 | 共 {len(df)} 只")
    print(f"{'='*100}")
    print(f"\n{'序号':>4} | {'代码':<10} | {'名称':<10} | {'行业':<8} | "
          f"{'基数Q1扣非':>12} | {'增长Q1扣非':>12} | {'同比增速':>8} | {'增长倍数':>8} | "
          f"{'市值(亿)':>8} | {'PE':>7}")
    print('-' * 120)
    
    for i, row in df.iterrows():
        pe_str = f"{row['pe_ttm']:.1f}" if pd.notna(row.get('pe_ttm')) else 'N/A'
        mv_str = f"{row['total_mv_yi']:.0f}" if pd.notna(row.get('total_mv_yi')) else 'N/A'
        base_str = f"{row['profit_dedt_base']/10000:.2f}亿" if row['profit_dedt_base'] >= 10000 else f"{row['profit_dedt_base']:.0f}万"
        grow_str = f"{row['profit_dedt']/10000:.2f}亿" if row['profit_dedt'] >= 10000 else f"{row['profit_dedt']:.0f}万"
        
        print(f"{i+1:>4} | {row['ts_code']:<10} | {row.get('name',''):<10} | {row.get('industry',''):<8} | "
              f"{base_str:>12} | {grow_str:>12} | {row['yoy_pct']:>7.0f}% | {row['growth_x']:>7.1f}x | "
              f"{mv_str:>8} | {pe_str:>7}")


def save_results(df, filename, output_dir='./output'):
    """保存CSV"""
    os.makedirs(output_dir, exist_ok=True)
    today_str = datetime.date.today().strftime('%Y%m%d')
    filepath = os.path.join(output_dir, f'{filename}_{today_str}.csv')
    df.to_csv(filepath, index=False, encoding='utf-8-sig')
    logger.info(f"已保存: {filepath}")


# ========== 主程序 ==========
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='业绩拐点筛选器')
    parser.add_argument('--mode', type=str, default='AB',
                        help='筛选模式: A=亏转盈, B=加速增长, AB=两种都跑')
    parser.add_argument('--min-mv', type=float, default=MIN_MV, help='最低市值(亿)')
    parser.add_argument('--max-mv', type=float, default=MAX_MV, help='最高市值(亿)')
    parser.add_argument('--save', action='store_true', help='保存CSV')
    parser.add_argument('--feishu', action='store_true', help='推送到飞书')
    
    parser.add_argument('--a-loss-year', type=str, default=A_LOSS_YEAR, help='亏损年份')
    parser.add_argument('--a-profit-year', type=str, default=A_PROFIT_YEAR, help='转正年份')
    parser.add_argument('--a-min-profit', type=float, default=A_MIN_PROFIT, help='转正扣非下限(万)')
    
    parser.add_argument('--b-base-year', type=str, default=B_BASE_YEAR, help='基数年份')
    parser.add_argument('--b-growth-year', type=str, default=B_GROWTH_YEAR, help='增长年份')
    parser.add_argument('--b-min-growth', type=float, default=B_MIN_GROWTH_PCT, help='最低增速(%)')
    parser.add_argument('--b-base-max', type=float, default=B_BASE_MAX_PROFIT, help='基数扣非上限(万)')
    
    args = parser.parse_args()
    
    MIN_MV = args.min_mv
    MAX_MV = args.max_mv
    A_LOSS_YEAR = args.a_loss_year
    A_PROFIT_YEAR = args.a_profit_year
    A_MIN_PROFIT = args.a_min_profit
    B_BASE_YEAR = args.b_base_year
    B_GROWTH_YEAR = args.b_growth_year
    B_MIN_GROWTH_PCT = args.b_min_growth
    B_BASE_MAX_PROFIT = args.b_base_max
    
    mode = args.mode.upper()
    
    # Windows控制台编码设置
    if sys.platform == "win32":
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")
    
    logger.info("业绩拐点筛选器启动")
    logger.info(f"模式: {mode} | 市值 {MIN_MV}~{MAX_MV}亿")
    
    # 获取股票池
    stock_pool = get_stock_pool()
    logger.info(f"股票池: {len(stock_pool)} 只")
    
    df_a = None
    df_b = None
    
    if 'A' in mode:
        df_a = screen_mode_a(stock_pool)
        if not df_a.empty:
            df_a = add_market_data(df_a)
            print_results_a(df_a)
            if args.save:
                save_results(df_a, 'earnings_loss_to_profit')
    
    if 'B' in mode:
        df_b = screen_mode_b(stock_pool)
        if not df_b.empty:
            df_b = add_market_data(df_b)
            print_results_b(df_b)
            if args.save:
                save_results(df_b, 'earnings_acceleration')
    
    # 飞书推送
    if args.feishu or (df_a is not None and not df_a.empty) or (df_b is not None and not df_b.empty):
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        title = f"📊 业绩拐点筛选 ({today_str})"
        content = generate_feishu_content(df_a, df_b)
        send_to_feishu(title, content)
    
    # AB模式交集
    if df_a is not None and df_b is not None and not df_a.empty and not df_b.empty:
        overlap = set(df_a['ts_code']) & set(df_b['ts_code'])
        if overlap:
            print(f"\n⚡ AB模式交集（{len(overlap)}只）:")
            for code in overlap:
                name = stock_pool[stock_pool['ts_code'] == code]['name'].values
                print(f"   {code} {name[0] if len(name) > 0 else ''}")
    
    print("\n筛选完成")
