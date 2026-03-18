#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
水泥价格 + 动力煤价格 每日追踪脚本
推送到飞书群，用于跟踪水泥行业周期拐点

跟踪指标：
1. 动力煤期货主力合约价格（Tushare）
2. 全国水泥价格指数（爬取中国水泥网）
3. 海螺水泥股价和PE（Tushare）

使用方法：
  python cement_coal_tracker.py
  
  带飞书推送：
  python cement_coal_tracker.py --feishu
  
  指定飞书Webhook：
  python cement_coal_tracker.py --feishu --webhook "你的webhook地址"

定时任务（每天17:30推送）：
  30 17 * * 1-5 cd /path/to/scripts && python cement_coal_tracker.py --feishu
"""

import json
import time
import requests
import tushare as ts
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
# 从环境变量或config.py读取Tushare Token
_TUSHARE_TOKEN = TUSHARE_TOKEN

# 飞书Webhook（可通过命令行参数指定）
_FEISHU_WEBHOOK = None

# 海螺水泥代码
CONCH_CODE = "600585.SH"

# 动力煤期货主力合约代码（郑商所）
COAL_FUTURE = "ZC.ZCE"

# ============ 初始化 ============
ts.set_token(_TUSHARE_TOKEN)
pro = ts.pro_api()


def get_coal_futures_price():
    """获取动力煤期货主力合约价格"""
    try:
        today = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")
        
        # 获取动力煤期货日线数据
        df = pro.fut_daily(ts_code=COAL_FUTURE, start_date=start, end_date=today)
        
        if df is None or df.empty:
            # 尝试用期货主力映射
            df = pro.fut_mapping(ts_code="ZC.ZCE")
            if df is not None and not df.empty:
                main_contract = df.iloc[0]['mapping_ts_code']
                df = pro.fut_daily(ts_code=main_contract, start_date=start, end_date=today)
        
        if df is None or df.empty:
            return None
            
        df = df.sort_values('trade_date', ascending=True)
        latest = df.iloc[-1]
        
        # 计算周环比和月环比
        price_now = latest['close']
        
        week_ago_price = None
        month_ago_price = None
        
        if len(df) >= 5:
            week_ago_price = df.iloc[-5]['close']
        if len(df) >= 22:
            month_ago_price = df.iloc[-22]['close']
        
        result = {
            'date': latest['trade_date'],
            'price': price_now,
            'open': latest['open'],
            'high': latest['high'],
            'low': latest['low'],
            'change_pct': latest.get('pct_chg', 0),
            'week_change': round((price_now / week_ago_price - 1) * 100, 2) if week_ago_price else None,
            'month_change': round((price_now / month_ago_price - 1) * 100, 2) if month_ago_price else None,
        }
        return result
    except Exception as e:
        print(f"获取煤炭期货数据失败: {e}")
        return None


def get_cement_price_index():
    """
    获取全国水泥价格指数
    数据源：百年建筑网 / 中国水泥网
    注：如果爬取失败，会返回None，需要手动关注水泥网数据
    """
    try:
        # 尝试从百年建筑网API获取水泥价格
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # 百年建筑网水泥价格页面
        url = "https://www.100njz.com/api/price/cement"
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            return data
    except:
        pass
    
    try:
        # 备选：尝试从水泥网获取
        url = "https://www.ccement.com/api/index"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    
    return None


def get_conch_stock_data():
    """获取海螺水泥股票数据（股价、PE、PB）"""
    try:
        today = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")
        
        # 日线行情
        df = pro.daily(ts_code=CONCH_CODE, start_date=start, end_date=today)
        if df is None or df.empty:
            return None
        
        df = df.sort_values('trade_date', ascending=True)
        latest = df.iloc[-1]
        
        # 每日指标（PE/PB）
        df_basic = pro.daily_basic(ts_code=CONCH_CODE, start_date=start, end_date=today)
        pe_ttm = None
        pb = None
        div_yield = None
        if df_basic is not None and not df_basic.empty:
            df_basic = df_basic.sort_values('trade_date', ascending=True)
            latest_basic = df_basic.iloc[-1]
            pe_ttm = latest_basic.get('pe_ttm')
            pb = latest_basic.get('pb')
            div_yield = latest_basic.get('dv_ttm')
        
        # 周涨幅和月涨幅
        price_now = latest['close']
        week_change = None
        month_change = None
        
        if len(df) >= 5:
            week_change = round((price_now / df.iloc[-5]['close'] - 1) * 100, 2)
        if len(df) >= 22:
            month_change = round((price_now / df.iloc[-22]['close'] - 1) * 100, 2)
        
        # MA20
        ma20 = None
        if len(df) >= 20:
            ma20 = round(df.tail(20)['close'].mean(), 2)
        
        result = {
            'date': latest['trade_date'],
            'close': price_now,
            'change_pct': latest['pct_chg'],
            'volume': latest['vol'],
            'pe_ttm': round(pe_ttm, 2) if pe_ttm else None,
            'pb': round(pb, 2) if pb else None,
            'div_yield': round(div_yield, 2) if div_yield else None,
            'ma20': ma20,
            'week_change': week_change,
            'month_change': month_change,
            'above_ma20': price_now > ma20 if ma20 else None,
        }
        return result
    except Exception as e:
        print(f"获取海螺水泥数据失败: {e}")
        return None


def build_message(coal_data, cement_data, conch_data):
    """构建飞书推送消息"""
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    lines = []
    lines.append(f"📊 水泥行业周期追踪 | {now}")
    lines.append("=" * 36)
    
    # 动力煤部分
    lines.append("")
    lines.append("🔥 【动力煤期货】")
    if coal_data:
        try:
            price = coal_data.get('price')
            if price is not None:
                change = coal_data.get('change_pct', 0)
                arrow = "🔴" if change > 0 else "🟢" if change < 0 else "⚪"
                lines.append(f"  收盘价: {price:.1f} 元/吨 {arrow} {change:+.2f}%")
                
                high = coal_data.get('high')
                low = coal_data.get('low')
                if high is not None and low is not None:
                    lines.append(f"  日内: {low:.1f} - {high:.1f}")
                
                if coal_data.get('week_change') is not None:
                    lines.append(f"  周涨跌: {coal_data['week_change']:+.2f}%")
                if coal_data.get('month_change') is not None:
                    lines.append(f"  月涨跌: {coal_data['month_change']:+.2f}%")
                
                # 煤价对水泥利润的判断
                if coal_data.get('month_change') is not None:
                    if coal_data['month_change'] < -5:
                        lines.append("  💡 煤价月跌幅>5%，利好水泥企业利润")
                    elif coal_data['month_change'] > 5:
                        lines.append("  ⚠️ 煤价月涨幅>5%，水泥成本端承压")
            else:
                lines.append("  ⚠️ 数据获取失败，请手动查看期货软件")
        except Exception as e:
            lines.append(f"  ⚠️ 数据解析异常: {e}")
    else:
        lines.append("  ⚠️ 数据获取失败，请手动查看期货软件")
    
    # 水泥价格部分
    lines.append("")
    lines.append("🏗️ 【水泥价格指数】")
    if cement_data and isinstance(cement_data, dict):
        lines.append(f"  数据: {json.dumps(cement_data, ensure_ascii=False)[:200]}")
    else:
        lines.append("  ⚠️ 自动获取失败")
        lines.append("  📎 请手动查看:")
        lines.append("  中国水泥网: www.ccement.com")
        lines.append("  百年建筑网: www.100njz.com")
        lines.append("  关注: 全国P.O42.5散装水泥均价")
    
    # 海螺水泥部分
    lines.append("")
    lines.append("🐚 【海螺水泥 600585】")
    if conch_data:
        try:
            price = conch_data.get('close')
            if price is not None:
                change = conch_data.get('change_pct', 0)
                arrow = "🔴" if change > 0 else "🟢" if change < 0 else "⚪"
                lines.append(f"  股价: {price:.2f} {arrow} {change:+.2f}%")
                
                if conch_data.get('pe_ttm'):
                    pe = conch_data['pe_ttm']
                    # PE历史位置判断
                    pe_comment = ""
                    if pe > 20:
                        pe_comment = " (偏高→利润在底部，关注拐点)"
                    elif pe < 10:
                        pe_comment = " (偏低→利润在高位，注意见顶风险)"
                    else:
                        pe_comment = " (中等区间)"
                    lines.append(f"  PE(TTM): {pe:.1f}{pe_comment}")
                
                if conch_data.get('pb'):
                    lines.append(f"  PB: {conch_data['pb']:.2f}")
                
                if conch_data.get('div_yield'):
                    lines.append(f"  股息率: {conch_data['div_yield']:.2f}%")
                
                if conch_data.get('ma20'):
                    ma20 = conch_data['ma20']
                    above = "站上" if conch_data.get('above_ma20') else "跌破"
                    lines.append(f"  MA20: {ma20:.2f} (当前{above}MA20)")
                
                if conch_data.get('week_change') is not None:
                    lines.append(f"  周涨跌: {conch_data['week_change']:+.2f}%")
                if conch_data.get('month_change') is not None:
                    lines.append(f"  月涨跌: {conch_data['month_change']:+.2f}%")
            else:
                lines.append("  ⚠️ 数据获取失败")
        except Exception as e:
            lines.append(f"  ⚠️ 数据解析异常: {e}")
    else:
        lines.append("  ⚠️ 数据获取失败")
    
    # 综合判断
    lines.append("")
    lines.append("📋 【周期位置综合判断】")
    
    signals = []
    if coal_data and coal_data.get('month_change') is not None:
        if coal_data['month_change'] < 0:
            signals.append("✅ 煤价下行(成本利好)")
        else:
            signals.append("⚠️ 煤价上行(成本承压)")
    
    if conch_data and conch_data.get('pe_ttm'):
        if conch_data['pe_ttm'] > 18:
            signals.append("✅ PE高位(利润底部,关注拐点)")
        elif conch_data['pe_ttm'] < 10:
            signals.append("⚠️ PE低位(利润高位,注意见顶)")
        else:
            signals.append("➡️ PE中等(周期中段)")
    
    if conch_data and conch_data.get('above_ma20') is not None:
        if conch_data['above_ma20']:
            signals.append("✅ 站上MA20(短期趋势向好)")
        else:
            signals.append("⚠️ 跌破MA20(短期趋势偏弱)")
    
    for s in signals:
        lines.append(f"  {s}")
    
    lines.append("")
    lines.append("─" * 36)
    lines.append("💡 操作提示: 周期股看拐点不看PE高低")
    lines.append("   煤价↓ + 水泥价↑ + 扣非拐点 = 买入窗口")
    
    return "\n".join(lines)


def send_to_feishu(message, webhook_url=None):
    """发送到飞书群"""
    if not webhook_url:
        print("⚠️ 未指定飞书Webhook地址，跳过推送")
        return False
    
    payload = {
        "msg_type": "text",
        "content": {
            "text": message
        }
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code == 200:
            result = resp.json()
            if result.get('code') == 0 or result.get('StatusCode') == 0:
                print("✅ 飞书推送成功")
                return True
            else:
                print(f"⚠️ 飞书返回异常: {result}")
                return False
        else:
            print(f"❌ 飞书推送失败: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"❌ 飞书推送异常: {e}")
        return False


def main():
    # 命令行参数解析
    parser = argparse.ArgumentParser(
        description="水泥行业周期追踪脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python cement_coal_tracker.py                           # 只显示数据
  python cement_coal_tracker.py --feishu                  # 推送到环境变量指定的飞书
  python cement_coal_tracker.py --feishu --webhook "xxx"  # 推送到指定webhook
        """
    )
    
    parser.add_argument(
        "--feishu",
        action="store_true",
        help="启用飞书推送（需指定--webhook或设置环境变量FEISHU_WEBHOOK）"
    )
    parser.add_argument(
        "--webhook",
        help="飞书机器人Webhook地址"
    )
    parser.add_argument(
        "--output",
        help="输出结果到文件（默认仅打印到控制台）"
    )
    
    args = parser.parse_args()
    
    print(f"开始获取数据... {datetime.now()}")
    
    # 1. 获取动力煤期货价格
    print("获取动力煤期货数据...")
    coal_data = get_coal_futures_price()
    time.sleep(0.5)
    
    # 2. 获取水泥价格指数
    print("获取水泥价格指数...")
    cement_data = get_cement_price_index()
    time.sleep(0.5)
    
    # 3. 获取海螺水泥股票数据
    print("获取海螺水泥数据...")
    conch_data = get_conch_stock_data()
    
    # 4. 构建消息
    message = build_message(coal_data, cement_data, conch_data)
    
    # 5. 输出到控制台或文件
    print("\n" + message)
    
    # 6. 可选：保存到文件
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(message)
            print(f"\n✅ 结果已保存到: {args.output}")
        except Exception as e:
            print(f"\n⚠️ 保存文件失败: {e}")
    
    # 7. 推送到飞书
    if args.feishu:
        print("\n推送到飞书...")
        webhook_url = args.webhook or os.environ.get("FEISHU_WEBHOOK")
        send_to_feishu(message, webhook_url)
    
    print(f"\n完成! {datetime.now()}")


if __name__ == "__main__":
    import os
    main()
