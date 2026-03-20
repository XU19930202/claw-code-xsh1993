#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU加速模块 - 批量技术指标计算
================================
利用RTX 4050的CUDA核心，一次性计算所有股票的技术指标

适用场景：
  1. 批量计算MA5/MA20/MA60/MA120
  2. 批量成交量比（vol_ratio）
  3. 批量信号扫描（突破检测）
  4. 全市场4000+股票的指标计算

安装依赖（Windows）：
  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

使用方法：
  python gpu_accelerator.py              # 运行benchmark对比CPU vs GPU
  
在回测中使用：
  from gpu_accelerator import GPUIndicatorEngine
  engine = GPUIndicatorEngine()
  results = engine.batch_compute(all_stock_data)
"""

import time
import numpy as np
import pandas as pd
from pathlib import Path

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    print("[警告] 未安装PyTorch，GPU加速不可用")
    print("安装命令: pip install torch --index-url https://download.pytorch.org/whl/cu121")


class GPUIndicatorEngine:
    """GPU加速的技术指标批量计算引擎"""
    
    def __init__(self, device=None):
        if not HAS_TORCH:
            raise RuntimeError("需要安装PyTorch: pip install torch --index-url https://download.pytorch.org/whl/cu121")
        
        if device is None:
            if torch.cuda.is_available():
                self.device = torch.device('cuda')
                gpu_name = torch.cuda.get_device_name(0)
                vram = torch.cuda.get_device_properties(0).total_mem / 1024**3
                print(f"GPU加速已启用: {gpu_name} ({vram:.1f}GB)")
            else:
                self.device = torch.device('cpu')
                print("CUDA不可用，回退到CPU模式")
        else:
            self.device = torch.device(device)
    
    @property
    def is_gpu(self):
        return self.device.type == 'cuda'
    
    # ============================================================
    # 核心：GPU上的滑动均线计算
    # ============================================================
    
    def rolling_mean(self, tensor: torch.Tensor, window: int) -> torch.Tensor:
        """
        GPU加速的滑动均线
        tensor: shape (n_stocks, n_days)
        返回: shape (n_stocks, n_days)，前window-1个值为NaN
        """
        if tensor.dim() == 1:
            tensor = tensor.unsqueeze(0)
        
        n_stocks, n_days = tensor.shape
        
        # 用1D卷积实现滑动均线（GPU上极快）
        kernel = torch.ones(1, 1, window, device=self.device, dtype=tensor.dtype) / window
        
        # 需要padding
        padded = torch.nn.functional.pad(tensor.unsqueeze(1), (window - 1, 0), mode='constant', value=0)
        result = torch.nn.functional.conv1d(padded, kernel).squeeze(1)
        
        # 前window-1个值设为NaN
        result[:, :window - 1] = float('nan')
        
        return result
    
    def rolling_max(self, tensor: torch.Tensor, window: int) -> torch.Tensor:
        """GPU加速的滑动最大值"""
        if tensor.dim() == 1:
            tensor = tensor.unsqueeze(0)
        
        n_stocks, n_days = tensor.shape
        padded = torch.nn.functional.pad(tensor.unsqueeze(1), (window - 1, 0), mode='constant', value=float('-inf'))
        result = torch.nn.functional.max_pool1d(padded, kernel_size=window, stride=1).squeeze(1)
        result[:, :window - 1] = float('nan')
        
        return result
    
    def rolling_min(self, tensor: torch.Tensor, window: int) -> torch.Tensor:
        """GPU加速的滑动最小值"""
        return -self.rolling_max(-tensor, window)
    
    # ============================================================
    # 批量技术指标
    # ============================================================
    
    def batch_compute_indicators(self, close_matrix: np.ndarray, 
                                  vol_matrix: np.ndarray = None,
                                  high_matrix: np.ndarray = None,
                                  low_matrix: np.ndarray = None) -> dict:
        """
        一次性计算所有股票的技术指标
        
        参数:
            close_matrix: shape (n_stocks, n_days) 收盘价矩阵
            vol_matrix:   shape (n_stocks, n_days) 成交量矩阵（可选）
            high_matrix:  shape (n_stocks, n_days) 最高价矩阵（可选）
            low_matrix:   shape (n_stocks, n_days) 最低价矩阵（可选）
        
        返回: dict，每个key是指标名，value是 (n_stocks, n_days) 的numpy数组
        """
        # 转到GPU
        close = torch.tensor(close_matrix, dtype=torch.float32, device=self.device)
        
        results = {}
        
        # 均线
        results['ma5'] = self.rolling_mean(close, 5).cpu().numpy()
        results['ma10'] = self.rolling_mean(close, 10).cpu().numpy()
        results['ma20'] = self.rolling_mean(close, 20).cpu().numpy()
        results['ma60'] = self.rolling_mean(close, 60).cpu().numpy()
        results['ma120'] = self.rolling_mean(close, 120).cpu().numpy()
        
        # 均线斜率（20日）
        ma20 = torch.tensor(results['ma20'], dtype=torch.float32, device=self.device)
        ma20_prev5 = torch.roll(ma20, 5, dims=1)
        ma20_prev5[:, :5] = float('nan')
        results['ma20_slope'] = ((ma20 / ma20_prev5 - 1) * 100).cpu().numpy()
        
        # 收盘价相对均线位置
        results['close_vs_ma20'] = (close / torch.tensor(results['ma20'], device=self.device, dtype=torch.float32)).cpu().numpy()
        results['close_vs_ma60'] = (close / torch.tensor(results['ma60'], device=self.device, dtype=torch.float32)).cpu().numpy()
        
        # N日新高
        results['high_20d'] = self.rolling_max(close, 20).cpu().numpy()
        results['high_60d'] = self.rolling_max(close, 60).cpu().numpy()
        results['high_120d'] = self.rolling_max(close, 120).cpu().numpy()
        
        # 突破信号：收盘价 >= N日最高价
        results['break_20d'] = (close_matrix >= results['high_20d']).astype(np.int8)
        results['break_60d'] = (close_matrix >= results['high_60d']).astype(np.int8)
        results['break_120d'] = (close_matrix >= results['high_120d']).astype(np.int8)
        
        # 日涨跌幅
        close_prev = torch.roll(close, 1, dims=1)
        close_prev[:, 0] = float('nan')
        results['pct_chg'] = ((close / close_prev - 1) * 100).cpu().numpy()
        
        if vol_matrix is not None:
            vol = torch.tensor(vol_matrix, dtype=torch.float32, device=self.device)
            results['vol_ma5'] = self.rolling_mean(vol, 5).cpu().numpy()
            results['vol_ma20'] = self.rolling_mean(vol, 20).cpu().numpy()
            # 量比
            vol_ma20 = torch.tensor(results['vol_ma20'], device=self.device, dtype=torch.float32)
            vol_ratio = vol / vol_ma20
            vol_ratio[vol_ma20 == 0] = float('nan')
            results['vol_ratio'] = vol_ratio.cpu().numpy()
        
        if high_matrix is not None and low_matrix is not None:
            high = torch.tensor(high_matrix, dtype=torch.float32, device=self.device)
            low = torch.tensor(low_matrix, dtype=torch.float32, device=self.device)
            # 振幅
            results['amplitude'] = ((high - low) / close_prev * 100).cpu().numpy()
            # ATR (Average True Range)
            tr1 = high - low
            tr2 = torch.abs(high - close_prev)
            tr3 = torch.abs(low - close_prev)
            tr = torch.max(torch.max(tr1, tr2), tr3)
            results['atr_20'] = self.rolling_mean(tr, 20).cpu().numpy()
        
        return results
    
    # ============================================================
    # 批量信号扫描（全市场突破检测）
    # ============================================================
    
    def scan_breakout_signals(self, close_matrix: np.ndarray,
                               vol_matrix: np.ndarray,
                               stock_codes: list,
                               scan_date_idx: int = -1) -> pd.DataFrame:
        """
        全市场突破信号扫描
        
        在GPU上同时扫描所有股票，找出满足条件的突破信号：
          1. 收盘价创MA20/MA60/MA120新高
          2. 成交量 > 20日均量的1.5倍
          3. MA20向上（斜率>0）
        
        参数:
            close_matrix: (n_stocks, n_days)
            vol_matrix:   (n_stocks, n_days)
            stock_codes:  股票代码列表
            scan_date_idx: 扫描哪一天（默认最后一天）
        
        返回: 满足条件的股票DataFrame
        """
        indicators = self.batch_compute_indicators(close_matrix, vol_matrix)
        
        idx = scan_date_idx
        n_stocks = close_matrix.shape[0]
        
        signals = []
        for i in range(n_stocks):
            code = stock_codes[i]
            
            # 跳过NaN
            if np.isnan(indicators['ma120'][i, idx]):
                continue
            
            # 条件检查
            break_ma20 = indicators['break_20d'][i, idx] == 1
            break_ma60 = indicators['break_60d'][i, idx] == 1
            break_ma120 = indicators['break_120d'][i, idx] == 1
            vol_amplified = indicators['vol_ratio'][i, idx] > 1.5 if not np.isnan(indicators['vol_ratio'][i, idx]) else False
            ma20_up = indicators['ma20_slope'][i, idx] > 0 if not np.isnan(indicators['ma20_slope'][i, idx]) else False
            
            if (break_ma20 or break_ma60 or break_ma120) and vol_amplified and ma20_up:
                level = 'MA120' if break_ma120 else ('MA60' if break_ma60 else 'MA20')
                signals.append({
                    'ts_code': code,
                    'breakout_level': level,
                    'close': close_matrix[i, idx],
                    'ma20': indicators['ma20'][i, idx],
                    'ma60': indicators['ma60'][i, idx],
                    'vol_ratio': round(indicators['vol_ratio'][i, idx], 2),
                    'ma20_slope': round(indicators['ma20_slope'][i, idx], 2),
                    'pct_chg': round(indicators['pct_chg'][i, idx], 2),
                })
        
        return pd.DataFrame(signals)
    
    # ============================================================
    # 工具方法
    # ============================================================
    
    def df_to_matrix(self, stock_data_dict: dict, column: str = 'close', 
                      align_dates: bool = True) -> tuple:
        """
        把多只股票的DataFrame转成GPU矩阵
        
        参数:
            stock_data_dict: {ts_code: DataFrame} 
                DataFrame需包含 'trade_date' 和指定column列
            column: 要提取的列名
            align_dates: 是否对齐交易日
        
        返回: (matrix, codes, dates)
            matrix: shape (n_stocks, n_days)
            codes: 股票代码列表
            dates: 交易日列表
        """
        codes = list(stock_data_dict.keys())
        
        if align_dates:
            # 找到所有股票共同的交易日
            all_dates = None
            for code, df in stock_data_dict.items():
                dates = set(df['trade_date'].values)
                all_dates = dates if all_dates is None else all_dates & dates
            all_dates = sorted(all_dates)
        
        n_stocks = len(codes)
        n_days = len(all_dates)
        matrix = np.full((n_stocks, n_days), np.nan, dtype=np.float32)
        
        for i, code in enumerate(codes):
            df = stock_data_dict[code]
            df = df[df['trade_date'].isin(all_dates)].sort_values('trade_date')
            if len(df) == n_days:
                matrix[i] = df[column].values.astype(np.float32)
        
        return matrix, codes, all_dates
    
    def gpu_info(self):
        """打印GPU信息"""
        if not HAS_TORCH or not torch.cuda.is_available():
            print("CUDA不可用")
            return
        
        print(f"PyTorch: {torch.__version__}")
        print(f"CUDA: {torch.version.cuda}")
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        props = torch.cuda.get_device_properties(0)
        print(f"显存: {props.total_mem / 1024**3:.1f} GB")
        print(f"CUDA核心: {props.multi_processor_count} SM")
        print(f"计算能力: {props.major}.{props.minor}")


# ============================================================
# 与回测脚本集成
# ============================================================

def precompute_all_indicators(cache_dir: str = 'backtest_cache',
                               output_file: str = 'backtest_results/gpu_indicators.parquet'):
    """
    预计算所有缓存股票的技术指标
    
    在回测前运行一次，把指标结果保存到本地
    回测时直接读取，不再重复计算
    """
    cache_path = Path(cache_dir)
    parquet_files = list(cache_path.glob('*.parquet'))
    
    if not parquet_files:
        print("没有找到缓存数据，请先运行回测下载数据")
        return
    
    print(f"加载 {len(parquet_files)} 只股票的缓存数据...")
    
    # 加载所有数据
    stock_data = {}
    for f in parquet_files:
        code = f.stem.replace('_', '.')
        df = pd.read_parquet(f)
        if len(df) >= 120:
            stock_data[code] = df
    
    print(f"有效股票: {len(stock_data)} 只")
    
    if len(stock_data) == 0:
        return
    
    # 初始化GPU引擎
    engine = GPUIndicatorEngine()
    
    # 转成矩阵
    print("构建数据矩阵...")
    close_matrix, codes, dates = engine.df_to_matrix(stock_data, 'close')
    vol_matrix, _, _ = engine.df_to_matrix(stock_data, 'vol')
    
    print(f"矩阵维度: {close_matrix.shape[0]} stocks × {close_matrix.shape[1]} days")
    
    # GPU批量计算
    print("GPU计算技术指标...")
    t0 = time.time()
    indicators = engine.batch_compute_indicators(close_matrix, vol_matrix)
    gpu_time = time.time() - t0
    print(f"GPU计算完成: {gpu_time:.2f}s")
    
    # 保存结果
    print(f"保存到 {output_file}...")
    # 每只股票每天一行，展开成长表
    rows = []
    for i, code in enumerate(codes):
        for j, date in enumerate(dates):
            row = {'ts_code': code, 'trade_date': date}
            for name, arr in indicators.items():
                row[name] = arr[i, j] if not np.isnan(arr[i, j]) else None
            rows.append(row)
    
    result_df = pd.DataFrame(rows)
    Path(output_file).parent.mkdir(exist_ok=True)
    result_df.to_parquet(output_file, index=False)
    print(f"保存完成: {len(result_df)} 行")
    
    return result_df


# ============================================================
# Benchmark: CPU vs GPU 速度对比
# ============================================================

def benchmark(n_stocks=200, n_days=500):
    """CPU vs GPU速度对比"""
    
    print(f"\n{'='*60}")
    print(f"Benchmark: {n_stocks}只股票 × {n_days}天")
    print(f"{'='*60}")
    
    # 生成模拟数据
    np.random.seed(42)
    close_matrix = np.cumsum(np.random.randn(n_stocks, n_days) * 0.02 + 0.001, axis=1) + 50
    close_matrix = close_matrix.astype(np.float32)
    vol_matrix = np.random.exponential(1e6, (n_stocks, n_days)).astype(np.float32)
    
    # ---- CPU (Pandas) ----
    print(f"\n[CPU] Pandas逐只计算...")
    t0 = time.time()
    
    for i in range(n_stocks):
        s = pd.Series(close_matrix[i])
        _ = s.rolling(5).mean()
        _ = s.rolling(10).mean()
        _ = s.rolling(20).mean()
        _ = s.rolling(60).mean()
        _ = s.rolling(120).mean()
        _ = s.rolling(20).max()
        _ = s.rolling(60).max()
        v = pd.Series(vol_matrix[i])
        _ = v.rolling(5).mean()
        _ = v.rolling(20).mean()
    
    cpu_time = time.time() - t0
    print(f"  CPU耗时: {cpu_time:.3f}s")
    
    # ---- GPU (PyTorch) ----
    if HAS_TORCH and torch.cuda.is_available():
        engine = GPUIndicatorEngine(device='cuda')
        
        # 预热
        _ = engine.batch_compute_indicators(close_matrix[:10], vol_matrix[:10])
        torch.cuda.synchronize()
        
        print(f"\n[GPU] PyTorch CUDA批量计算...")
        t0 = time.time()
        results = engine.batch_compute_indicators(close_matrix, vol_matrix)
        torch.cuda.synchronize()
        gpu_time = time.time() - t0
        print(f"  GPU耗时: {gpu_time:.3f}s")
        
        speedup = cpu_time / gpu_time
        print(f"\n  ★ GPU加速比: {speedup:.1f}x")
        print(f"  ★ CPU: {cpu_time:.3f}s → GPU: {gpu_time:.3f}s")
        
        # 验证结果一致性
        s = pd.Series(close_matrix[0])
        pd_ma20 = s.rolling(20).mean().values
        gpu_ma20 = results['ma20'][0]
        
        valid = ~np.isnan(pd_ma20) & ~np.isnan(gpu_ma20)
        max_diff = np.max(np.abs(pd_ma20[valid] - gpu_ma20[valid]))
        print(f"\n  结果验证: MA20最大误差 = {max_diff:.8f} ({'[一致]' if max_diff < 0.01 else '[有差异]'})")
    else:
        print("\n[GPU] CUDA不可用，跳过GPU测试")
        print("安装: pip install torch --index-url https://download.pytorch.org/whl/cu121")
    
    # ---- CPU多进程 (对比参考) ----
    print(f"\n[参考] 如果在回测中逐只计算:")
    per_stock = cpu_time / n_stocks
    print(f"  单只: {per_stock*1000:.1f}ms")
    print(f"  105只串行: {per_stock*105:.2f}s")
    print(f"  105只8进程: {per_stock*105/8:.2f}s")
    if HAS_TORCH and torch.cuda.is_available():
        print(f"  105只GPU批量: ~{gpu_time/n_stocks*105:.3f}s")


# ============================================================
# 主入口
# ============================================================

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='GPU加速模块')
    parser.add_argument('--benchmark', '-b', action='store_true', help='运行CPU vs GPU速度对比')
    parser.add_argument('--info', action='store_true', help='显示GPU信息')
    parser.add_argument('--precompute', action='store_true', help='预计算所有缓存股票的指标')
    parser.add_argument('--stocks', type=int, default=200, help='Benchmark股票数量')
    parser.add_argument('--days', type=int, default=500, help='Benchmark天数')
    args = parser.parse_args()
    
    if args.info:
        engine = GPUIndicatorEngine()
        engine.gpu_info()
    elif args.precompute:
        precompute_all_indicators()
    elif args.benchmark:
        benchmark(args.stocks, args.days)
    else:
        # 默认运行benchmark
        if HAS_TORCH:
            engine = GPUIndicatorEngine()
            engine.gpu_info()
        print()
        benchmark()