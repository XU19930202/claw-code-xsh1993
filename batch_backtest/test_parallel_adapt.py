#!/usr/bin/env python3
"""测试并行回测的适配逻辑"""

import sys
import os
import pandas as pd

# 添加路径
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

print("测试并行回测适配逻辑...")
print("=" * 60)

try:
    # 测试数据下载和适配
    import tushare as ts
    from batch_backtest_parallel import download_kline
    
    TUSHARE_TOKEN = os.environ.get('TUSHARE_TOKEN', '')
    if TUSHARE_TOKEN:
        ts.set_token(TUSHARE_TOKEN)
    
    pro = ts.pro_api()
    
    # 测试一只股票的数据下载和适配
    test_ts_code = '300502.SZ'  # 使用已有缓存的股票
    start_date = '20240101'
    end_date = '20251231'
    
    print(f"测试股票: {test_ts_code}")
    
    # 检查缓存
    from pathlib import Path
    CACHE_DIR = Path('backtest_cache')
    cache_file = CACHE_DIR / f'{test_ts_code.replace(".", "_")}.parquet'
    
    if cache_file.exists():
        print(f"缓存文件存在: {cache_file}")
        
        # 读取缓存数据
        df_cache = pd.read_parquet(cache_file)
        print(f"缓存数据形状: {df_cache.shape}")
        print(f"缓存数据列名: {', '.join(df_cache.columns.tolist())}")
        
        # 过滤指定日期范围
        df_filtered = df_cache[(df_cache['trade_date'] >= start_date) & 
                              (df_cache['trade_date'] <= end_date)].copy()
        
        print(f"过滤后数据形状: {df_filtered.shape}")
        
        # 测试列名转换
        column_mapping = {
            'trade_date': '交易日期',
            'open': '开盘价(元)',
            'high': '最高价(元)', 
            'low': '最低价(元)',
            'close': '收盘价(元)',
            'vol': '成交量(万股)',
            'amount': '成交额(万元)',
            'pct_chg': '涨跌幅(%)'
        }
        
        df_renamed = df_filtered.rename(columns=column_mapping)
        print(f"重命名后列名: {', '.join(df_renamed.columns.tolist())}")
        
        # 转换成交量单位：手 → 万股
        df_renamed['成交量(万股)'] = df_renamed['成交量(万股)'] / 100
        
        # 转换日期格式
        df_renamed['交易日期'] = pd.to_datetime(df_renamed['交易日期'], format='%Y%m%d')
        
        # 获取换手率数据
        basic_df = pro.daily_basic(ts_code=test_ts_code, start_date=start_date, end_date=end_date,
                                   fields='trade_date,turnover_rate,volume_ratio')
        
        if basic_df is not None and not basic_df.empty:
            print(f"获取到换手率数据: {basic_df.shape[0]} 行")
            basic_df['交易日期'] = pd.to_datetime(basic_df['trade_date'], format='%Y%m%d')
            df_renamed = df_renamed.merge(basic_df[['交易日期', 'turnover_rate', 'volume_ratio']], 
                                         on='交易日期', how='left')
            df_renamed['换手率(%)'] = df_renamed['turnover_rate'].fillna(0)
            print(f"合并换手率后数据形状: {df_renamed.shape}")
        else:
            print("未获取到换手率数据")
            df_renamed['换手率(%)'] = 0
    
        # 添加前复权收盘价列（与收盘价相同，简化处理）
        df_renamed['收盘价(前复权)(元)'] = df_renamed['收盘价(元)']
    
        # 测试backtest函数调用
        print("\n测试backtest函数调用...")
        try:
            from breakout_strategy_v5_patched import backtest
            
            code_only = test_ts_code.split('.')[0]
            
            # 尝试调用backtest函数
            print(f"调用backtest函数，代码: {code_only}")
            trades = backtest(
                stock_df=df_renamed,
                code=code_only,
                index_df=None,
                verbose=False,
                stock_name='新易盛'
            )
            
            if trades:
                print(f"回测成功，生成交易数: {len(trades)}")
                for i, trade in enumerate(trades[:3]):  # 只显示前3笔
                    print(f"  交易{i+1}: {trade.signal_date} buy@{trade.buy_price:.2f} → {trade.exit_date} exit@{trade.exit_price:.2f} | 收益: {trade.pnl:.2f}%")
            else:
                print("回测期间无交易信号")
                
        except Exception as e:
            print(f"backtest函数调用失败: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            
    else:
        print("缓存文件不存在，尝试下载...")
        success = download_kline(test_ts_code, start_date, end_date)
        print(f"下载结果: {'成功' if success else '失败'}")
        
except Exception as e:
    print(f"测试失败: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("测试完成")