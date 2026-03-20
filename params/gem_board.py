"""
创业板参数 (±20%)
300xxx / 301xxx (非ST)

初期与科创板共享同一组参数值。
后续可根据回测数据独立调优，例如:
- 创业板机构持仓比例更高，假突破率可能更低 → 量比阈值可适当降低
- 创业板公司更偏消费/医药，趋势持续性可能更好 → 模式B参数可更宽松
"""

from .base import BoardParams, classify_liquidity, liquidity_scale


def get_params(avg_turnover_120d: float = 3.5) -> BoardParams:
    """
    根据120日均换手率生成创业板参数
    
    Args:
        avg_turnover_120d: 120日平均换手率(%), 默认3.5
    """
    liq = classify_liquidity(avg_turnover_120d)
    t = avg_turnover_120d

    return BoardParams(
        board_name=f'创业板 (±20%) [{liq}流动性]',
        board_code='gem',
        liquidity=liq,
        avg_turnover_120d=t,

        # --- 涨跌幅 ---
        limit_pct=20.0,
        limit_up=19.5,
        limit_down=-19.5,

        # --- 突破信号 ---
        signal_vol_ratio=liquidity_scale(t, low_val=1.0, mid_val=1.3, high_val=1.5),
        signal_turnover=0,
        signal_max_pct=15.0,
        use_turnover=False,
        signal_vol_ratio_trend=liquidity_scale(t, low_val=0.8, mid_val=1.0, high_val=1.2),
        signal_turnover_trend=0,

        # --- 追踪期 ---
        track_days=14,

        # --- 动能衰减 ---
        decline_pct=-1.0,
        decay_ratio=0.5,
        decay_vol_ratio=liquidity_scale(t, low_val=0.8, mid_val=1.0, high_val=1.2),
        decay_turnover=0,

        # --- 极度缩量 ---
        shrink_vol_ratio=liquidity_scale(t, low_val=0.9, mid_val=0.7, high_val=0.5),
        shrink_turnover=0,
        shrink_turnover_trend=0,

        # --- 止损 ---
        stop_loss_pct=-12.0,
        mode_b_ma20_days=5,
        ma20_cum_loss_limit=-5.0,

        # --- 趋势回踩 ---
        pullback_range=0.08,  # 创业板放宽到8%，允许更大回调空间
        pullback_vol_ratio=liquidity_scale(t, low_val=0.9, mid_val=0.7, high_val=0.5),
        pullback_turnover=0,

        # --- 趋势强度 ---
        ma20_slope_min=0.03,  # 创业板放宽到3%，趋势强度要求降低

        # --- MA20容忍度 ---
        ma20_tolerance=0.97,  # 创业板放宽到97%，允许更大回调空间

        # --- 其他 ---
        small_yang_max=12.0,  # 创业板放宽到12%，小阳线定义更宽松
        trend_gap=1.03,
        trend_days=3,
        reentry_window=20,           # 创业板缩短到20天，快速重新入场
        allow_re_entry=True,          # 创业板启用二次上车机制，抓住大牛股回调后的机会
        max_hold_days=60,
        strict_ma20_stop_window=30,
        strict_signal_window=7,
        max_drawdown_from_peak=25.0,  # 创业板设置25%宽松浮盈回撤保护，兼顾牛股持仓与利润锁定
        ma20_slope_filter=0.05,
    )
