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

4. 严格模式（趋势不明时收紧入场条件）
   - 30天内有过MA20止损 → 只接受极度缩量企稳，不接受回踩确认/动能衰减
   - 7天内出现≥2个信号 → 只接受极度缩量企稳（MA20附近反复穿越，突破不干脆）

【出场规则】
阶段1 - MA20阶段（趋势未确立）：
   - 四条件同时满足才走：放量(≥1.2) + 下跌 + 破MA20 + 大盘正常(跌<1%)
   - 缩量阴跌累计止损：跌破MA20后累计跌幅超过3% → 直接走（防温水煮青蛙）
   - 缩量破MA20 → 洗盘，不走
   - 放量跌但大盘大跌 → 系统风险，不走
   - 放量但上涨/收复中 → 不走
   - 大跌但未放量 → 情绪波动，不走
   - 站回MA20 → 累计跌幅清零

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

# 从params包导入参数配置
from params import get_board_type, get_params as get_params_from_package
from params.base import (
    check_breakout_volume,
    check_had_decline,
    check_extreme_shrink,
    check_stop_loss,
    check_trend_pullback,
    check_above_ma20,
)


# ============================================================
#  板块参数体系 - 三板适配 (ST股±5%, 主板±10%, 科创板/创业板±20%)
#  注意: 同时支持从params包获取参数
# ============================================================

@dataclass
class BoardParams:
    """板块参数配置 - 完整版"""
    board_name: str             # 板块名称

    # --- 涨跌幅限制 ---
    limit_pct: float            # 涨跌停幅度 (5/10/20)
    limit_up: float             # 涨停判定阈值
    limit_down: float           # 跌停判定阈值

    # --- Mode A: 突破信号 ---
    signal_vol_ratio: float     # 放量突破: 量比阈值 (主板/科创板)
    signal_turnover: float      # 放量突破: 换手率阈值 (ST股)
    signal_max_pct: float       # 突破日最大涨幅 (过滤一字板)
    use_turnover: bool          # True=用换手率判断, False=用量比判断

    # --- Mode A: 趋势中的放量阈值 (分档) ---
    signal_vol_ratio_trend: float   # 趋势中量比阈值 (主板/科创板)
    signal_turnover_trend: float    # 趋势中换手率阈值 (ST股)

    # --- 追踪期 ---
    track_days: int             # 信号后追踪天数

    # --- 动能衰减 (had_decline) ---
    decline_pct: float          # 下跌阈值: 涨跌幅 < 此值视为"经历过下跌"
    decay_ratio: float          # 涨幅收窄比例: pct < signal_pct * ratio
    decay_vol_ratio: float      # 收窄时的量比要求 (主板/科创板)
    decay_turnover: float       # 收窄时的换手率要求 (ST股)

    # --- 极度缩量企稳 ---
    shrink_vol_ratio: float     # 极度缩量: 量比阈值 (主板/科创板)
    shrink_turnover: float      # 极度缩量: 换手率阈值 (ST股, 首次突破)
    shrink_turnover_trend: float  # 极度缩量: 换手率阈值 (ST股, 趋势中)

    # --- 止损/退出 ---
    stop_loss_pct: float        # Mode A 固定止损线 (负数)
    mode_b_ma20_days: int       # Mode B 连续N天跌破MA20才止损
    ma20_cum_loss_limit: float  # MA20下方缩量阴跌累计止损阈值

    # --- Mode B: 趋势回踩 ---
    pullback_range: float       # 回踩区间: 股价在MA20上方X%以内
    pullback_vol_ratio: float   # 回踩缩量: 量比要求 (主板/科创板)
    pullback_turnover: float    # 回踩缩量: 换手率要求 (ST股)

    # --- 趋势强度过滤 ---
    ma20_slope_min: float       # MA20斜率最低要求 (20天涨幅%)

    # --- MA20容忍度 ---
    ma20_tolerance: float       # 买入时MA20容忍系数

    # --- 其他参数 ---
    small_yang_max: float       # 小阳线上限
    trend_gap: float            # 多头确立：MA5/MA20比值
    trend_days: int             # 多头确立：连续天数
    reentry_window: int         # 二次上车观察窗口
    allow_re_entry: bool        # 是否允许二次上车
    max_hold_days: int          # 最大持仓天数
    strict_ma20_stop_window: int # MA20止损后严格模式窗口
    strict_signal_window: int   # 信号密集度严格模式窗口
    max_drawdown_from_peak: float  # 浮盈回撤止盈阈值(%)
    ma20_slope_filter: float    # MA20斜率过滤(20天涨幅%)
    shrink_need_stabilized: bool = True  # 极度缩量企稳是否需要stabilized前提
    
    # --- 动态止损均线切换 (浮盈分级保护) ---
    profit_tier_1: float = 10.0    # 浮盈<10%: 标准MA5止损(连续2天)
    profit_tier_2: float = 20.0    # 浮盈10-20%: 放宽MA5止损(连续4天)
    # 浮盈>20%: 跳过MA5,回退到MA20止损 + 浮盈回撤止盈双重保护


# --- 三套参数配置 ---

ST_PARAMS = BoardParams(
    board_name='ST股 (±5%)',
    limit_pct=5.0,
    limit_up=4.5,
    limit_down=-4.5,
    # 突破信号
    signal_vol_ratio=0,
    signal_turnover=5.0,
    signal_max_pct=8.0,
    use_turnover=True,
    signal_vol_ratio_trend=0,
    signal_turnover_trend=3.0,
    # 追踪期
    track_days=20,
    # 动能衰减
    decline_pct=-0.3,
    decay_ratio=0.5,
    decay_vol_ratio=0,
    decay_turnover=3.0,
    # 极度缩量
    shrink_vol_ratio=0,
    shrink_turnover=3.0,
    shrink_turnover_trend=2.0,
    # 止损
    stop_loss_pct=-5.0,
    mode_b_ma20_days=3,
    ma20_cum_loss_limit=-3.0,
    # 趋势回踩
    pullback_range=0.05,
    pullback_vol_ratio=0,
    pullback_turnover=3.0,
    # 趋势强度
    ma20_slope_min=0.03,
    # MA20容忍度
    ma20_tolerance=0.99,
    # 其他
    small_yang_max=5.0,
    trend_gap=1.03,
    trend_days=3,
    reentry_window=30,
    allow_re_entry=True,
    max_hold_days=60,
    strict_ma20_stop_window=30,
    strict_signal_window=7,
    max_drawdown_from_peak=0,  # ST股不做浮盈回撤止盈
    ma20_slope_filter=0.0,     # ST股不做斜率过滤
    shrink_need_stabilized=False,  # ST股极度缩量不需要stabilized前提
    profit_tier_1=8.0,         # ST股浮盈<8%: 标准MA5止损(连续2天)
    profit_tier_2=15.0,        # ST股浮盈8-15%: 放宽MA5止损(连续4天)
)

