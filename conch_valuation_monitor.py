#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海螺水泥估值修复监控脚本
监控三个维度：
  1. PB估值位置（从底部回升）
  2. 技术面信号（MA20/MA60突破）
  3. 基本面验证（季报利润拐点）

触发条件满足时发出特别提醒

使用方法：
  python conch_valuation_monitor.py
  
  推送到飞书：
  python conch_valuation_monitor.py --feishu --webhook "你的Webhook"

定时任务（每个交易日收盘后运行）：
  30 17 * * 1-5 cd /path/to/scripts && python conch_valuation_monitor.py --feishu
"""

import time
import requests
import tushare as ts
import numpy as np
import argparse
import sys
import io
import os
from datetime import datetime, timedelta
from config import TUSHARE_TOKEN

# 处理 Windows 中文编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ============ 配置区 ============
_TUSHARE_TOKEN = TUSHARE_TOKEN

CONCH_CODE = "600585.SH"
STOCK_NAME = "海螺水泥"

# PB阈值设定
PB_BOTTOM = 0.60       # 历史底部
PB_REPAIR_TARGET = 1.0  # 估值修复第一目标
PB_MID = 1.50          # 历史中枢

# ============ 初始化 ============
ts.set_token(_TUSHARE_TOKEN)
pro = ts.pro_api()


def get_daily_data(days=250):
    """获取日线行情数据"""
    try:
        today = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d")
        df = pro.daily(ts_code=CONCH_CODE, start_date=start, end_date=today)
        if df is not None and not df.empty:
            df = df.sort_values('trade_date', ascending=True).reset_index(drop=True)
            return df
    except Exception as e:
        print(f"获取日线数据失败: {e}")
    return None


def get_basic_data(days=250):
    """获取每日指标（PE/PB/股息率）"""
    try:
        today = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d")
        df = pro.daily_basic(ts_code=CONCH_CODE, start_date=start, end_date=today)
        if df is not None and not df.empty:
            df = df.sort_values('trade_date', ascending=True).reset_index(drop=True)
            return df
    except Exception as e:
        print(f"获取基本面指标失败: {e}")
    return None


def get_quarterly_profit():
    """获取近几个季度的扣非净利润数据"""
    try:
        df = pro.income(ts_code=CONCH_CODE, fields=[
            'ann_date', 'f_ann_date', 'end_date', 'revenue',
            'n_income_attr_p', 'report_type'
        ])
        if df is not None and not df.empty:
            # 只取合并报表
            df = df[df['report_type'] == '1'].sort_values('end_date', ascending=False)
            return df.head(8)  # 最近8个报告期
    except Exception as e:
        print(f"获取季报数据失败: {e}")
    
    # 备选：用fina_indicator获取扣非数据
    try:
        df = pro.fina_indicator(ts_code=CONCH_CODE, fields=[
            'ann_date', 'end_date', 'revenue', 'netprofit_yoy',
            'dt_netprofit_yoy', 'roe', 'grossprofit_margin',
            'op_yoy'
        ])
        if df is not None and not df.empty:
            df = df.sort_values('end_date', ascending=False)
            return df.head(8)
    except Exception as e:
        print(f"获取财务指标失败: {e}")
    return None


def analyze_pb(basic_df):
    """分析PB估值位置"""
    if basic_df is None or basic_df.empty:
        return None
    
    try:
        latest = basic_df.iloc[-1]
        pb_now = latest.get('pb')
        if pb_now is None:
            return None
        
        pb_now = round(pb_now, 3)
        
        # 计算PB历史分位（近1年）
        pb_series = basic_df['pb'].dropna()
        if len(pb_series) < 20:
            return None
        
        pb_min = round(pb_series.min(), 3)
        pb_max = round(pb_series.max(), 3)
        pb_mean = round(pb_series.mean(), 3)
        pb_percentile = round((pb_now - pb_min) / (pb_max - pb_min) * 100, 1) if pb_max > pb_min else 50
        
        # 近5日PB趋势
        pb_5d_ago = round(pb_series.iloc[-5], 3) if len(pb_series) >= 5 else None
        pb_20d_ago = round(pb_series.iloc[-20], 3) if len(pb_series) >= 20 else None
        
        pb_trend = "—"
        if pb_5d_ago and pb_20d_ago:
            if pb_now > pb_5d_ago > pb_20d_ago:
                pb_trend = "📈 连续回升"
            elif pb_now > pb_5d_ago:
                pb_trend = "↗️ 短期回升"
            elif pb_now < pb_5d_ago < pb_20d_ago:
                pb_trend = "📉 持续下探"
            elif pb_now < pb_5d_ago:
                pb_trend = "↘️ 短期回落"
            else:
                pb_trend = "➡️ 横盘"
        
        # 估值阶段判断
        if pb_now <= PB_BOTTOM:
            stage = "🔴 极度低估（历史底部区域）"
        elif pb_now < 0.8:
            stage = "🟡 低估区间（估值修复空间大）"
        elif pb_now < PB_REPAIR_TARGET:
            stage = "🟢 修复进行中（接近第一目标）"
        elif pb_now < PB_MID:
            stage = "🔵 估值修复基本完成"
        else:
            stage = "🟠 接近历史中枢（注意风险）"
        
        return {
            'pb_now': pb_now,
            'pb_min_1y': pb_min,
            'pb_max_1y': pb_max,
            'pb_mean_1y': pb_mean,
            'pb_percentile': pb_percentile,
            'pb_5d_ago': pb_5d_ago,
            'pb_20d_ago': pb_20d_ago,
            'pb_trend': pb_trend,
            'stage': stage,
            'pe_ttm': round(latest.get('pe_ttm', 0), 2) if latest.get('pe_ttm') else None,
            'dv_ttm': round(latest.get('dv_ttm', 0), 2) if latest.get('dv_ttm') else None,
        }
    except Exception as e:
        print(f"PB分析异常: {e}")
        return None


def analyze_technicals(daily_df):
    """分析技术面信号（MA突破）"""
    if daily_df is None or len(daily_df) < 60:
        return None
    
    try:
        close = daily_df['close'].values
        vol = daily_df['vol'].values
        
        price_now = close[-1]
        price_yesterday = close[-2] if len(close) >= 2 else price_now
        
        # 计算均线
        ma5 = round(np.mean(close[-5:]), 2) if len(close) >= 5 else None
        ma10 = round(np.mean(close[-10:]), 2) if len(close) >= 10 else None
        ma20 = round(np.mean(close[-20:]), 2) if len(close) >= 20 else None
        ma60 = round(np.mean(close[-60:]), 2) if len(close) >= 60 else None
        ma120 = round(np.mean(close[-120:]), 2) if len(close) >= 120 else None
        
        # 昨日MA20（用于判断突破）
        ma20_yesterday = round(np.mean(close[-21:-1]), 2) if len(close) >= 21 else None
        ma60_yesterday = round(np.mean(close[-61:-1]), 2) if len(close) >= 61 else None
        
        # 成交量分析
        vol_5d_avg = round(np.mean(vol[-5:]), 0) if len(vol) >= 5 else None
        vol_20d_avg = round(np.mean(vol[-20:]), 0) if len(vol) >= 20 else None
        vol_ratio = round(vol[-1] / vol_5d_avg, 2) if vol_5d_avg and vol_5d_avg > 0 else None
        
        # MA20方向（最近5日MA20斜率）
        ma20_direction = "—"
        if len(close) >= 25:
            ma20_5d_ago = round(np.mean(close[-25:-5]), 2)
            if ma20 and ma20 > ma20_5d_ago + 0.05:
                ma20_direction = "📈 拐头向上"
            elif ma20 and ma20 < ma20_5d_ago - 0.05:
                ma20_direction = "📉 向下"
            else:
                ma20_direction = "➡️ 走平"
        
        # 信号判断
        signals = []
        alert_level = 0  # 0=无信号, 1=关注, 2=重要, 3=买入信号
        
        # MA20突破判断
        if ma20 and ma20_yesterday:
            above_ma20_today = price_now > ma20
            above_ma20_yesterday = price_yesterday > ma20_yesterday
            
            if above_ma20_today and not above_ma20_yesterday:
                signals.append("🔥 今日站上MA20（短期趋势转好信号！）")
                alert_level = max(alert_level, 2)
            elif above_ma20_today:
                signals.append("✅ 站在MA20之上")
                alert_level = max(alert_level, 1)
            else:
                signals.append("⚠️ 在MA20之下（等待突破）")
        
        # MA60突破判断
        if ma60 and ma60_yesterday:
            above_ma60_today = price_now > ma60
            above_ma60_yesterday = price_yesterday > ma60_yesterday
            
            if above_ma60_today and not above_ma60_yesterday:
                signals.append("🔥🔥 今日突破MA60（中期趋势反转信号！）")
                alert_level = max(alert_level, 3)
            elif above_ma60_today:
                signals.append("✅ 站在MA60之上")
            else:
                signals.append("⚠️ 在MA60之下")
        
        # 放量判断
        if vol_ratio and vol_ratio >= 1.5:
            signals.append(f"📊 今日放量（量比{vol_ratio:.1f}x）")
            if alert_level >= 2:
                signals.append("💡 放量+突破均线 = 强确认信号！")
                alert_level = max(alert_level, 3)
        
        # MA20方向
        if "拐头向上" in ma20_direction:
            signals.append("✅ MA20拐头向上（趋势转好）")
            alert_level = max(alert_level, 1)
        
        # 均线多头排列判断
        if ma5 and ma10 and ma20 and ma60:
            if ma5 > ma10 > ma20 > ma60:
                signals.append("🔥🔥🔥 均线多头排列（强势信号）")
                alert_level = max(alert_level, 3)
        
        return {
            'price': price_now,
            'change_pct': round(daily_df.iloc[-1]['pct_chg'], 2) if 'pct_chg' in daily_df.columns else 0,
            'ma5': ma5,
            'ma10': ma10,
            'ma20': ma20,
            'ma60': ma60,
            'ma120': ma120,
            'ma20_direction': ma20_direction,
            'vol_today': vol[-1] if len(vol) > 0 else 0,
            'vol_5d_avg': vol_5d_avg,
            'vol_ratio': vol_ratio,
            'signals': signals,
            'alert_level': alert_level,
        }
    except Exception as e:
        print(f"技术面分析异常: {e}")
        return None


def analyze_fundamentals(quarterly_df):
    """分析基本面（季报利润趋势）"""
    if quarterly_df is None or quarterly_df.empty:
        return None
    
    lines = []
    
    try:
        # 检查是否有同比增速字段
        if 'dt_netprofit_yoy' in quarterly_df.columns:
            for _, row in quarterly_df.head(4).iterrows():
                end = row.get('end_date', '')
                yoy = row.get('dt_netprofit_yoy')
                rev_yoy = row.get('op_yoy')
                roe = row.get('roe')
                gm = row.get('grossprofit_margin')
                
                period = ""
                if str(end).endswith("1231"):
                    period = f"{str(end)[:4]}年报"
                elif str(end).endswith("0630"):
                    period = f"{str(end)[:4]}半年报"
                elif str(end).endswith("0331"):
                    period = f"{str(end)[:4]}一季报"
                elif str(end).endswith("0930"):
                    period = f"{str(end)[:4]}三季报"
                else:
                    period = str(end)
                
                yoy_str = f"扣非同比{yoy:+.1f}%" if yoy is not None else "扣非N/A"
                arrow = "🟢" if yoy and yoy > 0 else "🔴" if yoy and yoy < 0 else "⚪"
                gm_str = f"毛利率{gm:.1f}%" if gm is not None else ""
                
                lines.append(f"  {arrow} {period}: {yoy_str} {gm_str}")
        
        elif 'n_income_attr_p' in quarterly_df.columns:
            for _, row in quarterly_df.head(4).iterrows():
                end = row.get('end_date', '')
                profit = row.get('n_income_attr_p')
                revenue = row.get('revenue')
                
                period = ""
                if str(end).endswith("1231"):
                    period = f"{str(end)[:4]}年报"
                elif str(end).endswith("0630"):
                    period = f"{str(end)[:4]}半年报"
                elif str(end).endswith("0331"):
                    period = f"{str(end)[:4]}一季报"
                elif str(end).endswith("0930"):
                    period = f"{str(end)[:4]}三季报"
                else:
                    period = str(end)
                
                p_str = f"归母净利{profit/1e8:.1f}亿" if profit else "N/A"
                r_str = f"营收{revenue/1e8:.0f}亿" if revenue else ""
                lines.append(f"  {period}: {p_str} {r_str}")
    except Exception as e:
        print(f"基本面分析异常: {e}")
        lines.append(f"  ⚠️ 数据解析异常: {e}")
    
    return lines if lines else None


def build_message(pb_result, tech_result, fundamental_lines):
    """构建飞书推送消息"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    lines = []
    
    # 判断是否有重大信号
    alert_level = tech_result.get('alert_level', 0) if tech_result else 0
    
    if alert_level >= 3:
        lines.append(f"🚨🚨🚨 海螺水泥估值修复重大信号！")
    elif alert_level >= 2:
        lines.append(f"⚡ 海螺水泥估值修复信号出现")
    else:
        lines.append(f"📊 海螺水泥估值修复日报")
    
    lines.append(f"时间: {now}")
    lines.append("=" * 36)
    
    # 维度一：PB估值
    lines.append("")
    lines.append("【维度一：PB估值位置】")
    if pb_result:
        pb = pb_result['pb_now']
        lines.append(f"  当前PB: {pb:.3f}")
        lines.append(f"  1年范围: {pb_result['pb_min_1y']:.3f} ~ {pb_result['pb_max_1y']:.3f}")
        lines.append(f"  1年分位: {pb_result['pb_percentile']:.0f}%")
        lines.append(f"  PB趋势: {pb_result['pb_trend']}")
        lines.append(f"  阶段: {pb_result['stage']}")
        
        if pb_result.get('pe_ttm'):
            lines.append(f"  PE(TTM): {pb_result['pe_ttm']:.1f}")
        if pb_result.get('dv_ttm'):
            lines.append(f"  股息率: {pb_result['dv_ttm']:.2f}%")
        
        # 距离目标
        if pb < PB_REPAIR_TARGET:
            upside = round((PB_REPAIR_TARGET / pb - 1) * 100, 1)
            lines.append(f"  📐 距修复目标PB={PB_REPAIR_TARGET}: 还有{upside}%空间")
    else:
        lines.append("  ⚠️ 数据获取失败")
    
    # 维度二：技术面
    lines.append("")
    lines.append("【维度二：技术面信号】")
    if tech_result:
        price = tech_result['price']
        change = tech_result['change_pct']
        arrow = "🔴" if change > 0 else "🟢" if change < 0 else "⚪"
        lines.append(f"  股价: {price:.2f} {arrow} {change:+.2f}%")
        
        if tech_result.get('ma20'):
            diff_ma20 = round((price / tech_result['ma20'] - 1) * 100, 2)
            lines.append(f"  MA20: {tech_result['ma20']:.2f} (偏离{diff_ma20:+.2f}%)")
        if tech_result.get('ma60'):
            diff_ma60 = round((price / tech_result['ma60'] - 1) * 100, 2)
            lines.append(f"  MA60: {tech_result['ma60']:.2f} (偏离{diff_ma60:+.2f}%)")
        if tech_result.get('ma120'):
            lines.append(f"  MA120: {tech_result['ma120']:.2f}")
        
        lines.append(f"  MA20方向: {tech_result['ma20_direction']}")
        
        if tech_result.get('vol_ratio'):
            lines.append(f"  量比: {tech_result['vol_ratio']:.2f}x")
        
        lines.append("")
        lines.append("  信号判断:")
        for s in tech_result.get('signals', []):
            lines.append(f"  {s}")
    else:
        lines.append("  ⚠️ 数据获取失败")
    
    # 维度三：基本面
    lines.append("")
    lines.append("【维度三：基本面验证】")
    if fundamental_lines:
        for fl in fundamental_lines:
            lines.append(fl)
    else:
        lines.append("  ⚠️ 数据获取失败")
    
    # 关键时间节点提醒
    lines.append("")
    lines.append("【📅 下一个验证节点】")
    now_date = datetime.now()
    checkpoints = [
        ("2026-03-25", "海螺2025年报披露（确认全年扣非拐点）"),
        ("2026-04-30", "海螺2026一季报截止日（验证增长延续）"),
    ]
    for date_str, desc in checkpoints:
        try:
            cp_date = datetime.strptime(date_str, "%Y-%m-%d")
            if cp_date > now_date:
                days_left = (cp_date - now_date).days
                lines.append(f"  ⏰ {date_str}: {desc} (还有{days_left}天)")
        except:
            pass
    
    # 综合评估
    lines.append("")
    lines.append("─" * 36)
    lines.append("【综合评估】")
    
    score = 0
    checks = []
    
    # PB评分
    if pb_result:
        if pb_result['pb_now'] < 0.8:
            checks.append("✅ PB低估 (修复空间大)")
            score += 1
        elif pb_result['pb_now'] < PB_REPAIR_TARGET:
            checks.append("✅ PB修复进行中")
            score += 1
        else:
            checks.append("⚠️ PB已修复到位")
        
        if "回升" in pb_result['pb_trend']:
            checks.append("✅ PB趋势向上")
            score += 1
        else:
            checks.append("⚠️ PB趋势未明")
    
    # 技术面评分
    if tech_result:
        if tech_result.get('ma20') and tech_result['price'] > tech_result['ma20']:
            checks.append("✅ 站上MA20")
            score += 1
        else:
            checks.append("❌ 未站上MA20")
        
        if "拐头向上" in tech_result.get('ma20_direction', ''):
            checks.append("✅ MA20拐头向上")
            score += 1
        else:
            checks.append("⚠️ MA20未拐头")
        
        if tech_result.get('ma60') and tech_result['price'] > tech_result['ma60']:
            checks.append("✅ 站上MA60")
            score += 1
        else:
            checks.append("❌ 未站上MA60")
    
    for c in checks:
        lines.append(f"  {c}")
    
    lines.append(f"  得分: {score}/6")
    
    if score >= 5:
        lines.append("  🟢 估值修复确认，可考虑买入")
    elif score >= 3:
        lines.append("  🟡 估值修复进行中，继续观察")
    else:
        lines.append("  🔴 估值修复尚未启动，耐心等待")
    
    # 佰维模式提醒
    lines.append("")
    lines.append("💡 佰维模式检查清单:")
    lines.append("  □ 扣非净利润拐点? (2025H1已+31%)")
    lines.append("  □ MA20放量突破? (等待确认)")
    lines.append("  □ 量≥1.5x五日均量? (看量比)")
    
    return "\n".join(lines)


