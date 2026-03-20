"""
科创板参数 (±20%)
688xxx (非ST)

与主板的核心差异（仅持仓管理层面）:
- 止损: -12% (主板-8%)
- Mode B MA20止损: 5天 (主板3天)
- 动能衰减阈值: -1.0% (主板-0.3%)
- 关闭二次上车
- 浮盈回撤15%止盈
- 过热阈值自动适配 (limit_pct/2 = 10%)

信号识别与主板保持一致，仅通过流动性缩放。
"""

from .base import BoardParams, classify_liquidity, liquidity_scale


def get_params(avg_turnover_120d: float = 3.5) -> BoardParams:
    """
    根据120日均换手率生成科创板参数
    
    Args:
        avg_turnover_120d: 120日平均换手率(%), 默认3.5 (科创板普遍偏高)
    """
    liq = classify_liquidity(avg_turnover_120d)
    t = avg_turnover_120d

    return BoardParams(
        board_name=f'科创板 (±20%) [{liq}流动性]',
        board_code='star',
        liquidity=liq,
        avg_turnover_120d=t,

        # --- 涨跌幅 ---
        limit_pct=20.0,
        limit_up=19.5,
        limit_down=-19.5,

        # --- 突破信号 (和主板同逻辑，通过流动性缩放) ---
        signal_vol_ratio=liquidity_scale(t, low_val=1.0, mid_val=1.3, high_val=1.5),
        signal_turnover=0,
        signal_max_pct=15.0,          # 科创板放宽到15%
        use_turnover=False,
        signal_vol_ratio_trend=liquidity_scale(t, low_val=0.8, mid_val=1.0, high_val=1.2),
        signal_turnover_trend=0,

        # --- 追踪期 ---
        track_days=14,

        # --- 动能衰减 (核心差异) ---
        decline_pct=-1.0,             # 科创板日常波动大，-0.3%是噪音
        decay_ratio=0.5,
        decay_vol_ratio=liquidity_scale(t, low_val=0.8, mid_val=1.0, high_val=1.2),
        decay_turnover=0,

        # --- 极度缩量 ---
        shrink_vol_ratio=liquidity_scale(t, low_val=0.9, mid_val=0.7, high_val=0.5),
        shrink_turnover=0,
        shrink_turnover_trend=0,

        # --- 止损 (核心差异) ---
        stop_loss_pct=-12.0,          # 放宽 (主板-8%)
        mode_b_ma20_days=5,           # 放宽 (主板3天)
        ma20_cum_loss_limit=-5.0,     # 放宽 (主板-3%)

        # --- 趋势回踩 ---
        pullback_range=0.05,
        pullback_vol_ratio=liquidity_scale(t, low_val=0.9, mid_val=0.7, high_val=0.5),
        pullback_turnover=0,

        # --- 趋势强度 ---
        ma20_slope_min=0.05,

        # --- MA20容忍度 ---
        ma20_tolerance=0.985,

        # --- 其他 (核心差异) ---
        small_yang_max=10.0,          # 科创板允许更大涨幅算小阳
        trend_gap=1.03,
        trend_days=3,
        reentry_window=30,
        allow_re_entry=False,         # 科创板关闭二次上车
        max_hold_days=60,
        strict_ma20_stop_window=30,
        strict_signal_window=7,
        max_drawdown_from_peak=15.0,  # 科创板浮盈回撤15%止盈
        ma20_slope_filter=0.05,
    )
