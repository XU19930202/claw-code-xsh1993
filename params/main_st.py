"""
ST主板参数 (±5%)
沪市 60xxxx / 深市 00xxxx 带ST标记

核心特征:
- 涨跌幅±5%，限购50万股/账户/天
- 用换手率替代量比（限购导致成交量被制度性压制）
- 换手率阈值分档：首次突破5% / 趋势中3%
- 极度缩量也用换手率判断

流动性适配:
- ST股流动性差异极大（000506日常7-9% vs *ST摩登日常1-2%）
- 高流动性ST: 阈值接近标准值
- 低流动性ST: 阈值大幅下调（否则永远触发不了信号）
"""

from .base import BoardParams, classify_liquidity, liquidity_scale


def get_params(avg_turnover_120d: float = 3.0) -> BoardParams:
    """
    根据120日均换手率生成ST主板参数
    
    Args:
        avg_turnover_120d: 120日平均换手率(%), 默认3.0
    """
    liq = classify_liquidity(avg_turnover_120d)
    t = avg_turnover_120d

    return BoardParams(
        board_name=f'ST主板 (±5%) [{liq}流动性]',
        board_code='main_st',
        liquidity=liq,
        avg_turnover_120d=t,

        # --- 涨跌幅 ---
        limit_pct=5.0,
        limit_up=4.8,
        limit_down=-4.8,

        # --- 突破信号 (用换手率) ---
        signal_vol_ratio=0,
        # 高流动性: 换手率≥7%才算放量; 低流动性: ≥3%就算放量
        signal_turnover=liquidity_scale(t, low_val=3.0, mid_val=5.0, high_val=7.0),
        signal_max_pct=8.0,
        use_turnover=True,
        signal_vol_ratio_trend=0,
        # 趋势中放量: 同比例缩放
        signal_turnover_trend=liquidity_scale(t, low_val=1.5, mid_val=3.0, high_val=5.0),

        # --- 追踪期 ---
        track_days=20,                # ST股波动慢，追踪期延长

        # --- 动能衰减 ---
        decline_pct=-0.3,
        decay_ratio=0.5,
        decay_vol_ratio=0,
        # 动能衰减的换手率阈值
        decay_turnover=liquidity_scale(t, low_val=1.5, mid_val=3.0, high_val=5.0),

        # --- 极度缩量 ---
        shrink_vol_ratio=0,
        # 极度缩量: 低流动性ST只需换手<1.5%
        shrink_turnover=liquidity_scale(t, low_val=1.5, mid_val=3.0, high_val=5.0),
        shrink_turnover_trend=liquidity_scale(t, low_val=1.0, mid_val=2.0, high_val=3.0),
        shrink_need_stabilized=False,  # ST股极度缩量企稳不需要stabilized前提

        # --- 止损 ---
        stop_loss_pct=-5.0,           # ST股单日最大-5%
        mode_b_ma20_days=3,
        ma20_cum_loss_limit=-3.0,

        # --- 趋势回踩 ---
        pullback_range=0.05,
        pullback_vol_ratio=0,
        pullback_turnover=liquidity_scale(t, low_val=1.5, mid_val=3.0, high_val=5.0),

        # --- 趋势强度 ---
        ma20_slope_min=0.03,          # ST股涨得慢，斜率要求更低

        # --- MA20容忍度 ---
        ma20_tolerance=0.99,          # ST股波动小，容忍度可以更紧

        # --- 其他 ---
        small_yang_max=3.0,           # ST股5%涨跌幅下，3%算大阳了
        trend_gap=1.03,
        trend_days=3,
        reentry_window=30,
        allow_re_entry=True,          # ST主板允许二次上车
        max_hold_days=60,
        strict_ma20_stop_window=30,
        strict_signal_window=7,
        max_drawdown_from_peak=0,     # ST主板关闭浮盈回撤止盈
        ma20_slope_filter=0,          # ST主板关闭斜率过滤（涨得慢是常态）
        
        # --- 动态止损均线切换 (ST股阈值更低，因为5%涨跌幅下涨8%已说明趋势很强) ---
        profit_tier_1=8.0,            # 浮盈<8%: 标准MA5止损(连续2天)
        profit_tier_2=15.0,           # 浮盈8-15%: 放宽MA5止损(连续4天)
        # 浮盈>15%: 跳过MA5,回退到MA20止损
    )