MAIN_PARAMS = BoardParams(
    board_name='主板 (±10%)',
    limit_pct=10.0,
    limit_up=9.5,
    limit_down=-9.5,
    # 突破信号
    signal_vol_ratio=1.3,
    signal_turnover=0,
    signal_max_pct=8.0,
    use_turnover=False,
    signal_vol_ratio_trend=1.0,
    signal_turnover_trend=0,
    # 追踪期
    track_days=14,
    # 动能衰减
    decline_pct=-0.3,
    decay_ratio=0.5,
    decay_vol_ratio=1.0,
    decay_turnover=0,
    # 极度缩量
    shrink_vol_ratio=0.7,
    shrink_turnover=0,
    shrink_turnover_trend=0,
    # 止损
    stop_loss_pct=-8.0,
    mode_b_ma20_days=3,
    ma20_cum_loss_limit=-3.0,
    # 趋势回踩
    pullback_range=0.05,
    pullback_vol_ratio=0.7,
    pullback_turnover=0,
    # 趋势强度
    ma20_slope_min=0.05,
    # MA20容忍度
    ma20_tolerance=0.985,
    # 其他
    small_yang_max=5.0,
    trend_gap=1.03,
    trend_days=3,
    reentry_window=30,
    allow_re_entry=True,
    max_hold_days=60,
    strict_ma20_stop_window=30,
    strict_signal_window=7,
    max_drawdown_from_peak=0,  # 主板不做浮盈回撤止盈
    ma20_slope_filter=0.05,    # 主板MA20斜率过滤5%
    shrink_need_stabilized=True,  # 主板极度缩量需要stabilized前提
    profit_tier_1=10.0,        # 主板浮盈<10%: 标准MA5止损(连续2天)
    profit_tier_2=20.0,        # 主板浮盈10-20%: 放宽MA5止损(连续4天)
)

STAR_PARAMS = BoardParams(
    board_name='科创板/创业板 (±20%)',
    limit_pct=20.0,
    limit_up=19.5,
    limit_down=-19.5,
    # 突破信号 - 和主板保持一致
    signal_vol_ratio=1.3,        # 主板: 1.3
    signal_turnover=0,
    signal_max_pct=15.0,          # 主板: 15.0
    use_turnover=False,
    signal_vol_ratio_trend=1.0,  # 主板: 1.0
    signal_turnover_trend=0,
    # 追踪期 - 和主板保持一致
    track_days=14,               # 主板: 14
    # 动能衰减
    decline_pct=-1.0,            # 核心改动: 原-0.3%在科创板是噪音
    decay_ratio=0.5,             # 主板: 0.5
    decay_vol_ratio=1.0,         # 主板: 1.0
    decay_turnover=0,
    # 极度缩量 - 和主板保持一致
    shrink_vol_ratio=0.7,        # 主板: 0.7
    shrink_turnover=0,
    shrink_turnover_trend=0,
    # 止损 - 核心改动
    stop_loss_pct=-12.0,         # 核心改动: 原-8%太紧
    mode_b_ma20_days=5,          # 核心改动: 原3天太敏感
    ma20_cum_loss_limit=-5.0,    # 科创板波动大,放宽到-5%
    # 趋势回踩 - 和主板保持一致
    pullback_range=0.05,         # 主板: 0.05
    pullback_vol_ratio=0.7,      # 主板: 0.7
    pullback_turnover=0,
    # 趋势强度 - 和主板保持一致
    ma20_slope_min=0.05,         # 主板: 0.05
    # MA20容忍度 - 和主板保持一致
    ma20_tolerance=0.985,        # 主板: 0.985
    # 其他 - 和主板保持一致
    small_yang_max=10.0,         # 科创板允许更大涨幅
    trend_gap=1.03,
    trend_days=3,
    reentry_window=30,
    allow_re_entry=False,        # 科创板关闭二次上车
    max_hold_days=60,
    strict_ma20_stop_window=30,
    strict_signal_window=7,
    max_drawdown_from_peak=0.0,   # 创业板大牛股回调幅度大，关闭浮盈回撤止盈
    ma20_slope_filter=0.05,     # 科创板MA20斜率过滤5%
    shrink_need_stabilized=True,  # 科创板极度缩量需要stabilized前提
    profit_tier_1=10.0,        # 科创板浮盈<10%: 标准MA5止损(连续2天)
    profit_tier_2=20.0,        # 科创板浮盈10-20%: 放宽MA5止损(连续4天)
)

