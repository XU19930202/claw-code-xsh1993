"""
ST科创板参数 (±20%)
688xxx 带ST标记

特征:
- 涨跌幅±20% (跟随科创板，不是主板ST的±5%)
- 量能判断用换手率 (ST特征)
- 止损/持仓管理用科创板幅度
- 关闭二次上车 + 浮盈回撤止盈 (科创板特征)
"""

from .base import BoardParams, classify_liquidity, liquidity_scale


def get_params(avg_turnover_120d: float = 3.0) -> BoardParams:
    """
    根据120日均换手率生成ST科创板参数
    """
    liq = classify_liquidity(avg_turnover_120d)
    t = avg_turnover_120d

    return BoardParams(
        board_name=f'ST科创板 (±20%) [{liq}流动性]',
        board_code='star_st',
        liquidity=liq,
        avg_turnover_120d=t,

        # --- 涨跌幅 (科创板) ---
        limit_pct=20.0,
        limit_up=19.5,
        limit_down=-19.5,

        # --- 突破信号 (用换手率, ST特征) ---
        signal_vol_ratio=0,
        signal_turnover=liquidity_scale(t, low_val=3.0, mid_val=5.0, high_val=7.0),
        signal_max_pct=15.0,          # 科创板涨幅上限
        use_turnover=True,
        signal_vol_ratio_trend=0,
        signal_turnover_trend=liquidity_scale(t, low_val=1.5, mid_val=3.0, high_val=5.0),

        # --- 追踪期 ---
        track_days=14,                # 科创板波动快，不用延长

        # --- 动能衰减 (科创板幅度 + ST换手率) ---
        decline_pct=-1.0,             # 科创板幅度
        decay_ratio=1/3,
        decay_vol_ratio=0,
        decay_turnover=liquidity_scale(t, low_val=1.5, mid_val=3.0, high_val=5.0),

        # --- 极度缩量 (换手率) ---
        shrink_vol_ratio=0,
        shrink_turnover=liquidity_scale(t, low_val=1.5, mid_val=3.0, high_val=5.0),
        shrink_turnover_trend=liquidity_scale(t, low_val=1.0, mid_val=2.0, high_val=3.0),

        # --- 止损 (科创板幅度) ---
        stop_loss_pct=-12.0,
        mode_b_ma20_days=5,
        ma20_cum_loss_limit=-5.0,

        # --- 趋势回踩 ---
        pullback_range=0.08,          # ST波动大，放宽到8%
        pullback_vol_ratio=0,
        pullback_turnover=liquidity_scale(t, low_val=1.5, mid_val=3.0, high_val=5.0),

        # --- 趋势强度 ---
        ma20_slope_min=0.05,

        # --- MA20容忍度 ---
        ma20_tolerance=0.985,

        # --- 其他 ---
        small_yang_max=10.0,
        trend_gap=1.03,
        trend_days=3,
        reentry_window=30,
        allow_re_entry=False,         # 科创板关闭二次上车
        max_hold_days=60,
        strict_ma20_stop_window=30,
        strict_signal_window=7,
        max_drawdown_from_peak=15.0,  # 科创板浮盈回撤止盈
        ma20_slope_filter=0.05,
    )
