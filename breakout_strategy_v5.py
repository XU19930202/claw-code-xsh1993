"""
MA20突破回踩策略 v5 完整版
========================================
策略框架：突破扫描 → 信号入池 → 决策树追踪 → 持仓管理 → 二次上车

规则汇总（2026-03-19定稿）：

【入场规则】
1. 信号池：MA20放量突破
   - 收盘价 > MA20 且 前一日收盘价 <= MA20*1.02
   - 量比 >= 1.3
   - 涨幅 <= 8%（主板）/ 16%（创业板/科创板）
   - 排除ST

2. 追踪期：14天，等待企稳信号
   - 回踩确认：经历过下跌 + 不放量(<1.2) + 小阳(≤5%/10%)/十字星 + 站上MA20
   - 动能衰减：涨幅≤信号日1/3 + 不放量 + 站上MA20
   - 极度缩量企稳：量比<0.7 + 站上MA20（不管阴阳）

3. 追踪期过滤
   - 放量下跌但未破MA20 → 观察，不放弃（had_decline=True）
   - 放量跌破MA20 → 放弃
   - 连续2天收盘破MA20 → 放弃
   - 大盘(上证)跌>1% → 当日冻结

【出场规则】
阶段1 - MA20阶段（趋势未确立）：
   - 四条件同时满足才走：放量(≥1.2) + 下跌 + 破MA20 + 大盘正常(跌<1%)
   - 缩量破MA20 → 洗盘，不走
   - 放量跌但大盘大跌 → 系统风险，不走
   - 放量但上涨/收复中 → 不走
   - 大跌但未放量 → 情绪波动，不走

阶段切换 - 多头确立：
   - MA5 > MA20 × 1.03 且连续维持3天以上
   - 切换到MA5阶段

阶段2 - MA5阶段（多头确立）：
   - 连续2天收盘低于MA5 且 收阴 → 清仓
   - 破MA5但收阳 → 不计数（在努力收复）
   - 高开低走且收盘<MA5 → 清仓
   - MA5跌破MA20 → 回退MA20阶段

【例外规则】
   - 跌停熔断：持仓期间有过涨停，之后出现跌停 → 立即清仓
     * 主板：涨停≥9.5%，跌停≤-9.5%
     * 创业板/科创板：涨停≥19.5%，跌停≤-19.5%

【二次上车】
   - MA5止损卖出后，观察30天
   - 如果股价始终未跌破MA20，且重新站上MA5 → 直接买回
   - 如果期间跌破MA20 → 取消观察

【板块适配】
   - 主板(60xxxx, 00xxxx, 001xxx)：涨跌停±10%，信号涨幅上限8%，小阳≤5%
   - 创业板(300xxx)：涨跌停±20%，信号涨幅上限16%，小阳≤10%
   - 科创板(688xxx)：涨跌停±20%，信号涨幅上限16%，小阳≤10%

【价格使用】
   - 统一使用前复权价格计算MA和买卖点
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict


# ============================================================
#  配置参数
# ============================================================
@dataclass
class BoardConfig:
    """板块参数配置"""
    name: str
    limit_up: float       # 涨停判定阈值
    limit_down: float     # 跌停判定阈值
    signal_max_pct: float # 入池涨幅上限
    small_yang_max: float # 小阳线上限

BOARD_CONFIGS = {
    'main':  BoardConfig('主板', 9.5, -9.5, 8.0, 5.0),
    'gem':   BoardConfig('创业板', 19.5, -19.5, 16.0, 10.0),
    'star':  BoardConfig('科创板', 19.5, -19.5, 16.0, 10.0),
}

@dataclass
class StrategyConfig:
    """策略全局参数"""
    vol_min: float = 1.3          # 入池最低量比
    track_days: int = 14          # 追踪期天数
    trend_gap: float = 1.03       # 多头确立：MA5/MA20比值
    trend_days: int = 3           # 多头确立：连续天数
    extreme_shrink: float = 0.7   # 极度缩量阈值
    vol_up_threshold: float = 1.2 # 放量阈值
    ma20_tolerance: float = 0.985 # MA20容差（允许1.5%的误差）
    reentry_window: int = 30      # 二次上车观察窗口
    max_hold_days: int = 60       # 最大持仓天数


def detect_board(code: str) -> BoardConfig:
    """根据股票代码判断板块"""
    if code.startswith('300') or code.startswith('301'):
        return BOARD_CONFIGS['gem']
    elif code.startswith('688') or code.startswith('689'):
        return BOARD_CONFIGS['star']
    else:
        return BOARD_CONFIGS['main']


# ============================================================
#  数据准备
# ============================================================
def prepare_data(stock_df: pd.DataFrame, index_df: Optional[pd.DataFrame] = None) -> Tuple[pd.DataFrame, Dict]:
    """
    准备股票数据和大盘涨跌幅映射
    
    Args:
        stock_df: 股票行情DataFrame，需包含：交易日期, 收盘价(元), 收盘价(前复权)(元),
                  开盘价(元), 最高价(元), 最低价(元), 涨跌幅(%), 成交量(万股)
        index_df: 上证指数DataFrame（可选），需包含：交易日期, 涨跌幅(%)
    
    Returns:
        (处理后的stock_df, 大盘涨跌幅字典)
    """
    stock = stock_df.copy()
    stock = stock.dropna(subset=['交易日期'])
    stock = stock[~stock['交易日期'].astype(str).str.contains('数据来源')]
    stock = stock.sort_values('交易日期').reset_index(drop=True)
    
    # 前复权处理
    adj_diff = stock[stock['收盘价(元)'] != stock['收盘价(前复权)(元)']].dropna(
        subset=['收盘价(元)', '收盘价(前复权)(元)'])
    
    if len(adj_diff) > 0:
        adj_ratio = stock['收盘价(前复权)(元)'] / stock['收盘价(元)']
        stock['close'] = stock['收盘价(前复权)(元)']
        stock['open'] = stock['开盘价(元)'] * adj_ratio
        stock['high'] = stock['最高价(元)'] * adj_ratio
        stock['low'] = stock['最低价(元)'] * adj_ratio
    else:
        stock['close'] = stock['收盘价(元)']
        stock['open'] = stock['开盘价(元)']
        stock['high'] = stock['最高价(元)']
        stock['low'] = stock['最低价(元)']
    
    stock['pct'] = stock['涨跌幅(%)']
    stock['MA5'] = stock['close'].rolling(5).mean()
    stock['MA20'] = stock['close'].rolling(20).mean()
    stock['vol_ma5'] = stock['成交量(万股)'].rolling(5).mean()
    stock['vol_ratio'] = stock['成交量(万股)'] / stock['vol_ma5']
    
    # 大盘数据
    idx_map = {}
    if index_df is not None:
        idx = index_df.copy()
        idx = idx.dropna(subset=['交易日期'])
        idx = idx[~idx['交易日期'].astype(str).str.contains('数据来源')]
        idx = idx.sort_values('交易日期').reset_index(drop=True)
        idx_map = dict(zip(idx['交易日期'].astype(str).str[:10], idx['涨跌幅(%)']))
    
    return stock, idx_map


# ============================================================
#  信号扫描
# ============================================================
def scan_signals(stock: pd.DataFrame, cfg: StrategyConfig, board: BoardConfig) -> List[int]:
    """
    扫描MA20放量突破信号
    
    Returns:
        信号日的index列表
    """
    signals = []
    for i in range(21, len(stock)):
        row = stock.iloc[i]
        prev = stock.iloc[i - 1]
        ma20 = row['MA20']
        prev_ma20 = prev['MA20']
        vr = row['vol_ratio']
        
        if pd.isna(ma20) or pd.isna(vr):
            continue
        
        # 突破条件：今日收盘 > MA20，前日收盘 <= MA20*1.02
        # 量比 >= 门槛，涨幅 <= 板块上限
        if (row['close'] > ma20
                and prev['close'] <= prev_ma20 * 1.02
                and vr >= cfg.vol_min
                and row['pct'] <= board.signal_max_pct):
            signals.append(i)
    
    return signals


# ============================================================
#  入场决策树
# ============================================================
@dataclass
class EntryResult:
    """入场结果"""
    triggered: bool = False
    buy_idx: Optional[int] = None
    buy_price: Optional[float] = None
    buy_date: Optional[str] = None
    buy_type: Optional[str] = None
    log: List[str] = field(default_factory=list)


def run_entry(stock: pd.DataFrame, signal_idx: int, idx_map: Dict,
              cfg: StrategyConfig, board: BoardConfig,
              last_exit_idx: int = -1) -> EntryResult:
    """
    从信号日开始，追踪14天寻找买点
    """
    result = EntryResult()
    row = stock.iloc[signal_idx]
    signal_pct = row['pct']
    ma20 = row['MA20']
    had_decline = False
    
    for j in range(signal_idx + 1, min(signal_idx + cfg.track_days + 1, len(stock))):
        if j <= last_exit_idx:
            continue
        
        r = stock.iloc[j]
        d = str(r['交易日期'])[:10]
        m20 = r['MA20'] if pd.notna(r['MA20']) else ma20
        v = r['vol_ratio'] if pd.notna(r['vol_ratio']) else 1.0
        pct = r['pct']
        close = r['close']
        opn = r['open']
        above = close >= m20 * cfg.ma20_tolerance
        day_n = j - signal_idx
        
        body = abs(close - opn) / close if close > 0 else 0
        not_vol_up = v < cfg.vol_up_threshold
        is_small_yang = 0 < pct <= board.small_yang_max
        is_doji = body < 0.005
        extreme_shrink = v < cfg.extreme_shrink
        
        if pct < -0.3:
            had_decline = True
        momentum_decay = (0 <= pct <= signal_pct / 3) if signal_pct > 0 else False
        stabilized = had_decline or momentum_decay
        
        # === 放量下跌判断 ===
        if v >= cfg.vol_up_threshold and pct < 0:
            if not above:
                result.log.append(
                    f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x | ❌ 放量跌破MA20")
                break
            else:
                result.log.append(
                    f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x | ⚠️ 放量跌未破MA20")
                had_decline = True
                continue
        
        # === 破MA20判断 ===
        if not above:
            if j > signal_idx + 1:
                prev_above = stock.iloc[j - 1]['close'] >= (
                    stock.iloc[j - 1]['MA20'] if pd.notna(stock.iloc[j - 1]['MA20']) else 0
                ) * cfg.ma20_tolerance
                if not prev_above:
                    result.log.append(
                        f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x | ❌ 连续破MA20")
                    break
            result.log.append(
                f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x | ⚠️ 破MA20")
            continue
        
        # === 大盘过滤 ===
        mkt = idx_map.get(d, 0)
        
        # === 极度缩量企稳（量比<0.7，不管阴阳）===
        if above and extreme_shrink and stabilized:
            if mkt <= -1.0:
                result.log.append(
                    f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x | 🛑 大盘跌{mkt:.2f}%")
                continue
            result.triggered = True
            result.buy_idx = j
            result.buy_price = close
            result.buy_date = d
            result.buy_type = '极度缩量企稳'
            result.log.append(
                f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x | ✅ 极度缩量企稳(Day{day_n})")
            break
        
        # === 回踩确认 / 动能衰减 ===
        if above and not_vol_up and (is_small_yang or is_doji) and stabilized:
            if mkt <= -1.0:
                result.log.append(
                    f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x | 🛑 大盘跌{mkt:.2f}%")
                continue
            reason = '动能衰减' if (momentum_decay and not had_decline) else '回踩确认'
            result.triggered = True
            result.buy_idx = j
            result.buy_price = close
            result.buy_date = d
            result.buy_type = reason
            result.log.append(
                f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x | ✅ {reason}(Day{day_n})")
            break
        
        # === 等待状态 ===
        if pct > 5:
            result.log.append(
                f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x | ⏳ 过热")
        elif pct > 0 and v >= cfg.vol_up_threshold:
            result.log.append(
                f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x | ⏳ 放量上涨")
        elif pct > 0 and not stabilized:
            result.log.append(
                f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x | ⏳ 未企稳")
        else:
            result.log.append(
                f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x | ⏳ 等企稳")
    
    return result


# ============================================================
#  出场决策树
# ============================================================
@dataclass
class ExitResult:
    """出场结果"""
    exit_idx: Optional[int] = None
    exit_price: Optional[float] = None
    exit_date: Optional[str] = None
    exit_reason: Optional[str] = None
    exit_type: str = ''   # 'ma5', 'ma20', 'limit_down', 'end'
    max_pnl: float = 0.0
    log: List[str] = field(default_factory=list)


def run_exit(stock: pd.DataFrame, buy_idx: int, buy_price: float,
             idx_map: Dict, cfg: StrategyConfig, board: BoardConfig) -> ExitResult:
    """
    从买入日开始，执行出场逻辑
    """
    result = ExitResult()
    phase = 'MA20'
    below_ma5_count = 0
    gap_streak = 0
    had_limit_up = False
    
    for k in range(buy_idx + 1, min(buy_idx + cfg.max_hold_days, len(stock))):
        r = stock.iloc[k]
        d = str(r['交易日期'])[:10]
        m5 = r['MA5'] if pd.notna(r['MA5']) else 0
        m20 = r['MA20'] if pd.notna(r['MA20']) else 0
        v = r['vol_ratio'] if pd.notna(r['vol_ratio']) else 1.0
        pct = r['pct']
        close = r['close']
        opn = r['open']
        high = r['high']
        pnl = (close - buy_price) / buy_price * 100
        above_ma5 = close >= m5
        above_ma20 = close >= m20
        gap = (m5 / m20 - 1) * 100 if m20 > 0 else 0
        mkt = idx_map.get(d, 0)
        below_ma5_close = close < m5 if m5 > 0 else False
        high_open_low_close = (opn >= high * 0.998) and (close < opn)
        is_up_day = pct > 0
        
        if pnl > result.max_pnl:
            result.max_pnl = pnl
        
        # ============ 例外规则：跌停熔断 ============
        if pct >= board.limit_up:
            had_limit_up = True
        if had_limit_up and pct <= board.limit_down:
            result.exit_idx = k
            result.exit_price = close
            result.exit_date = d
            result.exit_reason = '跌停熔断'
            result.exit_type = 'limit_down'
            result.log.append(f"  {d} | {close:.2f} {pct:+.2f}% | +{pnl:.1f}% | 🚨 跌停熔断")
            return result
        
        # ============ 多头确立判定 ============
        if m5 > m20 * cfg.trend_gap:
            gap_streak += 1
        else:
            gap_streak = 0
        
        if phase == 'MA20' and gap_streak >= cfg.trend_days and above_ma5:
            phase = 'MA5'
            below_ma5_count = 0
            result.log.append(
                f"  {d} | {close:.2f} {pct:+.2f}% 差距{gap:+.1f}%(连续{gap_streak}天) "
                f"| +{pnl:.1f}% | 🔄 多头确立")
        
        # MA5回退MA20
        if phase == 'MA5' and m5 < m20:
            phase = 'MA20'
            below_ma5_count = 0
            gap_streak = 0
            result.log.append(
                f"  {d} | {close:.2f} {pct:+.2f}% | +{pnl:.1f}% | 🔄 回退MA20")
        
        # ============ MA5阶段出场 ============
        if phase == 'MA5':
            # 高开低走且收盘<MA5
            if below_ma5_close and high_open_low_close:
                result.exit_idx = k
                result.exit_price = close
                result.exit_date = d
                result.exit_reason = '高开低走且破MA5'
                result.exit_type = 'ma5'
                result.log.append(
                    f"  {d} | {close:.2f} 开{opn:.2f} ✗MA5({m5:.2f}) "
                    f"| +{pnl:.1f}% | ❌ 高开低走且破MA5")
                return result
            
            if not above_ma5:
                if is_up_day:
                    # ★ 破MA5但收阳 → 在努力收复，不计数
                    result.log.append(
                        f"  {d} | {close:.2f} {pct:+.2f}% ✗MA5({m5:.2f}) "
                        f"| +{pnl:.1f}% | ✅ 破MA5但收阳，不计数")
                    below_ma5_count = 0
                else:
                    below_ma5_count += 1
                    if below_ma5_count >= 2:
                        result.exit_idx = k
                        result.exit_price = close
                        result.exit_date = d
                        result.exit_reason = '连续2天破MA5且收阴'
                        result.exit_type = 'ma5'
                        result.log.append(
                            f"  {d} | {close:.2f} {pct:+.2f}% ✗MA5({m5:.2f}) "
                            f"| +{pnl:.1f}% | ❌ 连续2天破MA5且收阴")
                        return result
                    else:
                        result.log.append(
                            f"  {d} | {close:.2f} {pct:+.2f}% ✗MA5({m5:.2f}) "
                            f"| +{pnl:.1f}% | ⚠️ 破MA5+收阴 第{below_ma5_count}天")
            else:
                if below_ma5_count > 0:
                    result.log.append(
                        f"  {d} | {close:.2f} {pct:+.2f}% ✓MA5 | +{pnl:.1f}% | ✅ 站回MA5")
                below_ma5_count = 0
                if abs(pct) > 2:
                    result.log.append(
                        f"  {d} | {close:.2f} {pct:+.2f}% ✓MA5 差距{gap:+.1f}% "
                        f"| +{pnl:.1f}% | 持有{'🔥' if had_limit_up else ''}")
        
        # ============ MA20阶段出场 ============
        elif phase == 'MA20':
            if not above_ma20:
                if v >= cfg.vol_up_threshold and pct < 0 and mkt > -1.0:
                    result.exit_idx = k
                    result.exit_price = close
                    result.exit_date = d
                    result.exit_reason = '放量+下跌+破MA20+大盘正常'
                    result.exit_type = 'ma20'
                    result.log.append(
                        f"  {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x ✗MA20 "
                        f"| +{pnl:.1f}% | ❌ 放量+下跌+破MA20+大盘正常")
                    return result
                elif v >= cfg.vol_up_threshold and pct < 0 and mkt <= -1.0:
                    result.log.append(
                        f"  {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x ✗MA20 "
                        f"| +{pnl:.1f}% | ⚠️ 放量跌但大盘大跌")
                elif v >= cfg.vol_up_threshold and pct >= 0:
                    result.log.append(
                        f"  {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x ✗MA20 "
                        f"| +{pnl:.1f}% | ✅ 放量收复中")
                elif v <= 0.85:
                    result.log.append(
                        f"  {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x ✗MA20 "
                        f"| +{pnl:.1f}% | ✅ 缩量洗盘")
                elif pct < -5:
                    result.log.append(
                        f"  {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x ✗MA20 "
                        f"| +{pnl:.1f}% | ✅ 大跌但未放量")
                else:
                    result.log.append(
                        f"  {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x ✗MA20 "
                        f"| +{pnl:.1f}% | ⚠️ 观察")
            else:
                if abs(pct) > 2 or gap > 2:
                    result.log.append(
                        f"  {d} | {close:.2f} {pct:+.2f}% ✓MA20 差距{gap:+.1f}%"
                        f"(连续{gap_streak}天) | +{pnl:.1f}% | MA20持有")
    
    # 60天未触发出场 → 数据末尾
    if result.exit_idx is None:
        last_k = min(buy_idx + cfg.max_hold_days - 1, len(stock) - 1)
        result.exit_idx = last_k
        result.exit_price = stock.iloc[last_k]['close']
        result.exit_date = str(stock.iloc[last_k]['交易日期'])[:10]
        result.exit_reason = '数据末尾'
        result.exit_type = 'end'
    
    return result


# ============================================================
#  二次上车检查
# ============================================================
@dataclass
class ReentryResult:
    """二次上车结果"""
    triggered: bool = False
    reentry_idx: Optional[int] = None
    reentry_price: Optional[float] = None
    reentry_date: Optional[str] = None
    log: List[str] = field(default_factory=list)


def check_reentry(stock: pd.DataFrame, exit_idx: int, cfg: StrategyConfig) -> ReentryResult:
    """
    MA5止损后，检查是否满足二次上车条件
    """
    result = ReentryResult()
    
    for k in range(exit_idx + 1, min(exit_idx + cfg.reentry_window, len(stock))):
        r = stock.iloc[k]
        d = str(r['交易日期'])[:10]
        m5 = r['MA5'] if pd.notna(r['MA5']) else 0
        m20 = r['MA20'] if pd.notna(r['MA20']) else 0
        close = r['close']
        
        # 跌破MA20 → 趋势结束，取消观察
        if close < m20:
            result.log.append(f"  {d} | {close:.2f} ✗MA20({m20:.2f}) | 破MA20，取消观察")
            return result
        
        # 站回MA5 → 触发二次上车
        if close >= m5:
            result.triggered = True
            result.reentry_idx = k
            result.reentry_price = close
            result.reentry_date = d
            result.log.append(
                f"  {d} | {close:.2f} ✓MA5({m5:.2f}) ✓MA20({m20:.2f}) | ✅ 二次上车!")
            return result
        
        result.log.append(
            f"  {d} | {close:.2f} ✗MA5({m5:.2f}) ✓MA20({m20:.2f}) | 等待站回MA5")
    
    return result


# ============================================================
#  完整回测引擎
# ============================================================
@dataclass
class Trade:
    """交易记录"""
    n: int
    signal_date: str
    buy_date: str
    buy_price: float
    exit_date: str
    exit_price: float
    pnl: float
    max_pnl: float
    days: int
    trade_type: str


def backtest(stock_df: pd.DataFrame, code: str,
             index_df: Optional[pd.DataFrame] = None,
             verbose: bool = True) -> List[Trade]:
    """
    完整回测入口
    
    Args:
        stock_df: 股票原始数据
        code: 股票代码（如 '300308'）
        index_df: 上证指数数据（可选）
        verbose: 是否打印详细日志
    
    Returns:
        交易记录列表
    """
    cfg = StrategyConfig()
    board = detect_board(code)
    stock, idx_map = prepare_data(stock_df, index_df)
    
    if verbose:
        print(f"{'=' * 85}")
        print(f"  {code} 回测 | {board.name} | 涨跌停±{board.limit_up:.0f}%")
        print(f"  股价: {stock['close'].iloc[0]:.2f} → {stock['close'].iloc[-1]:.2f} "
              f"({(stock['close'].iloc[-1] / stock['close'].iloc[0] - 1) * 100:+.0f}%)")
        print(f"{'=' * 85}")
    
    # 扫描信号
    all_signals = scan_signals(stock, cfg, board)
    if verbose:
        print(f"\n信号池: {len(all_signals)}个")
        for si in all_signals:
            r = stock.iloc[si]
            print(f"  {str(r['交易日期'])[:10]} | {r['close']:.2f} "
                  f"涨{r['pct']:+.1f}% 量比{r['vol_ratio']:.2f}x")
    
    trades = []
    last_exit_idx = -1
    
    for si in all_signals:
        if si <= last_exit_idx:
            continue
        
        signal_date = str(stock.iloc[si]['交易日期'])[:10]
        
        # === 入场 ===
        entry = run_entry(stock, si, idx_map, cfg, board, last_exit_idx)
        
        if not entry.triggered:
            if verbose:
                status = '放弃' if any('❌' in l for l in entry.log) else '期满'
                r = stock.iloc[si]
                print(f"\n{'🔴' if '放弃' in status else '⚪'} {signal_date} | "
                      f"{r['close']:.2f} 涨{r['pct']:+.1f}% | {status}")
                for l in entry.log:
                    print(l)
            continue
        
        # === 交易循环（含二次上车）===
        cur_buy_idx = entry.buy_idx
        cur_buy_price = entry.buy_price
        cur_buy_date = entry.buy_date
        cur_buy_type = entry.buy_type
        cur_entry_log = entry.log
        
        while True:
            # 执行出场
            exit_result = run_exit(stock, cur_buy_idx, cur_buy_price, idx_map, cfg, board)
            
            total_pnl = (exit_result.exit_price - cur_buy_price) / cur_buy_price * 100
            days = exit_result.exit_idx - cur_buy_idx if exit_result.exit_idx else 0
            
            trade = Trade(
                n=len(trades) + 1,
                signal_date=signal_date,
                buy_date=cur_buy_date,
                buy_price=cur_buy_price,
                exit_date=exit_result.exit_date,
                exit_price=exit_result.exit_price,
                pnl=total_pnl,
                max_pnl=exit_result.max_pnl,
                days=days,
                trade_type=cur_buy_type,
            )
            trades.append(trade)
            
            if verbose:
                icon = '🟢' if total_pnl > 0 else '🔴'
                print(f"\n{icon} 第{trade.n}笔 信号:{signal_date} | {cur_buy_type}")
                if '上车' in cur_buy_type:
                    print(f"  MA5止损后未破MA20，重新站上MA5 → 买回")
                else:
                    for l in cur_entry_log:
                        print(l)
                print(f"  买入: {cur_buy_date} @ {cur_buy_price:.2f} ({cur_buy_type})")
                for l in exit_result.log:
                    print(l)
                print(f"  退出: {exit_result.exit_date} @ {exit_result.exit_price:.2f} "
                      f"| {exit_result.exit_reason}")
                print(f"  收益: {total_pnl:+.2f}% | 最高浮盈: {exit_result.max_pnl:+.2f}% "
                      f"| 持有{days}天")
            
            if exit_result.exit_idx:
                last_exit_idx = exit_result.exit_idx
            
            # === 二次上车检查 ===
            if exit_result.exit_type != 'ma5' or not exit_result.exit_idx:
                break
            
            reentry = check_reentry(stock, exit_result.exit_idx, cfg)
            
            if verbose and reentry.log:
                print(f"\n  --- 二次上车观察 ---")
                for l in reentry.log:
                    print(l)
            
            if reentry.triggered:
                cur_buy_idx = reentry.reentry_idx
                cur_buy_price = reentry.reentry_price
                cur_buy_date = reentry.reentry_date
                n_re = sum(1 for t in trades if t.signal_date == signal_date)
                labels = ['二次上车', '三次上车', '四次上车']
                cur_buy_type = labels[min(n_re - 1, len(labels) - 1)]
                cur_entry_log = []
                continue
            else:
                break
    
    return trades


# ============================================================
#  结果汇总
# ============================================================
def print_summary(trades: List[Trade], initial_capital: float = 200000):
    """打印回测结果汇总"""
    if not trades:
        print("  无交易")
        return
    
    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    
    print(f"\n{'=' * 85}")
    print(f"  回测结果汇总")
    print(f"{'=' * 85}")
    print(f"\n  交易: {len(trades)}笔 | 胜率: {len(wins)}/{len(trades)} "
          f"= {len(wins) / len(trades) * 100:.0f}%")
    if wins:
        print(f"  均盈: {np.mean(wins):+.2f}%")
    if losses:
        print(f"  均亏: {np.mean(losses):+.2f}%")
    if wins and losses:
        print(f"  盈亏比: {abs(np.mean(wins) / np.mean(losses)):.2f}")
    
    capital = initial_capital
    print(f"\n  复利计算({initial_capital / 10000:.0f}万本金):")
    print(f"  {'笔':>3s} | {'类型':>8s} | {'买入日':>12s} | {'买价':>7s} | "
          f"{'卖出日':>12s} | {'卖价':>7s} | {'收益':>8s} | {'资金':>10s}")
    print(f"  {'-' * 85}")
    
    for t in trades:
        capital = capital * (1 + t.pnl / 100)
        icon = '🟢' if t.pnl > 0 else '🔴'
        print(f"  {icon}{t.n:>2d} | {t.trade_type:>8s} | {t.buy_date:>12s} | "
              f"{t.buy_price:>7.2f} | {t.exit_date:>12s} | {t.exit_price:>7.2f} | "
              f"{t.pnl:>+7.2f}% | {capital / 10000:>9.2f}万")
    
    print(f"  {'-' * 85}")
    print(f"  最终: {capital / 10000:.2f}万 | "
          f"总收益: {(capital / initial_capital - 1) * 100:+.2f}% | "
          f"净赚: {(capital - initial_capital) / 10000:.2f}万")


# ============================================================
#  主函数
# ============================================================
if __name__ == '__main__':
    import sys
    
    # 使用示例
    print("=" * 85)
    print("  MA20突破回踩策略 v5")
    print("  用法: 修改下方文件路径，运行即可")
    print("=" * 85)
    
    # ---- 修改这里的文件路径 ----
    stock_file = '/mnt/user-data/uploads/每日行情数据统计_601689.xlsx'
    index_file = '/mnt/user-data/uploads/000001_SH行情数据统计明细.xlsx'
    code = '601689'
    # ----------------------------
    
    stock_df = pd.read_excel(stock_file)
    index_df = pd.read_excel(index_file)
    
    trades = backtest(stock_df, code, index_df, verbose=True)
    print_summary(trades)