# 科创板/创业板ST股参数
STAR_ST_PARAMS = BoardParams(
    board_name='科创板/创业板ST (±20%)',
    limit_pct=20.0,
    limit_up=19.5,
    limit_down=-19.5,
    # 信号判断: 用换手率 (ST特征)
    signal_vol_ratio=0,
    signal_turnover=5.0,
    signal_max_pct=15.0,          # 科创板特征
    use_turnover=True,
    signal_vol_ratio_trend=0,
    signal_turnover_trend=3.0,
    # 追踪期: 缩短到10天 (ST股波动大)
    track_days=10,
    # 动能衰减: 科创板幅度 + ST换手率判断
    decline_pct=-1.0,
    decay_ratio=1/3,
    decay_vol_ratio=0,
    decay_turnover=3.0,
    # 极度缩量
    shrink_vol_ratio=0,
    shrink_turnover=3.0,
    shrink_turnover_trend=2.0,
    # 止损: 用科创板幅度
    stop_loss_pct=-12.0,
    mode_b_ma20_days=5,
    ma20_cum_loss_limit=-5.0,
    # 趋势回踩
    pullback_range=0.08,          # 放宽到8% (ST股波动大)
    pullback_vol_ratio=0,
    pullback_turnover=3.0,
    # 趋势强度
    ma20_slope_min=0.05,
    # MA20容忍度
    ma20_tolerance=0.985,
    # 其他
    small_yang_max=10.0,
    trend_gap=1.03,
    trend_days=3,
    reentry_window=30,
    allow_re_entry=False,        # 科创板ST关闭二次上车
    max_hold_days=60,
    strict_ma20_stop_window=30,
    strict_signal_window=7,
    max_drawdown_from_peak=15.0,  # 科创板ST浮盈回撤15%止盈
    ma20_slope_filter=0.05,     # 科创板ST MA20斜率过滤5%
    shrink_need_stabilized=False,  # 科创板ST极度缩量不需要stabilized前提
    profit_tier_1=8.0,         # 科创板ST浮盈<8%: 标准MA5止损(连续2天)
    profit_tier_2=15.0,        # 科创板ST浮盈8-15%: 放宽MA5止损(连续4天)
)

# 参数映射表
_PARAMS_MAP = {
    'st': ST_PARAMS,
    'main': MAIN_PARAMS,
    'star': STAR_PARAMS,
    'star_st': STAR_ST_PARAMS,
}


# ============================================================
#  板块识别与参数获取
# ============================================================

# 注意: 原有的get_board_type函数已被移除
# 请使用params包中的get_board_type函数，该函数能正确区分科创板和创业板
# from params import get_board_type


def get_params(board: str, avg_turnover_120d: float = 3.0) -> BoardParams:
    """获取板块参数 - 优先使用params包"""
    # 映射旧接口到params包
    board_type_map = {
        'st': 'main_st',
        'main': 'main',
        'star': 'star',
        'star_st': 'star_st',
    }
    board_type = board_type_map.get(board, board)
    
    # 尝试从params包获取参数
    try:
        return get_params_from_package(board_type, avg_turnover_120d)
    except Exception:
        # 如果params包获取失败，使用本地硬编码参数
        return _PARAMS_MAP.get(board, MAIN_PARAMS)


# ============================================================
#  条件判断工具函数
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
    """判断是否满足'动能衰减'条件"""
    # 条件1: 真实下跌
    if pct < p.decline_pct:
        return True
    # 条件2: 涨幅收窄 + 缩量
    pct_shrink = pct < signal_pct * p.decay_ratio
    if p.use_turnover:
        vol_shrink = turnover < p.decay_turnover
    else:
        vol_shrink = vol_ratio < p.decay_vol_ratio
    return pct_shrink and vol_shrink


def check_extreme_shrink(p: BoardParams, vol_ratio: float, turnover: float,
                         in_trend: bool = False) -> bool:
    """判断是否满足'极度缩量企稳'条件"""
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
    """判断是否满足 Mode B 趋势回踩买入条件"""
    if ma20 is None or ma60 is None or ma20_20d_ago is None:
        return False
    # Stage 2 判断
    if ma20 <= ma60:
        return False
    if ma20 <= ma20_20d_ago:
        return False
    # MA20斜率过滤
    slope = (ma20 - ma20_20d_ago) / ma20_20d_ago
    if slope < p.ma20_slope_min:
        return False
    # 股价接近MA20
    if close < ma20 * 0.95:
        return False
    if close > ma20 * (1 + p.pullback_range):
        return False
    # 缩量确认
    if p.use_turnover:
        return turnover < p.pullback_turnover
    else:
        return vol_ratio < p.pullback_vol_ratio


def check_above_ma20(p: BoardParams, close: float, ma20: float) -> bool:
    """判断是否站上MA20 (考虑容忍度)"""
    if ma20 is None:
        return False
    return close >= ma20 * p.ma20_tolerance


# ============================================================
#  兼容旧接口的BoardConfig和detect_board
# ============================================================

@dataclass
class BoardConfig:
    """板块参数配置 - 兼容旧接口"""
    name: str
    limit_up: float       # 涨停判定阈值
    limit_down: float     # 跌停判定阈值
    signal_max_pct: float # 入池涨幅上限
    small_yang_max: float # 小阳线上限


def detect_board(code: str, name: str = '') -> BoardConfig:
    """根据股票代码判断板块 - 返回兼容旧接口的BoardConfig"""
    # 使用正确的get_board_type函数（已在第75行从params导入）
    board_type = get_board_type(code, name)
    p = get_params(board_type)
    return BoardConfig(
        name=p.board_name,
        limit_up=p.limit_up,
        limit_down=p.limit_down,
        signal_max_pct=p.signal_max_pct,
        small_yang_max=p.small_yang_max
    )


