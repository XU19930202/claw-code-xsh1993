"""
主板参数 (±10%)
沪市 60xxxx / 深市 00xxxx (非ST)

流动性适配逻辑:
- 高流动性(>5%): 放量阈值上调，缩量阈值下调（噪音多，信号需更强）
- 中流动性(2-5%): 标准值（大部分主板股票）
- 低流动性(<2%): 放量阈值下调，缩量阈值上调（成交清淡，标准放宽）
"""

from .base import BoardParams, classify_liquidity, liquidity_scale


def get_params(avg_turnover_120d: float = 3.0) -> BoardParams:
    """
    根据120日均换手率生成主板参数
    
    Args:
        avg_turnover_120d: 120日平均换手率(%), 默认3.0
    """
    liq = classify_liquidity(avg_turnover_120d)
    t = avg_turnover_120d  # 缩写

    return BoardParams(
        board_name=f'主板 (±10%) [{liq}流动性]',
        board_code='main',
        liquidity=liq,
        avg_turnover_120d=t,

        # --- 涨跌幅 ---
        limit_pct=10.0,
        limit_up=9.5,
        limit_down=-9.5,

        # --- 突破信号 ---
        # 高流动性: 量比要求更高(1.5), 低流动性: 更低(1.0)
        signal_vol_ratio=liquidity_scale(t, low_val=1.0, mid_val=1.3, high_val=1.5),
        signal_turnover=0,
        signal_max_pct=8.0,
        use_turnover=False,
        # 趋势中放量阈值同步缩放
        signal_vol_ratio_trend=liquidity_scale(t, low_val=0.8, mid_val=1.0, high_val=1.2),
        signal_turnover_trend=0,

        # --- 追踪期 ---
        track_days=14,

        # --- 动能衰减 ---
        decline_pct=-0.3,
        decay_ratio=0.5,
        decay_vol_ratio=liquidity_scale(t, low_val=0.8, mid_val=1.0, high_val=1.2),
        decay_turnover=0,

        # --- 极度缩量 ---
        # 高流动性: 缩量标准更严(0.5), 低流动性: 更宽松(0.9)
        shrink_vol_ratio=liquidity_scale(t, low_val=0.9, mid_val=0.7, high_val=0.5),
        shrink_turnover=0,
        shrink_turnover_trend=0,

        # --- 止损 ---
        stop_loss_pct=-8.0,
        mode_b_ma20_days=3,
        ma20_cum_loss_limit=-3.0,

        # --- 趋势回踩 ---
        pullback_range=0.05,
        pullback_vol_ratio=liquidity_scale(t, low_val=0.9, mid_val=0.7, high_val=0.5),
        pullback_turnover=0,

        # --- 趋势强度 ---
        ma20_slope_min=0.05,

        # --- MA20容忍度 ---
        ma20_tolerance=0.985,

        # --- 其他 ---
        small_yang_max=5.0,
        trend_gap=1.03,
        trend_days=3,
        reentry_window=30,
        allow_re_entry=True,
        max_hold_days=60,
        strict_ma20_stop_window=30,
        strict_signal_window=7,
        max_drawdown_from_peak=0,     # 主板关闭浮盈回撤止盈
        ma20_slope_filter=0.05,
    )
