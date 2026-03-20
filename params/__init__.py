"""
板块参数统一入口

使用方法:
    from params import get_board_type, get_params
    
    # 基本用法
    board_type = get_board_type(code='688220', name='翱捷科技-U')
    p = get_params(board_type, avg_turnover_120d=3.5)
    
    # 在策略中
    stock_df['turnover_120d'] = stock_df['换手率(%)'].rolling(120).mean()
    avg_t = stock_df['turnover_120d'].iloc[-1]
    p = get_params(board_type, avg_turnover_120d=avg_t)
"""

from .base import (
    BoardParams,
    classify_liquidity,
    liquidity_scale,
    check_breakout_volume,
    check_had_decline,
    check_extreme_shrink,
    check_stop_loss,
    check_trend_pullback,
    check_above_ma20,
)

from . import main_board, star_board, gem_board, main_st, star_st, gem_st


# ============================================================
# 板块识别
# ============================================================

def get_board_type(code: str, name: str = '') -> str:
    """
    根据股票代码和名称判断板块类型
    
    Returns:
        'main' / 'star' / 'gem' / 'main_st' / 'star_st' / 'gem_st'
    """
    is_st = 'ST' in name.upper()

    # 科创板: 688xxx
    if code.startswith('688'):
        return 'star_st' if is_st else 'star'

    # 创业板: 300xxx, 301xxx
    if code.startswith('300') or code.startswith('301'):
        return 'gem_st' if is_st else 'gem'

    # 北交所: 8xxxxx (暂归入科创板体系, ±30%涨跌幅后续可单独适配)
    if code.startswith('8') and len(code) == 6:
        return 'star_st' if is_st else 'star'

    # 主板: 沪市60xxxx, 深市00xxxx
    return 'main_st' if is_st else 'main'


# ============================================================
# 参数获取
# ============================================================

_MODULE_MAP = {
    'main':    main_board,
    'star':    star_board,
    'gem':     gem_board,
    'main_st': main_st,
    'star_st': star_st,
    'gem_st':  gem_st,
}


def get_params(board_type: str, avg_turnover_120d: float = 3.0) -> BoardParams:
    """
    获取板块参数
    
    Args:
        board_type: 板块类型 (get_board_type的返回值)
        avg_turnover_120d: 120日平均换手率(%)
    
    Returns:
        BoardParams 实例，参数根据流动性动态调整
    """
    module = _MODULE_MAP.get(board_type, main_board)
    return module.get_params(avg_turnover_120d)


# ============================================================
# 调试工具
# ============================================================

def print_params(p: BoardParams):
    """打印参数配置摘要"""
    print(f'\n{"="*60}')
    print(f'  {p.board_name}')
    print(f'  120日均换手率: {p.avg_turnover_120d:.2f}%')
    print(f'{"="*60}')
    print(f'  涨跌幅: ±{p.limit_pct}%')
    print(f'')
    print(f'  [信号识别]')
    if p.use_turnover:
        print(f'    放量: 换手率 >= {p.signal_turnover:.1f}% (趋势 >= {p.signal_turnover_trend:.1f}%)')
    else:
        print(f'    放量: 量比 >= {p.signal_vol_ratio:.2f} (趋势 >= {p.signal_vol_ratio_trend:.2f})')
    print(f'    最大涨幅: <= {p.signal_max_pct}%')
    print(f'    追踪期: {p.track_days}天')
    print(f'')
    print(f'  [动能衰减]')
    print(f'    下跌阈值: {p.decline_pct}%')
    print(f'    收窄比例: signal_pct × {p.decay_ratio:.2f}')
    print(f'')
    print(f'  [缩量企稳]')
    if p.use_turnover:
        print(f'    极度缩量: 换手率 < {p.shrink_turnover:.1f}% (趋势 < {p.shrink_turnover_trend:.1f}%)')
    else:
        print(f'    极度缩量: 量比 < {p.shrink_vol_ratio:.2f}')
    print(f'')
    print(f'  [止损]')
    print(f'    Mode A: {p.stop_loss_pct}%')
    print(f'    Mode B: 连续{p.mode_b_ma20_days}天 < MA20')
    print(f'    浮盈回撤: {"关闭" if p.max_drawdown_from_peak == 0 else f"{p.max_drawdown_from_peak}%"}')
    print(f'')
    print(f'  [趋势回踩]')
    print(f'    回踩区间: MA20上方{p.pullback_range*100:.0f}%以内')
    print(f'    MA20斜率: > {p.ma20_slope_min*100:.0f}%/20天')
    print(f'    二次上车: {"开" if p.allow_re_entry else "关"}')
    print(f'{"="*60}\n')


def demo():
    """演示不同板块+流动性的参数差异"""
    cases = [
        ('000506', '*ST中润', 7.0,  '高流动性ST主板'),
        ('000506', '*ST中润', 1.5,  '低流动性ST主板'),
        ('600289', 'ST信通', 3.0,  '中流动性ST主板'),
        ('688220', '翱捷科技-U', 3.5, '中流动性科创板'),
        ('300502', '新易盛', 5.0,    '高流动性创业板'),
        ('300502', '新易盛', 1.0,    '低流动性创业板'),
    ]
    
    for code, name, turnover, desc in cases:
        bt = get_board_type(code, name)
        p = get_params(bt, turnover)
        print(f'--- {desc}: {code} {name} (120日均换手 {turnover}%) ---')
        print_params(p)


if __name__ == '__main__':
    demo()
