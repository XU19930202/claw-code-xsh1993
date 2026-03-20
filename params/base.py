"""
板块参数基础模块
- BoardParams 数据类
- 通用工具函数（条件判断）
- 流动性分档逻辑
"""

from dataclasses import dataclass
from typing import Optional
import pandas as pd


# ============================================================
# 流动性分档
# ============================================================

def classify_liquidity(avg_turnover_120d: float) -> str:
    """
    根据120日均换手率划分流动性等级
    
    Args:
        avg_turnover_120d: 120日平均换手率(%)
    
    Returns:
        'high' / 'medium' / 'low'
    """
    if avg_turnover_120d >= 5.0:
        return 'high'
    elif avg_turnover_120d >= 2.0:
        return 'medium'
    else:
        return 'low'


def liquidity_scale(avg_turnover_120d: float,
                    low_val: float, mid_val: float, high_val: float) -> float:
    """
    根据流动性线性插值参数值
    
    低流动性 → low_val
    中流动性 → mid_val  (基准)
    高流动性 → high_val
    
    在分界点之间做线性插值，避免硬跳变
    """
    if avg_turnover_120d <= 0.5:
        return low_val
    elif avg_turnover_120d <= 2.0:
        # 0.5~2.0 之间: low → mid 插值
        t = (avg_turnover_120d - 0.5) / 1.5
        return low_val + (mid_val - low_val) * t
    elif avg_turnover_120d <= 5.0:
        # 2.0~5.0 之间: mid (基准值)
        return mid_val
    elif avg_turnover_120d <= 10.0:
        # 5.0~10.0 之间: mid → high 插值
        t = (avg_turnover_120d - 5.0) / 5.0
        return mid_val + (high_val - mid_val) * t
    else:
        return high_val


# ============================================================
# 参数数据类
# ============================================================

@dataclass
class BoardParams:
    """板块参数配置"""
    board_name: str             # 板块名称
    board_code: str             # 板块代码 (main/star/gem/main_st/star_st/gem_st)
    liquidity: str              # 流动性等级 (high/medium/low)
    avg_turnover_120d: float    # 120日均换手率(%)

    # --- 涨跌幅限制 ---
    limit_pct: float            # 涨跌停幅度 (5/10/20)
    limit_up: float             # 涨停判定阈值
    limit_down: float           # 跌停判定阈值

    # --- Mode A: 突破信号 ---
    signal_vol_ratio: float     # 放量突破: 量比阈值
    signal_turnover: float      # 放量突破: 换手率阈值 (ST股)
    signal_max_pct: float       # 突破日最大涨幅
    use_turnover: bool          # True=用换手率, False=用量比

    # --- Mode A: 趋势中的放量阈值 (分档) ---
    signal_vol_ratio_trend: float
    signal_turnover_trend: float

    # --- 追踪期 ---
    track_days: int

    # --- 动能衰减 (had_decline) ---
    decline_pct: float          # 下跌阈值
    decay_ratio: float          # 涨幅收窄比例
    decay_vol_ratio: float      # 收窄时量比要求
    decay_turnover: float       # 收窄时换手率要求

    # --- 极度缩量企稳 ---
    shrink_vol_ratio: float
    shrink_turnover: float
    shrink_turnover_trend: float

    # --- 止损/退出 ---
    stop_loss_pct: float
    mode_b_ma20_days: int
    ma20_cum_loss_limit: float

    # --- Mode B: 趋势回踩 ---
    pullback_range: float
    pullback_vol_ratio: float
    pullback_turnover: float

    # --- 趋势强度过滤 ---
    ma20_slope_min: float

    # --- MA20容忍度 ---
    ma20_tolerance: float

    # --- 其他 ---
    small_yang_max: float
    trend_gap: float
    trend_days: int
    reentry_window: int
    allow_re_entry: bool
    max_hold_days: int
    strict_ma20_stop_window: int
    strict_signal_window: int
    max_drawdown_from_peak: float
    ma20_slope_filter: float
    shrink_need_stabilized: bool = True  # 极度缩量企稳是否需要stabilized前提
    
    # --- 动态止损均线切换 (浮盈分级保护) ---
    profit_tier_1: float = 10.0    # 浮盈<10%: 标准MA5止损(连续2天)
    profit_tier_2: float = 20.0    # 浮盈10-20%: 放宽MA5止损(连续4天)
    # 浮盈>20%: 跳过MA5,回退到MA20止损 + 浮盈回撤止盈双重保护


# ============================================================
# 通用工具函数
# ============================================================

def check_breakout_volume(p: BoardParams, vol_ratio: float, turnover: float,
                          in_trend: bool = False) -> bool:
    """判断突破日是否满足放量条件"""
    if p.use_turnover:
        threshold = p.signal_turnover_trend if in_trend else p.signal_turnover
        return turnover >= threshold
    else:
        threshold = p.signal_vol_ratio_trend if in_trend else p.signal_vol_ratio
        return vol_ratio >= threshold


def check_had_decline(p: BoardParams, pct: float, signal_pct: float,
                      vol_ratio: float, turnover: float) -> bool:
    """判断是否满足动能衰减条件"""
    if pct < p.decline_pct:
        return True
    pct_shrink = pct < signal_pct * p.decay_ratio
    if p.use_turnover:
        vol_shrink = turnover < p.decay_turnover
    else:
        vol_shrink = vol_ratio < p.decay_vol_ratio
    return pct_shrink and vol_shrink


def check_extreme_shrink(p: BoardParams, vol_ratio: float, turnover: float,
                         in_trend: bool = False) -> bool:
    """判断是否满足极度缩量企稳条件"""
    if p.use_turnover:
        threshold = p.shrink_turnover_trend if in_trend else p.shrink_turnover
        return turnover < threshold
    else:
        return vol_ratio < p.shrink_vol_ratio


def check_stop_loss(p: BoardParams, entry_mode: str,
                    cumulative_pct: float, days_below_ma20: int) -> bool:
    """判断是否触发止损"""
    if entry_mode == 'trend_pullback':
        return days_below_ma20 >= p.mode_b_ma20_days
    else:
        return cumulative_pct <= p.stop_loss_pct


def check_trend_pullback(p: BoardParams, close: float, ma20: float,
                         ma60: float, ma20_20d_ago: float,
                         vol_ratio: float, turnover: float) -> bool:
    """判断是否满足Mode B趋势回踩买入条件"""
    if ma20 is None or ma60 is None or ma20_20d_ago is None:
        return False
    if ma20 <= ma60:
        return False
    if ma20 <= ma20_20d_ago:
        return False
    slope = (ma20 - ma20_20d_ago) / ma20_20d_ago
    if slope < p.ma20_slope_min:
        return False
    if close < ma20 * 0.95:
        return False
    if close > ma20 * (1 + p.pullback_range):
        return False
    if p.use_turnover:
        return turnover < p.pullback_turnover
    else:
        return vol_ratio < p.pullback_vol_ratio


def check_above_ma20(p: BoardParams, close: float, ma20: float) -> bool:
    """判断是否站上MA20"""
    if ma20 is None or ma20 == 0:
        return False
    return close >= ma20 * p.ma20_tolerance
