#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MA20突破 + MACD金叉共振筛选器
筛选刚站上20日均线的A股标的，并标注MACD共振信号等级
信号等级：★★★ 零轴上方金叉共振 > ★★☆ 零轴下方金叉共振 > ★☆☆ DIF>DEA > ☆☆☆ 无配合
适配 Tushare Pro API，可部署到服务器通过 cron 每日收盘后运行
支持飞书推送
"""

import tushare as ts
import pandas as pd
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

# 筛选参数
MA_PERIOD = 20          # 均线周期
LOOKBACK_DAYS = 60      # 拉取行情天数（EMA26需要更多预热数据）
VOL_RATIO_MIN = 1.3     # 突破日成交量相对20日均量的最低倍数（设0则不过滤）
MIN_MV = 30             # 最低总市值（亿），过滤小微盘
MAX_MV = 3000           # 最高总市值（亿），过滤超大盘（可按需调）
EXCLUDE_ST = True       # 排除ST
EXCLUDE_NEW_DAYS = 60   # 排除上市不满N天的次新股
MIN_PRICE = 3.0         # 最低股价
MAX_PRICE = 100.0       # 最高股价（可选）

# MACD参数
MACD_FAST = 12          # 快线EMA周期
MACD_SLOW = 26          # 慢线EMA周期
MACD_SIGNAL = 9         # 信号线DEA的EMA周期
MACD_CROSS_DAYS = 3     # 金叉发生在最近N个交易日内即算共振
REQUIRE_MACD = False    # True=强制要求MACD金叉共振，False=不要求但标记

# 日志配置
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def get_trade_dates(n=LOOKBACK_DAYS):
    """获取最近n个交易日"""
    today = datetime.date.today().strftime('%Y%m%d')
    df = pro.trade_cal(exchange='SSE', start_date='20250101', end_date=today,
                       fields='cal_date,is_open')
    df = df[df['is_open'] == 1].sort_values('cal_date', ascending=False)
    dates = df['cal_date'].head(n).tolist()
    return sorted(dates)


def get_stock_pool():
    """获取当前A股股票池（排除ST、停牌等）"""
    df = pro.stock_basic(exchange='', list_status='L',
                         fields='ts_code,symbol,name,area,industry,market,list_date')
    
    if EXCLUDE_ST:
        df = df[~df['name'].str.contains('ST', na=False)]
    
    # 排除次新股
    if EXCLUDE_NEW_DAYS > 0:
        cutoff = (datetime.date.today() - datetime.timedelta(days=EXCLUDE_NEW_DAYS)).strftime('%Y%m%d')
        df = df[df['list_date'] <= cutoff]
    
    # 只保留主板、创业板、科创板（排除北交所等）
    df = df[df['ts_code'].str.endswith(('.SH', '.SZ'))]
    
    return df


def fetch_daily_basic(trade_date):
    """获取某日全市场每日指标（市值等）"""
    try:
        df = pro.daily_basic(trade_date=trade_date,
                             fields='ts_code,close,turnover_rate,volume_ratio,total_mv,circ_mv,pe_ttm,pb')
        return df
    except Exception as e:
        logger.warning(f"daily_basic获取失败: {e}")
        return None


def batch_screen_ma20(stock_pool, trade_dates):
    """
    批量筛选：站上MA20的标的
    为节省积分，使用 pro.daily() 按日期拉全市场数据，而非逐只拉取
    """
    results = []
    
    start_date = trade_dates[0]
    end_date = trade_dates[-1]
    latest_date = trade_dates[-1]
    prev_date = trade_dates[-2] if len(trade_dates) >= 2 else None
    
    logger.info(f"筛选区间: {start_date} ~ {end_date}")
    logger.info(f"最新交易日: {latest_date}，前一交易日: {prev_date}")
    
    # 按日期批量拉取
    logger.info("正在拉取全市场日线数据（按日期批量）...")
    
    all_daily = []
    for i, d in enumerate(trade_dates):
        try:
            df = pro.daily(trade_date=d,
                           fields='ts_code,trade_date,open,high,low,close,vol,amount')
            if df is not None:
                all_daily.append(df)
            if i % 5 == 0:
                logger.info(f"已拉取 {i+1}/{len(trade_dates)} 个交易日...")
            time.sleep(0.15)  # 控制频率
        except Exception as e:
            logger.warning(f"{d} 拉取失败: {e}")
            time.sleep(1)
    
    if not all_daily:
        logger.error("未获取到任何行情数据")
        return pd.DataFrame()
    
    daily_all = pd.concat(all_daily, ignore_index=True)
    daily_all = daily_all.sort_values(['ts_code', 'trade_date']).reset_index(drop=True)
    
    logger.info(f"共获取 {len(daily_all)} 条记录，覆盖 {daily_all['ts_code'].nunique()} 只股票")
    
    # 计算MA20 & MACD & 筛选
    logger.info("正在计算MA20 + MACD并筛选突破标的...")
    
    valid_codes = set(stock_pool['ts_code'].tolist())
    
    for ts_code, grp in daily_all.groupby('ts_code'):
        if ts_code not in valid_codes:
            continue
        
        grp = grp.sort_values('trade_date').reset_index(drop=True)
        
        if len(grp) < MA_PERIOD + 1:
            continue
        
        # 计算MA20
        grp['ma20'] = grp['close'].rolling(window=MA_PERIOD).mean()
        # 计算20日均量
        grp['vol_ma20'] = grp['vol'].rolling(window=MA_PERIOD).mean()
        
        # 计算MACD
        grp['ema_fast'] = grp['close'].ewm(span=MACD_FAST, adjust=False).mean()
        grp['ema_slow'] = grp['close'].ewm(span=MACD_SLOW, adjust=False).mean()
        grp['dif'] = grp['ema_fast'] - grp['ema_slow']
        grp['dea'] = grp['dif'].ewm(span=MACD_SIGNAL, adjust=False).mean()
        grp['macd_bar'] = (grp['dif'] - grp['dea']) * 2
        
        # 取最后两行（今日 & 昨日）
        if len(grp) < 2:
            continue
        
        today_row = grp.iloc[-1]
        yest_row = grp.iloc[-2]
        
        # 核心条件：今日收盘 > MA20，且昨日收盘 <= MA20（刚突破）
        if pd.isna(today_row['ma20']) or pd.isna(yest_row['ma20']):
            continue
        
        cross_up = (today_row['close'] > today_row['ma20']) and (yest_row['close'] <= yest_row['ma20'])
        
        if not cross_up:
            continue
        
        # 量比确认
        vol_ratio = today_row['vol'] / today_row['vol_ma20'] if today_row['vol_ma20'] > 0 else 0
        if VOL_RATIO_MIN > 0 and vol_ratio < VOL_RATIO_MIN:
            continue
        
        # 价格过滤
        if today_row['close'] < MIN_PRICE or today_row['close'] > MAX_PRICE:
            continue
        
        # --- MACD金叉共振判断 ---
        # 检查最近N日内是否出现MACD金叉（DIF上穿DEA）
        macd_golden = False
        macd_above_zero = False
        macd_cross_day = 'N/A'
        
        tail = grp.tail(MACD_CROSS_DAYS + 1)  # 多取1行用于比较前一日
        for j in range(1, len(tail)):
            row_t = tail.iloc[j]
            row_y = tail.iloc[j - 1]
            if pd.notna(row_t['dif']) and pd.notna(row_t['dea']):
                if row_t['dif'] > row_t['dea'] and row_y['dif'] <= row_y['dea']:
                    macd_golden = True
                    macd_cross_day = row_t['trade_date']
                    break
        
        # 判断DIF/DEA是否在零轴上方
        if pd.notna(today_row['dif']) and pd.notna(today_row['dea']):
            macd_above_zero = (today_row['dif'] > 0) and (today_row['dea'] > 0)
        
        # 如果强制要求MACD共振，过滤掉无金叉的
        if REQUIRE_MACD and not macd_golden:
            continue
        
        # 信号等级评定
        if macd_golden and macd_above_zero:
            signal_level = '★★★'   # 零轴上方金叉 + MA20突破，最强
        elif macd_golden and not macd_above_zero:
            signal_level = '★★☆'   # 零轴下方金叉 + MA20突破，中等
        elif not macd_golden and today_row['dif'] > today_row['dea']:
            signal_level = '★☆☆'   # 无金叉但DIF>DEA（已在多头），较弱
        else:
            signal_level = '☆☆☆'   # 无MACD配合
        
        # MA20斜率（趋势方向）
        if len(grp) >= MA_PERIOD + 5:
            ma20_5d_ago = grp.iloc[-6]['ma20'] if not pd.isna(grp.iloc[-6]['ma20']) else today_row['ma20']
            ma20_slope = (today_row['ma20'] - ma20_5d_ago) / ma20_5d_ago * 100
        else:
            ma20_slope = 0
        
        # 突破力度：收盘价高于MA20的百分比
        break_pct = (today_row['close'] - today_row['ma20']) / today_row['ma20'] * 100
        
        results.append({
            'ts_code': ts_code,
            'trade_date': today_row['trade_date'],
            'close': round(today_row['close'], 2),
            'ma20': round(today_row['ma20'], 2),
            'break_pct': round(break_pct, 2),          # 突破幅度%
            'vol_ratio': round(vol_ratio, 2),            # 量比
            'ma20_slope': round(ma20_slope, 2),          # MA20斜率%（5日）
            'amount': round(today_row['amount'] / 100000, 1),  # 成交额（亿）
            'dif': round(today_row['dif'], 3),
            'dea': round(today_row['dea'], 3),
            'macd_bar': round(today_row['macd_bar'], 3),
            'macd_golden': macd_golden,                  # 近N日是否金叉
            'macd_above_zero': macd_above_zero,          # DIF&DEA是否在零轴上方
            'macd_cross_day': macd_cross_day,            # 金叉日期
            'signal_level': signal_level,                # 综合信号等级
        })
    
    if not results:
        logger.warning("未筛选到符合条件的标的")
        return pd.DataFrame()
    
    df_result = pd.DataFrame(results)
    
    # 合并基本信息
    df_result = df_result.merge(
        stock_pool[['ts_code', 'name', 'industry', 'area']],
        on='ts_code', how='left'
    )
    
    # 合并市值数据
    logger.info("正在获取市值数据...")
    df_basic = fetch_daily_basic(latest_date)
    if df_basic is not None and len(df_basic) > 0:
        df_basic['total_mv_yi'] = (df_basic['total_mv'] / 10000).round(1)  # 万元 -> 亿元
        df_result = df_result.merge(
            df_basic[['ts_code', 'total_mv_yi', 'pe_ttm', 'pb', 'turnover_rate']],
            on='ts_code', how='left'
        )
        
        # 市值过滤
        df_result = df_result[
            (df_result['total_mv_yi'] >= MIN_MV) & 
            (df_result['total_mv_yi'] <= MAX_MV)
        ]
    
    # 排序输出：信号等级优先，量比次之
    level_order = {'★★★': 0, '★★☆': 1, '★☆☆': 2, '☆☆☆': 3}
    df_result['_level_sort'] = df_result['signal_level'].map(level_order)
    df_result = df_result.sort_values(['_level_sort', 'vol_ratio'], ascending=[True, False]).reset_index(drop=True)
    df_result = df_result.drop(columns=['_level_sort'])
    
    return df_result


def send_to_feishu(title, content):
    """发送消息到飞书群"""
    if not FEISHU_WEBHOOK:
        logger.warning("飞书Webhook未配置，跳过推送")
        return False
    
    # 构建飞书卡片消息
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title
                },
                "template": "blue"
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
            logger.info(f"飞书推送成功")
            return True
        else:
            logger.error(f"飞书推送失败: {result}")
            return False
    except Exception as e:
        logger.error(f"飞书推送异常: {e}")
        return False


def generate_feishu_content(df):
    """生成飞书推送内容"""
    if df.empty:
        return "今日无符合MA20突破条件的标的"
    
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    n_golden = len(df[df['macd_golden'] == True])
    
    lines = [
        f"📅 **{today_str}**",
        f"筛选出 **{len(df)}** 只突破MA20标的，其中 **{n_golden}** 只MACD金叉共振",
        ""
    ]
    
    # ★★★ 零轴上方金叉共振（最强信号）
    df_3star = df[df['signal_level'] == '★★★'].head(10)
    if not df_3star.empty:
        lines.append("**⭐⭐⭐ 零轴上方金叉共振（最强）:**")
        for _, row in df_3star.iterrows():
            lines.append(
                f"  • {row.get('name','')} ({row['ts_code'][:6]}) "
                f"¥{row['close']} | 突破{row['break_pct']:.1f}% | "
                f"量比{row['vol_ratio']:.1f}x | DIF {row['dif']:.3f}"
            )
        lines.append("")
    
    # ★★☆ 零轴下方金叉共振
    df_2star = df[df['signal_level'] == '★★☆'].head(10)
    if not df_2star.empty:
        lines.append("**⭐⭐ 零轴下方金叉共振:**")
        for _, row in df_2star.iterrows():
            lines.append(
                f"  • {row.get('name','')} ({row['ts_code'][:6]}) "
                f"¥{row['close']} | 突破{row['break_pct']:.1f}% | "
                f"量比{row['vol_ratio']:.1f}x | DIF {row['dif']:.3f}"
            )
        lines.append("")
    
    # 其余标的简要列出
    df_rest = df[~df['signal_level'].isin(['★★★', '★★☆'])].head(8)
    if not df_rest.empty:
        lines.append(f"**仅MA20突破（无MACD共振）:**")
        for _, row in df_rest.iterrows():
            lines.append(
                f"  • {row.get('name','')} ({row['ts_code'][:6]}) "
                f"¥{row['close']} | 量比{row['vol_ratio']:.1f}x"
            )
    
    lines.append("")
    lines.append("---")
    lines.append("💡 信号等级说明:")
    lines.append("• ★★★ 零轴上方金叉 + MA20突破")
    lines.append("• ★★☆ 零轴下方金叉 + MA20突破")
    lines.append("• ★☆☆ DIF>DEA 无金叉")
    lines.append("• ☆☆☆ 无MACD配合")
    
    return '\n'.join(lines)


def print_results(df):
    """格式化打印结果"""
    if df.empty:
        print("\n今日无符合条件的MA20突破标的")
        return
    
    print(f"\n{'='*100}")
    print(f"  MA20突破 + MACD共振筛选结果 —— 共 {len(df)} 只")
    print(f"  信号等级: ★★★=零轴上金叉共振 | ★★☆=零轴下金叉共振 | ★☆☆=DIF>DEA无金叉 | ☆☆☆=无MACD配合")
    print(f"{'='*100}")
    
    print(f"\n{'序号':>4} | {'信号':>3} | {'代码':<10} | {'名称':<8} | {'行业':<8} | {'收盘':>7} | {'MA20':>7} | {'突破%':>6} | {'量比':>5} | {'DIF':>7} | {'DEA':>7} | {'市值(亿)':>8}")
    print('-' * 120)
    
    for i, row in df.iterrows():
        mv_str = f"{row.get('total_mv_yi', 0):.0f}" if pd.notna(row.get('total_mv_yi')) else 'N/A'
        
        print(f"{i+1:>4} | {row['signal_level']} | {row['ts_code']:<10} | {row.get('name',''):<8} | {row.get('industry',''):<8} | "
              f"{row['close']:>7.2f} | {row['ma20']:>7.2f} | {row['break_pct']:>5.1f}% | "
              f"{row['vol_ratio']:>5.2f} | {row['dif']:>7.3f} | {row['dea']:>7.3f} | "
              f"{mv_str:>8}")
    
    # 统计摘要
    n_3star = len(df[df['signal_level'] == '★★★'])
    n_2star = len(df[df['signal_level'] == '★★☆'])
    n_golden = len(df[df['macd_golden'] == True])
    
    print(f"\n信号分布: ★★★ {n_3star}只 | ★★☆ {n_2star}只 | MACD金叉共振 {n_golden}只")
    print(f"MA20斜率向上: {len(df[df['ma20_slope'] > 0])} 只")
    print(f"量比 > 2.0: {len(df[df['vol_ratio'] > 2.0])} 只")
    
    if 'industry' in df.columns:
        top_industries = df['industry'].value_counts().head(5)
        print(f"\n行业分布 Top5:")
        for ind, cnt in top_industries.items():
            print(f"   {ind}: {cnt} 只")


def save_results(df, output_dir='./output'):
    """保存结果到CSV"""
    os.makedirs(output_dir, exist_ok=True)
    today_str = datetime.date.today().strftime('%Y%m%d')
    filepath = os.path.join(output_dir, f'ma20_cross_{today_str}.csv')
    df.to_csv(filepath, index=False, encoding='utf-8-sig')
    logger.info(f"结果已保存: {filepath}")
    return filepath


# ========== 主程序 ==========
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='MA20突破筛选器')
    parser.add_argument('--vol-ratio', type=float, default=VOL_RATIO_MIN, help='最低量比')
    parser.add_argument('--min-mv', type=float, default=MIN_MV, help='最低市值(亿)')
    parser.add_argument('--max-mv', type=float, default=MAX_MV, help='最高市值(亿)')
    parser.add_argument('--save', action='store_true', help='保存CSV')
    parser.add_argument('--feishu', action='store_true', help='推送到飞书')
    parser.add_argument('--macd', action='store_true', help='强制要求MACD金叉共振')
    args = parser.parse_args()
    
    VOL_RATIO_MIN = args.vol_ratio
    MIN_MV = args.min_mv
    MAX_MV = args.max_mv
    REQUIRE_MACD = args.macd
    
    # Windows控制台编码设置
    if sys.platform == "win32":
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")
    
    logger.info("MA20突破 + MACD共振筛选器启动")
    macd_mode = "强制共振" if REQUIRE_MACD else "标记模式（全部输出，标注信号等级）"
    logger.info(f"参数: MA{MA_PERIOD} | 量比>{VOL_RATIO_MIN} | 市值 {MIN_MV}~{MAX_MV}亿 | 价格 {MIN_PRICE}~{MAX_PRICE}")
    logger.info(f"MACD: {macd_mode} | 金叉窗口 {MACD_CROSS_DAYS}日")
    
    # 1. 获取交易日历
    trade_dates = get_trade_dates(LOOKBACK_DAYS)
    
    # 2. 获取股票池
    stock_pool = get_stock_pool()
    logger.info(f"股票池: {len(stock_pool)} 只")
    
    # 3. 批量筛选
    df_result = batch_screen_ma20(stock_pool, trade_dates)
    
    # 4. 输出
    print_results(df_result)
    
    if args.save and not df_result.empty:
        save_results(df_result)
    
    # 5. 飞书推送
    if args.feishu or not df_result.empty:
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        title = f"📊 MA20突破筛选 ({today_str})"
        content = generate_feishu_content(df_result)
        send_to_feishu(title, content)
