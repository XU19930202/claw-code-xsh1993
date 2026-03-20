"""
回测中润资源（000506.SZ）
使用并行回测系统的适配逻辑
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tushare as ts
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import config

def backtest_000506():
    """回测中润资源（000506.SZ）"""
    
    stock_code = "000506"
    ts_code = "000506.SZ"
    stock_name = "中润资源"
    
    print(f"\n{'='*60}")
    print(f"回测 {stock_name} ({ts_code})")
    print(f"{'='*60}")
    
    # 初始化Tushare Pro
    try:
        pro = ts.pro_api()
        print("[OK] Tushare Pro API连接成功")
    except Exception as e:
        print(f"[ERROR] Tushare Pro API连接失败: {e}")
        return
    
    # 设置日期范围（获取更长时间的数据）
    end_date = datetime.now()
    start_date = datetime(2020, 1, 1)  # 获取5年数据
    
    start_str = start_date.strftime('%Y%m%d')
    end_str = end_date.strftime('%Y%m%d')
    
    print(f"数据范围: {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}")
    
    # 1. 获取日线数据
    print("\n[1/4] 获取日线数据...")
    try:
        daily_df = pro.daily(ts_code=ts_code, start_date=start_str, end_date=end_str)
        
        if daily_df.empty:
            print(f"[ERROR] 未获取到{stock_name}的日线数据")
            return
            
        print(f"[OK] 获取到{daily_df.shape[0]}个交易日数据")
        
    except Exception as e:
        print(f"[ERROR] 获取日线数据失败: {e}")
        return
    
    # 2. 获取换手率等基本面数据
    print("\n[2/4] 获取换手率数据...")
    try:
        basic_df = pro.daily_basic(ts_code=ts_code, start_date=start_str, end_date=end_str)
        print(f"[OK] 获取到换手率数据: {basic_df.shape[0]}行")
        
    except Exception as e:
        print(f"[ERROR] 获取换手率数据失败: {e}")
        basic_df = None
    
    # 3. 准备回测数据
    print("\n[3/4] 准备回测数据...")
    
    # 重命名列（适配回测函数）
    column_mapping = {
        'ts_code': 'ts_code',
        'trade_date': '交易日期',
        'open': '开盘价(元)',
        'high': '最高价(元)',
        'low': '最低价(元)',
        'close': '收盘价(元)',
        'vol': '成交量(万股)',  # 注意：Tushare的vol是手，后面会转换为万股
        'amount': '成交额(万元)',
        'pct_chg': '涨跌幅(%)'
    }
    
    df = daily_df.rename(columns=column_mapping)
    
    # 转换成交量单位：手 → 万股
    df['成交量(万股)'] = df['成交量(万股)'] / 100
    
    # 转换日期格式
    df['交易日期'] = pd.to_datetime(df['交易日期'], format='%Y%m%d')
    
    # 添加前复权收盘价列（简化处理，与前收盘价相同）
    df['收盘价(前复权)(元)'] = df['收盘价(元)']
    
    # 合并换手率数据
    if basic_df is not None and not basic_df.empty:
        basic_df['交易日期'] = pd.to_datetime(basic_df['trade_date'], format='%Y%m%d')
        df = df.merge(basic_df[['交易日期', 'turnover_rate', 'volume_ratio']], 
                     on='交易日期', how='left')
        df['换手率(%)'] = df['turnover_rate'].fillna(0)
    else:
        df['换手率(%)'] = 0
    
    print(f"[OK] 数据准备完成，总数据行数: {df.shape[0]}")
    
    # 计算股价涨幅（从数据开始到结束）
    if len(df) > 0:
        start_price = df['收盘价(元)'].iloc[0]
        end_price = df['收盘价(元)'].iloc[-1]
        price_change_pct = ((end_price - start_price) / start_price) * 100
        print(f"[INFO] 股价变化: {start_price:.2f}元 → {end_price:.2f}元 ({price_change_pct:+.2f}%)")
    
    print()
    
    # 4. 执行回测
    print("[4/4] 执行回测...")
    try:
        # 导入回测函数
        from breakout_strategy_v5_patched import backtest
        
        # 执行回测
        trades = backtest(df, stock_code, None, verbose=True, stock_name=stock_name)
        
        if trades:
            print(f"\n[SUCCESS] 回测完成，生成交易数: {len(trades)}")
            
            # 计算总收益
            total_pnl = sum(trade.pnl for trade in trades)
            
            # 计算胜率
            winning_trades = sum(1 for trade in trades if trade.pnl > 0)
            win_rate = (winning_trades / len(trades)) * 100 if trades else 0
            
            # 计算平均盈亏
            avg_pnl = total_pnl / len(trades) if trades else 0
            
            print(f"\n[策略总结]")
            print(f"  总交易数: {len(trades)}")
            print(f"  胜率: {win_rate:.1f}% ({winning_trades}胜/{len(trades)-winning_trades}负)")
            print(f"  总收益: {total_pnl:+.2f}%")
            print(f"  平均收益/笔: {avg_pnl:+.2f}%")
            
            # 打印前5笔交易详情
            print(f"\n[前5笔交易详情]")
            for i, trade in enumerate(trades[:5]):
                print(f"  交易{i+1}: {trade.signal_date} buy@{trade.buy_price:.2f} → {trade.exit_date} exit@{trade.exit_price:.2f} | 收益: {trade.pnl:+.2f}%")
            
            # 策略评价
            print(f"\n[策略评价]")
            if total_pnl > 0:
                print(f"  [+] 策略表现: 盈利，总收益 {total_pnl:+.2f}%")
                if total_pnl > 20:
                    print(f"  [++] 表现优秀，大幅跑赢基准")
                elif total_pnl > 0:
                    print(f"  [+] 表现尚可，小幅盈利")
            else:
                print(f"  [-] 策略表现: 亏损，总收益 {total_pnl:+.2f}%")
                if total_pnl < -20:
                    print(f"  [--] 表现较差，大幅亏损")
                else:
                    print(f"  [-] 表现不佳，小幅亏损")
            
            # 与股价涨幅比较
            if len(df) > 0:
                strategy_vs_price = total_pnl - price_change_pct
                print(f"\n[策略vs股价表现]")
                print(f"  股价涨幅: {price_change_pct:+.2f}%")
                print(f"  策略收益: {total_pnl:+.2f}%")
                print(f"  超额收益: {strategy_vs_price:+.2f}%")
                
                if strategy_vs_price > 0:
                    print(f"  [+] 策略跑赢股价{strategy_vs_price:.2f}%")
                else:
                    print(f"  [-] 策略跑输股价{-strategy_vs_price:.2f}%")
                    
        else:
            print(f"[WARNING] 回测完成，但未生成任何交易")
            
    except Exception as e:
        print(f"[ERROR] 回测执行失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n{'='*60}")
    print(f"回测完成")
    print(f"{'='*60}")

if __name__ == "__main__":
    # 设置Tushare token
    ts.set_token(config.TUSHARE_TOKEN)
    backtest_000506()