# ============================================================
#  策略全局参数 (逐步迁移到BoardParams)
# ============================================================
@dataclass
class StrategyConfig:
    """策略全局参数 - 保留用于向后兼容"""
    vol_min: float = 1.3          # 入池最低量比
    track_days: int = 14          # 追踪期天数
    trend_gap: float = 1.03       # 多头确立：MA5/MA20比值
    trend_days: int = 3           # 多头确立：连续天数
    extreme_shrink: float = 0.7   # 极度缩量阈值
    vol_up_threshold: float = 1.2 # 放量阈值
    ma20_tolerance: float = 0.985 # MA20容差
    reentry_window: int = 30      # 二次上车观察窗口
    max_hold_days: int = 60       # 最大持仓天数
    ma20_cum_loss_limit: float = -3.0
    strict_ma20_stop_window: int = 30
    strict_signal_window: int = 7


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
    stock['MA60'] = stock['close'].rolling(60).mean()  # 添加MA60用于Stage 2判断
    stock['vol_ma5'] = stock['成交量(万股)'].rolling(5).mean()
    stock['vol_ratio'] = stock['成交量(万股)'] / stock['vol_ma5']
    
    # 换手率（如果数据中有）
    if '换手率(%)' in stock.columns:
        stock['turnover_rate'] = stock['换手率(%)']
    else:
        stock['turnover_rate'] = None
    
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
#  Stage 2 趋势判断
# ============================================================
def is_stage2(row: pd.Series, prev_rows: pd.DataFrame) -> bool:
    """
    判断是否处于Stage 2上升趋势
    条件：MA20 > MA60 且 MA20在上升（比5天前高）
    """
    ma20 = row.get('MA20')
    ma60 = row.get('MA60')
    
    if pd.isna(ma20) or pd.isna(ma60):
        return False
    
    # MA20 > MA60
    if ma20 <= ma60:
        return False
    
    # MA20在上升（需要至少5天的历史数据）
    if len(prev_rows) < 5:
        return False
    
    ma20_prev5 = prev_rows.iloc[-5]['MA20']
    if pd.isna(ma20_prev5):
        return False
    
    return ma20 > ma20_prev5


def mode_b_trend_pullback(stock: pd.DataFrame, idx: int, p: BoardParams) -> bool:
    """
    模式B：趋势回踩买入信号 (使用BoardParams参数化)
    
    条件：
    1. Stage 2上升趋势（MA20 > MA60 且 MA20上升）
    2. MA20斜率足够陡峭（根据板块参数），过滤横盘震荡
    3. 股价接近MA20（上方X%以内，根据板块参数）
    4. 缩量企稳（根据板块参数使用量比或换手率）
    
    Args:
        stock: 股票数据DataFrame
        idx: 当前索引
        p: 板块参数配置
    
    Returns:
        True if 符合趋势回踩买入条件
    """
    if idx < 60:  # 需要至少60天数据计算MA60
        return False
    
    row = stock.iloc[idx]
    close = row['close']
    ma20 = row['MA20']
    ma60 = row['MA60']
    
    if pd.isna(ma20) or pd.isna(ma60):
        return False
    
    # 使用check_trend_pullback进行统一判断
    ma20_20days_ago = stock.iloc[idx-20]['MA20'] if idx >= 20 else None
    vol_ratio = row.get('vol_ratio', 0)
    turnover = row.get('turnover_rate', 0)
    
    return check_trend_pullback(p, close, ma20, ma60, ma20_20days_ago, vol_ratio, turnover)