def send_to_feishu(message, webhook_url=None):
    """发送到飞书"""
    if not webhook_url:
        print("⚠️ 未指定飞书Webhook地址，跳过推送")
        return False
    
    payload = {
        "msg_type": "text",
        "content": {"text": message}
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code == 200:
            result = resp.json()
            if result.get('code') == 0 or result.get('StatusCode') == 0:
                print("✅ 飞书推送成功")
                return True
            else:
                print(f"⚠️ 飞书返回: {result}")
                return False
        else:
            print(f"❌ HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"❌ 推送失败: {e}")
        return False


def main():
    # 命令行参数解析
    parser = argparse.ArgumentParser(
        description="海螺水泥估值修复监控脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python conch_valuation_monitor.py                           # 查看分析
  python conch_valuation_monitor.py --output result.txt       # 保存到文件
  python conch_valuation_monitor.py --feishu --webhook "URL"  # 推送到飞书
        """
    )
    
    parser.add_argument(
        "--feishu",
        action="store_true",
        help="启用飞书推送"
    )
    parser.add_argument(
        "--webhook",
        help="飞书Webhook地址"
    )
    parser.add_argument(
        "--output",
        help="保存结果到文件"
    )
    
    args = parser.parse_args()
    
    print(f"=== 海螺水泥估值修复监控 ===")
    print(f"时间: {datetime.now()}")
    print()
    
    # 获取数据
    print("获取日线数据...")
    daily_df = get_daily_data(250)
    time.sleep(0.3)
    
    print("获取估值指标...")
    basic_df = get_basic_data(250)
    time.sleep(0.3)
    
    print("获取季报数据...")
    quarterly_df = get_quarterly_profit()
    
    # 分析
    print("\n分析PB估值...")
    pb_result = analyze_pb(basic_df)
    
    print("分析技术面...")
    tech_result = analyze_technicals(daily_df)
    
    print("分析基本面...")
    fundamental_lines = analyze_fundamentals(quarterly_df)
    
    # 构建消息
    message = build_message(pb_result, tech_result, fundamental_lines)
    print("\n" + message)
    
    # 保存到文件
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(message)
            print(f"\n✅ 结果已保存到: {args.output}")
        except Exception as e:
            print(f"\n⚠️ 保存文件失败: {e}")
    
    # 推送到飞书
    if args.feishu:
        print("\n推送到飞书...")
        webhook_url = args.webhook or os.environ.get("FEISHU_WEBHOOK")
        success = send_to_feishu(message, webhook_url)
        
        # 如果有重大信号，额外推送一条醒目提醒
        if success and tech_result and tech_result.get('alert_level', 0) >= 3:
            alert_msg = (
                f"🚨🚨🚨 海螺水泥(600585)买入信号！\n\n"
                f"股价: {tech_result['price']:.2f}\n"
                f"信号: {'、'.join(tech_result.get('signals', []))}\n\n"
                f"请立即查看详细分析并决策！"
            )
            send_to_feishu(alert_msg, webhook_url)
    
    print(f"\n完成! {datetime.now()}")


if __name__ == "__main__":
    main()