# ============================================================
#  信号扫描
# ============================================================
def scan_signals(stock: pd.DataFrame, cfg: StrategyConfig, board: BoardConfig,
                p: BoardParams = None) -> List[Tuple[int, str]]:
    """
    扫描MA20放量突破信号和趋势回踩信号 (支持BoardParams参数化)
    
    Args:
        stock: 股票数据
        cfg: 策略配置
        board: 板块配置（兼容旧接口）
        p: 板块参数（新接口，优先使用）
    
    Returns:
        信号列表，每个元素为 (index, signal_type)
        signal_type: 'breakout' 或 'pullback'
    """
    signals = []
    
    # 如果没有传入BoardParams，从board推断（兼容旧代码）
    if p is None:
        if board.limit_pct == 5.0:
            p = ST_PARAMS
        elif board.limit_pct == 20.0:
            p = STAR_PARAMS
        else:
            p = MAIN_PARAMS
    
    for i in range(60, len(stock)):  # 从60开始，确保MA60已计算
        row = stock.iloc[i]
        prev = stock.iloc[i - 1]
        ma20 = row['MA20']
        prev_ma20 = prev['MA20']
        
        if pd.isna(ma20):
            continue
        
        # ========== MA20斜率过滤 ==========
        # 只在MA20斜率 > 设置值时才触发信号
        if i >= 20 and p.ma20_slope_filter > 0:
            ma20_20d_ago = stock.iloc[i-20]['MA20']
            if pd.notna(ma20_20d_ago) and ma20_20d_ago > 0:
                slope = (ma20 - ma20_20d_ago) / ma20_20d_ago
                if slope < p.ma20_slope_filter:
                    # 斜率不足，跳过此信号
                    continue
        
        # 判断是否处于趋势中（股价远离MA20）
        in_trend = row['close'] > ma20 * 1.5
        
        # ========== 模式A：MA20放量突破信号 ==========
        # 使用check_breakout_volume进行放量判断
        vol_ratio = row.get('vol_ratio', 0) if pd.notna(row.get('vol_ratio')) else 0
        turnover = row.get('turnover_rate', 0) if pd.notna(row.get('turnover_rate')) else 0
        volume_ok = check_breakout_volume(p, vol_ratio, turnover, in_trend)
        
        # 突破条件：今日收盘 > MA20，前日收盘 <= MA20*1.02
        # 放量条件，涨幅 <= 板块上限
        if (row['close'] > ma20
                and prev['close'] <= prev_ma20 * 1.02
                and volume_ok
                and row['pct'] <= p.signal_max_pct):
            signals.append((i, 'breakout'))
            continue  # 如果触发突破信号，跳过趋势回踩检测
        
        # ========== 模式B：趋势回踩买入信号 ==========
        # 只在未触发突破信号时检测
        if mode_b_trend_pullback(stock, i, p):
            signals.append((i, 'pullback'))
    
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
              last_exit_idx: int = -1,
              strict_entry: bool = False,
              p: BoardParams = None) -> EntryResult:
    """
    从信号日开始，追踪N天寻找买点 (完全参数化版本)
    
    Args:
        strict_entry: 为True时只接受极度缩量企稳，不接受回踩确认/动能衰减
                      触发条件：30天内有MA20止损 或 7天内有≥2个信号
        p: 板块参数配置（BoardParams）
    """
    result = EntryResult()
    
    # 如果没有传入BoardParams，从board推断（兼容旧代码）
    if p is None:
        if board.limit_pct == 5.0:
            p = ST_PARAMS
        elif board.limit_pct == 20.0:
            p = STAR_PARAMS
        else:
            p = MAIN_PARAMS
    
    row = stock.iloc[signal_idx]
    signal_pct = row['pct']
    ma20 = row['MA20']
    had_decline = False
    
    # === 从BoardParams获取参数，不再硬编码 ===
    max_track_days = p.track_days           # 追踪期天数
    
    for j in range(signal_idx + 1, min(signal_idx + max_track_days + 1, len(stock))):
        if j <= last_exit_idx:
            continue
        
        r = stock.iloc[j]
        d = str(r['交易日期'])[:10]
        m20 = r['MA20'] if pd.notna(r['MA20']) else ma20
        v = r['vol_ratio'] if pd.notna(r['vol_ratio']) else 1.0
        pct = r['pct']
        close = r['close']
        opn = r['open']
        above = check_above_ma20(p, close, m20)  # 使用BoardParams的容忍度
        day_n = j - signal_idx
        
        body = abs(close - opn) / close if close > 0 else 0
        not_vol_up = v < cfg.vol_up_threshold
        is_small_yang = 0 < pct <= p.small_yang_max   # 使用BoardParams
        is_doji = body < 0.005
        
        # 获取换手率
        turnover_rate = r.get('turnover_rate') if 'turnover_rate' in r else None
        turnover = turnover_rate if pd.notna(turnover_rate) else 0
        
        # 判断是否处于趋势中（用于分档阈值）
        in_trend = close > m20 * 1.5
        
        # 极度缩量判断：统一使用BoardParams
        extreme_shrink = check_extreme_shrink(p, v, turnover, in_trend)
        
        # 动能衰减判断：统一使用BoardParams
        if check_had_decline(p, pct, signal_pct, v, turnover):
            had_decline = True
        
        # 动能衰减（涨幅收窄到信号日的 decay_ratio 倍）
        decay_threshold = signal_pct * p.decay_ratio if signal_pct > 0 else 0
        momentum_decay = (0 <= pct <= decay_threshold) if signal_pct > 0 else False
        stabilized = had_decline or momentum_decay
        
        # 日志中的量能显示：ST股显示换手率，其他显示量比
        if p.use_turnover and pd.notna(turnover_rate):
            vol_tag = f'换手{turnover_rate:.2f}%'
        else:
            vol_tag = f'量比{v:.2f}x'
        
        # === 放量下跌判断 ===
        if v >= cfg.vol_up_threshold and pct < 0:
            if not above:
                result.log.append(
                    f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% {vol_tag} | [X] 放量跌破MA20")
                break
            else:
                result.log.append(
                    f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% {vol_tag} | [!] 放量跌未破MA20")
                had_decline = True
                continue
        
        # === 破MA20判断 ===
        if not above:
            if j > signal_idx + 1:
                prev_close = stock.iloc[j - 1]['close']
                prev_ma20 = stock.iloc[j - 1]['MA20'] if pd.notna(stock.iloc[j - 1]['MA20']) else 0
                prev_above = check_above_ma20(p, prev_close, prev_ma20)
                if not prev_above:
                    result.log.append(
                        f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% {vol_tag} | [X] 连续破MA20")
                    break
            result.log.append(
                f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% {vol_tag} | [!] 破MA20")
            continue
        
        # === 大盘过滤 ===
        mkt = idx_map.get(d, 0)
        
        # === 极度缩量企稳（根据BoardParams判断）===
        if above and extreme_shrink and stabilized:
            if mkt <= -1.0:
                result.log.append(
                    f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% {vol_tag} | [S] 大盘跌{mkt:.2f}%")
                continue
            result.triggered = True
            result.buy_idx = j
            result.buy_price = close
            result.buy_date = d
            result.buy_type = '极度缩量企稳'
            result.log.append(
                f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% {vol_tag} | [OK] 极度缩量企稳(Day{day_n})")
            break
        
        # === 回踩确认 / 动能衰减 ===
        if above and not_vol_up and (is_small_yang or is_doji) and stabilized:
            # ★ 严格模式下跳过，只接受极度缩量企稳
            if strict_entry:
                result.log.append(
                    f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% {vol_tag} | "
                    f"[STRICT] 回踩确认但严格模式，需极度缩量")
                continue
            if mkt <= -1.0:
                result.log.append(
                    f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% {vol_tag} | [S] 大盘跌{mkt:.2f}%")
                continue
            reason = '动能衰减' if (momentum_decay and not had_decline) else '回踩确认'
            result.triggered = True
            result.buy_idx = j
            result.buy_price = close
            result.buy_date = d
            result.buy_type = reason
            result.log.append(
                f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% {vol_tag} | [OK] {reason}(Day{day_n})")
            break
        
        # === 等待状态 ===
        overheat_pct = p.limit_pct / 2   # 过热阈值 = 涨跌停幅度的一半
        if pct > overheat_pct:
            result.log.append(
                f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% {vol_tag} | [WAIT] 过热")
        elif pct > 0 and v >= cfg.vol_up_threshold:
            result.log.append(
                f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% {vol_tag} | [WAIT] 放量上涨")
        elif pct > 0 and not stabilized:
            result.log.append(
                f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% {vol_tag} | [WAIT] 未企稳")
        else:
            result.log.append(
                f"  Day{day_n:2d} {d} | {close:.2f} {pct:+.2f}% {vol_tag} | [WAIT] 等企稳")
    
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
             idx_map: Dict, cfg: StrategyConfig, board: BoardConfig,
             entry_mode: str = 'breakout', p: BoardParams = None) -> ExitResult:
    """
    从买入日开始，执行出场逻辑
    
    Args:
        entry_mode: 'breakout' 或 'trend_pullback'
                   trend_pullback模式下使用MA20动态止损（连续N天破MA20才止损）
        p: 板块参数配置（新接口，优先使用）
    """
    # 如果没有传入BoardParams，从board推断（兼容旧代码）
    if p is None:
        if board.limit_pct == 5.0:
            p = ST_PARAMS
        elif board.limit_pct == 20.0:
            p = STAR_PARAMS
        else:
            p = MAIN_PARAMS
    
    result = ExitResult()
    phase = 'MA20'
    below_ma5_count = 0
    below_ma20_count = 0  # Mode B: 连续破MA20天数计数
    gap_streak = 0
    had_limit_up = False
    below_ma20_cum_loss = 0.0  # MA20下方累计跌幅
    peak_pnl = 0.0  # 记录最高浮盈（用于回撤止盈）
    
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
        
        # ============ 浮盈回撤止盈 (科创板专用) ============
        if p.max_drawdown_from_peak > 0:
            # 更新最高浮盈
            if pnl > peak_pnl:
                peak_pnl = pnl
            # 检查回撤是否超过阈值
            if peak_pnl > 0 and pnl <= peak_pnl - p.max_drawdown_from_peak:
                result.exit_idx = k
                result.exit_price = close
                result.exit_date = d
                result.exit_reason = f'浮盈回撤{peak_pnl - pnl:.1f}%止盈'
                result.exit_type = 'drawdown'
                result.log.append(
                    f"  {d} | {close:.2f} {pnl:+.2f}% | 最高+{peak_pnl:.1f}%回落到{peak_pnl - pnl:.1f}% | "
                    f"[EXIT] 浮盈回撤止盈")
                return result
        
        # ============ 例外规则：跌停熔断 ============
        if pct >= board.limit_up:
            had_limit_up = True
        # ★ 浮盈保护：浮盈超过tier_2时，跳过跌停熔断，让利润奔跑
        if had_limit_up and pct <= board.limit_down and pnl < p.profit_tier_2:
            result.exit_idx = k
            result.exit_price = close
            result.exit_date = d
            result.exit_reason = '跌停熔断'
            result.exit_type = 'limit_down'
            result.log.append(f"  {d} | {close:.2f} {pct:+.2f}% | +{pnl:.1f}% | [STOP] 跌停熔断")
            return result
        elif had_limit_up and pct <= board.limit_down and pnl >= p.profit_tier_2:
            # 浮盈较高时，跳过跌停熔断，记录日志
            result.log.append(f"  {d} | {close:.2f} {pct:+.2f}% | +{pnl:.1f}% | [PROFIT] 跌停但浮盈>{p.profit_tier_2:.0f}%，继续持有")
        
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
                f"| +{pnl:.1f}% | [UP] 多头确立")
        
        # MA5回退MA20
        if phase == 'MA5' and m5 < m20:
            phase = 'MA20'
            below_ma5_count = 0
            gap_streak = 0
            result.log.append(
                f"  {d} | {close:.2f} {pct:+.2f}% | +{pnl:.1f}% | [DOWN] 回退MA20")
        
        # ============ MA5阶段出场 ============
        if phase == 'MA5':
            # 浮盈保护：浮盈越大，对MA5越宽容
            ma5_stop_days = 2  # 默认连续2天破MA5止损
            
            if pnl >= p.profit_tier_2:
                # 浮盈>tier_2: 跳过MA5止损，回退到MA20阶段让利润奔跑
                phase = 'MA20'
                below_ma5_count = 0
                result.log.append(
                    f"  {d} | {close:.2f} {pct:+.2f}% | +{pnl:.1f}% | [PROFIT] "
                    f"浮盈>{p.profit_tier_2:.0f}%，回退MA20阶段")
                continue  # 跳到MA20阶段处理
            elif pnl >= p.profit_tier_1:
                # 浮盈tier_1-tier_2: MA5连续天数从2放宽到4
                ma5_stop_days = 4
            # 否则浮盈<tier_1: 保持默认2天
            
            # 高开低走且收盘<MA5
            if below_ma5_close and high_open_low_close:
                result.exit_idx = k
                result.exit_price = close
                result.exit_date = d
                result.exit_reason = '高开低走且破MA5'
                result.exit_type = 'ma5'
                result.log.append(
                    f"  {d} | {close:.2f} 开{opn:.2f} X_MA5({m5:.2f}) "
                    f"| +{pnl:.1f}% | [EXIT] 高开低走且破MA5")
                return result
            
            if not above_ma5:
                if is_up_day:
                    # ★ 破MA5但收阳 → 在努力收复，不计数
                    result.log.append(
                        f"  {d} | {close:.2f} {pct:+.2f}% X_MA5({m5:.2f}) "
                        f"| +{pnl:.1f}% | [OK] 破MA5但收阳，不计数")
                    below_ma5_count = 0
                else:
                    below_ma5_count += 1
                    if below_ma5_count >= ma5_stop_days:
                        result.exit_idx = k
                        result.exit_price = close
                        result.exit_date = d
                        result.exit_reason = f'连续{ma5_stop_days}天破MA5且收阴'
                        result.exit_type = 'ma5'
                        result.log.append(
                            f"  {d} | {close:.2f} {pct:+.2f}% X_MA5({m5:.2f}) "
                            f"| +{pnl:.1f}% | [EXIT] 连续{ma5_stop_days}天破MA5且收阴")
                        return result
                    else:
                        tier_info = f"(放宽{ma5_stop_days}天)" if ma5_stop_days > 2 else ""
                        result.log.append(
                            f"  {d} | {close:.2f} {pct:+.2f}% X_MA5({m5:.2f}) "
                            f"| +{pnl:.1f}% | [!] 破MA5+收阴 第{below_ma5_count}天{tier_info}")
            else:
                if below_ma5_count > 0:
                    result.log.append(
                        f"  {d} | {close:.2f} {pct:+.2f}% OK_MA5 | +{pnl:.1f}% | [OK] 站回MA5")
                below_ma5_count = 0
                if abs(pct) > 2:
                    limit_tag = '[L]' if had_limit_up else ''
                    result.log.append(
                        f"  {d} | {close:.2f} {pct:+.2f}% OK_MA5 差距{gap:+.1f}% "
                        f"| +{pnl:.1f}% | 持有{limit_tag}")
        
        # ============ MA20阶段出场 ============
        elif phase == 'MA20':
            if not above_ma20:
                # 累计跌幅追踪
                below_ma20_cum_loss += pct
                
                # ===== Mode B 趋势回踩：MA20动态止损逻辑 =====
                if entry_mode == 'trend_pullback':
                    below_ma20_count += 1
                    if below_ma20_count >= p.mode_b_ma20_days:
                        # 连续N天破MA20，执行止损
                        result.exit_idx = k
                        result.exit_price = close
                        result.exit_date = d
                        result.exit_reason = f'趋势回踩:连续{p.mode_b_ma20_days}天破MA20'
                        result.exit_type = 'ma20'
                        result.log.append(
                            f"  {d} | {close:.2f} {pct:+.2f}% X_MA20(连续{below_ma20_count}天) "
                            f"| +{pnl:.1f}% | [EXIT] 趋势回踩:连续{p.mode_b_ma20_days}天破MA20止损")
                        return result
                    else:
                        # 观察状态，不止损
                        result.log.append(
                            f"  {d} | {close:.2f} {pct:+.2f}% X_MA20(第{below_ma20_count}天) "
                            f"| +{pnl:.1f}% | [!] 趋势回踩:破MA20第{below_ma20_count}天，观察")
                else:
                    # ===== Mode A 突破模式：原有止损逻辑 =====
                    # 止损条件1：放量+下跌+破MA20+大盘正常
                    if v >= cfg.vol_up_threshold and pct < 0 and mkt > -1.0:
                        result.exit_idx = k
                        result.exit_price = close
                        result.exit_date = d
                        result.exit_reason = '放量+下跌+破MA20+大盘正常'
                        result.exit_type = 'ma20'
                        result.log.append(
                            f"  {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x X_MA20 "
                            f"| +{pnl:.1f}% | [EXIT] 放量+下跌+破MA20+大盘正常")
                        return result
                    
                    # 止损条件2：缩量阴跌累计超过阈值
                    if below_ma20_cum_loss <= p.ma20_cum_loss_limit:
                        result.exit_idx = k
                        result.exit_price = close
                        result.exit_date = d
                        result.exit_reason = f'缩量阴跌累计{below_ma20_cum_loss:.1f}%'
                        result.exit_type = 'ma20'
                        result.log.append(
                            f"  {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x X_MA20 "
                            f"累计{below_ma20_cum_loss:+.1f}% "
                            f"| +{pnl:.1f}% | [EXIT] 缩量阴跌累计>{abs(p.ma20_cum_loss_limit):.0f}%止损")
                        return result
                    
                    # 观察状态
                    if v >= cfg.vol_up_threshold and pct < 0 and mkt <= -1.0:
                        result.log.append(
                            f"  {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x X_MA20 "
                            f"累计{below_ma20_cum_loss:+.1f}% "
                            f"| +{pnl:.1f}% | [!] 放量跌但大盘大跌")
                    elif v >= cfg.vol_up_threshold and pct >= 0:
                        result.log.append(
                            f"  {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x X_MA20 "
                            f"| +{pnl:.1f}% | [OK] 放量收复中")
                    elif v <= 0.85:
                        result.log.append(
                            f"  {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x X_MA20 "
                            f"累计{below_ma20_cum_loss:+.1f}% "
                            f"| +{pnl:.1f}% | [OK] 缩量洗盘")
                    elif pct < -5:
                        result.log.append(
                            f"  {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x X_MA20 "
                            f"| +{pnl:.1f}% | [OK] 大跌但未放量")
                    else:
                        result.log.append(
                            f"  {d} | {close:.2f} {pct:+.2f}% 量比{v:.2f}x X_MA20 "
                            f"累计{below_ma20_cum_loss:+.1f}% "
                            f"| +{pnl:.1f}% | [!] 观察")
            else:
                # 站回MA20，重置计数器和累计跌幅
                below_ma20_count = 0
                below_ma20_cum_loss = 0.0
                if abs(pct) > 2 or gap > 2:
                    result.log.append(
                        f"  {d} | {close:.2f} {pct:+.2f}% OK_MA20 差距{gap:+.1f}%"
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


def check_reentry(stock: pd.DataFrame, exit_idx: int, cfg: StrategyConfig, buy_price: float) -> ReentryResult:
    """
    MA5止损后，检查是否满足二次上车条件
    新增累计涨幅限制：如果从首次突破点累计涨幅超过150%，不再触发二次上车
    """
    result = ReentryResult()
    
    # 检查累计涨幅是否超过150%
    if exit_idx >= 0 and exit_idx < len(stock):
        exit_price = stock.iloc[exit_idx]['close']
        if buy_price > 0:
            # 计算从首次突破点到退出点的累计涨幅
            total_return = (exit_price - buy_price) / buy_price * 100
            if total_return > 150:  # 累计涨幅超过150%
                result.log.append(f"  累计涨幅 {total_return:.1f}% > 150%，禁止二次上车（主升浪末端风险过高）")
                return result
    
    for k in range(exit_idx + 1, min(exit_idx + cfg.reentry_window, len(stock))):
        r = stock.iloc[k]
        d = str(r['交易日期'])[:10]
        m5 = r['MA5'] if pd.notna(r['MA5']) else 0
        m20 = r['MA20'] if pd.notna(r['MA20']) else 0
        close = r['close']
        
        # 跌破MA20 → 趋势结束，取消观察
        if close < m20:
            result.log.append(f"  {d} | {close:.2f} X_MA20({m20:.2f}) | 破MA20，取消观察")
            return result
        
        # 站回MA5 → 触发二次上车
        if close >= m5:
            result.triggered = True
            result.reentry_idx = k
            result.reentry_price = close
            result.reentry_date = d
            result.log.append(
                f"  {d} | {close:.2f} OK_MA5({m5:.2f}) OK_MA20({m20:.2f}) | [REENTRY] 二次上车!")
            return result
        
        result.log.append(
            f"  {d} | {close:.2f} X_MA5({m5:.2f}) OK_MA20({m20:.2f}) | 等待站回MA5")
    
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
             verbose: bool = True,
             stock_name: str = '') -> List[Trade]:
    """
    完整回测入口
    
    Args:
        stock_df: 股票原始数据
        code: 股票代码（如 '300308'）
        index_df: 上证指数数据（可选）
        verbose: 是否打印详细日志
        stock_name: 股票名称（用于判断ST股）
    
    Returns:
        交易记录列表
    """
    cfg = StrategyConfig()
    board = detect_board(code, stock_name)
    
    # 获取板块参数（新接口）- 使用正确的get_board_type函数
    board_type = get_board_type(code, stock_name)
    p = get_params(board_type)
    
    stock, idx_map = prepare_data(stock_df, index_df)
    
    if verbose:
        print(f"{'=' * 85}")
        print(f"  {code} 回测 | {board.name} | 涨跌停±{board.limit_up:.0f}%")
        print(f"  股价: {stock['close'].iloc[0]:.2f} → {stock['close'].iloc[-1]:.2f} "
              f"({(stock['close'].iloc[-1] / stock['close'].iloc[0] - 1) * 100:+.0f}%)")
        print(f"{'=' * 85}")
    
    # 扫描信号
    all_signals = scan_signals(stock, cfg, board, p)
    if verbose:
        print(f"\n信号池: {len(all_signals)}个")
        for si, stype in all_signals:
            r = stock.iloc[si]
            type_str = "突破" if stype == 'breakout' else "回踩"
            print(f"  {str(r['交易日期'])[:10]} | {r['close']:.2f} "
                  f"涨{r['pct']:+.1f}% 量比{r['vol_ratio']:.2f}x | [{type_str}]")
    
    trades = []
    last_exit_idx = -1
    signal_history = []     # 记录所有信号的 (signal_idx, signal_date)
    ma20_stop_history = []  # 记录MA20止损的 (exit_idx, exit_date)
    
    for si, stype in all_signals:
        if si <= last_exit_idx:
            continue
        
        signal_date = str(stock.iloc[si]['交易日期'])[:10]
        signal_type = stype  # 'breakout' 或 'pullback'
        
        # === 判断是否启用严格模式 ===
        strict_entry = False
        strict_reason = ''
        
        # 条件1：30天内有MA20止损
        for stop_idx, stop_date in ma20_stop_history:
            if si - stop_idx <= cfg.strict_ma20_stop_window:
                strict_entry = True
                strict_reason = f'{cfg.strict_ma20_stop_window}天内有MA20止损({stop_date})'
                break
        
        # 条件2：7天内有其他信号
        if not strict_entry:
            for prev_si, prev_date in signal_history:
                if si - prev_si <= cfg.strict_signal_window and si != prev_si:
                    strict_entry = True
                    strict_reason = f'{cfg.strict_signal_window}天内有其他信号({prev_date})'
                    break
        
        # 记录当前信号
        signal_history.append((si, signal_date))
        
        # === 模式B：趋势回踩信号直接买入 ===
        if signal_type == 'pullback':
            r = stock.iloc[si]
            entry = EntryResult()
            entry.triggered = True
            entry.buy_idx = si
            entry.buy_price = r['close']
            entry.buy_date = signal_date
            entry.buy_type = '趋势回踩'
            entry.entry_mode = 'trend_pullback'  # 标记为趋势回踩模式
            turnover = r.get('turnover_rate', 0)
            turnover_val = turnover if pd.notna(turnover) else 0
            entry.log = [f"  趋势回踩买入 | MA20:{r['MA20']:.2f} 换手:{turnover_val:.2f}%"]
            
            if verbose:
                print(f"\n[+] 趋势回踩信号 {signal_date} | {r['close']:.2f}")
                print(f"  Stage 2上升趋势，股价接近MA20，缩量企稳")
        else:
            # === 模式A：突破信号需要追踪期 ===
            if verbose and strict_entry:
                print(f"\n  [严格模式] {strict_reason} -> 只接受极度缩量企稳")
            
            entry = run_entry(stock, si, idx_map, cfg, board, last_exit_idx,
                              strict_entry=strict_entry, p=p)
            entry.entry_mode = 'breakout'  # 标记为突破模式
            
            if not entry.triggered:
                if verbose:
                    status = '放弃' if any('跌破MA20' in l for l in entry.log) else '期满'
                    r = stock.iloc[si]
                    mark = '[X]' if '放弃' in status else '[O]'
                    print(f"\n{mark} {signal_date} | "
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
        cur_entry_mode = getattr(entry, 'entry_mode', 'breakout')  # 获取入场模式
        
        while True:
            # 执行出场
            exit_result = run_exit(stock, cur_buy_idx, cur_buy_price, idx_map, cfg, board, cur_entry_mode, p)
            
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
                icon = '[+]' if total_pnl > 0 else '[-]'
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
            
            # 记录MA20止损历史（用于严格模式判定）
            if exit_result.exit_type == 'ma20':
                ma20_stop_history.append(
                    (exit_result.exit_idx, exit_result.exit_date))
            
            # === 二次上车检查 ===
            if exit_result.exit_type != 'ma5' or not exit_result.exit_idx:
                break
            
            # 检查是否允许二次上车
            if not p.allow_re_entry:
                if verbose:
                    print(f"\n  [关闭] 该板块不允许二次上车")
                break
            
            reentry = check_reentry(stock, exit_result.exit_idx, cfg, cur_buy_price)
            
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
                # 二次上车保持原有的entry_mode（继承原始信号的止损逻辑）
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
        icon = '[+]' if t.pnl > 0 else '[-]'
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
    stock_file = '个股行情数据.xlsx'
    index_file = '000001_SH行情数据统计明细.xlsx'
    code = '600760'
    # ----------------------------
    
    stock_df = pd.read_excel(stock_file)
    index_df = pd.read_excel(index_file)
    
    trades = backtest(stock_df, code, index_df, verbose=True)
    print_summary(trades)
