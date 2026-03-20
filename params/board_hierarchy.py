"""
板块参数分层架构
基于流动性/市值分级提供差异化的参数设置

分级标准:
1. 超高流动性: 日均换手 > 5% 或 市值 > 1000亿
2. 高流动性: 日均换手 2-5% 或 市值 200-1000亿  
3. 中流动性: 日均换手 1-2% 或 市值 50-200亿
4. 低流动性: 日均换手 < 1% 或 市值 < 50亿

参数调整原则:
- 高流动性: 放宽参数（大牛股特征明显）
- 低流动性: 收紧参数（防止过度持仓和假突破）
"""

from typing import Dict, Any, Optional
from .base import BoardParams, classify_liquidity, liquidity_scale

def apply_liquidity_adjustments(base_params: BoardParams, avg_turnover_120d: float) -> BoardParams:
    """
    根据流动性分级调整参数
    
    Args:
        base_params: 基础板块参数
        avg_turnover_120d: 120日平均换手率(%)
        
    Returns:
        调整后的参数
    """
    # 获取流动性分级
    liq_class = classify_liquidity(avg_turnover_120d)
    
    # 复制基础参数
    params_dict = base_params.__dict__.copy()
    
    # 根据流动性分级调整参数
    if liq_class == 'low':  # 低流动性
        adjustments = {
            # 收紧入场条件
            'signal_vol_ratio': max(1.5, params_dict.get('signal_vol_ratio', 1.3)),
            'signal_max_pct': min(10.0, params_dict.get('signal_max_pct', 15.0)),
            
            # 收紧止损条件
            'stop_loss_pct': max(-8.0, params_dict.get('stop_loss_pct', -12.0)),
            'ma20_cum_loss_limit': max(-3.0, params_dict.get('ma20_cum_loss_limit', -5.0)),
            
            # 收紧浮盈保护
            'max_drawdown_from_peak': min(15.0, params_dict.get('max_drawdown_from_peak', 25.0)),
            
            # 收紧趋势回踩条件
            'pullback_range': min(0.05, params_dict.get('pullback_range', 0.08)),
            
            # 收紧MA20容忍度
            'ma20_tolerance': max(0.985, params_dict.get('ma20_tolerance', 0.97)),
            
            # 降低趋势强度要求
            'ma20_slope_min': max(0.05, params_dict.get('ma20_slope_min', 0.03)),
            
            # 收紧二次上车条件
            'allow_re_entry': False,  # 低流动性关闭二次上车
        }
        
    elif liq_class == 'medium':  # 中流动性
        adjustments = {
            'max_drawdown_from_peak': min(20.0, params_dict.get('max_drawdown_from_peak', 25.0)),
            'ma20_tolerance': max(0.98, params_dict.get('ma20_tolerance', 0.97)),
            'pullback_range': min(0.07, params_dict.get('pullback_range', 0.08)),
        }
        
    elif liq_class == 'high':  # 高流动性
        adjustments = {
            # 稍微放宽
            'max_drawdown_from_peak': 25.0,
            'ma20_tolerance': 0.97,
            'allow_re_entry': True,
        }
        
    else:  # 超高流动性 (very_high)
        adjustments = {
            # 大幅放宽，适应大牛股特征
            'max_drawdown_from_peak': 30.0,  # 更宽松的浮盈保护
            'ma20_tolerance': 0.96,  # 允许更大回调空间
            'stop_loss_pct': -15.0,  # 放宽止损
            'ma20_cum_loss_limit': -8.0,  # 放宽累计亏损限制
            'pullback_range': 0.10,  # 允许10%回调
            'allow_re_entry': True,  # 启用二次上车
            'reentry_window': 15,  # 缩短观察窗口
        }
    
    # 应用调整
    for key, value in adjustments.items():
        if key in params_dict:
            params_dict[key] = value
    
    # 更新板块名称
    original_name = params_dict.get('board_name', '').replace(f' [{base_params.liquidity}流动性]', '')
    params_dict['board_name'] = f"{original_name} [{liq_class}流动性]"
    params_dict['liquidity'] = liq_class
    
    # 创建新的BoardParams对象
    return BoardParams(**params_dict)


def get_hierarchical_params(board_code: str, avg_turnover_120d: float, market_cap: Optional[float] = None) -> BoardParams:
    """
    获取分层参数
    
    Args:
        board_code: 板块代码 ('gem', 'star', 'main')
        avg_turnover_120d: 120日平均换手率(%)
        market_cap: 市值(亿元)，可选
        
    Returns:
        分层调整后的参数
    """
    from . import get_params as get_base_params
    
    # 获取基础参数
    base_params = get_base_params(board_code, avg_turnover_120d)
    
    # 如果提供市值，调整流动性分级
    if market_cap is not None:
        # 市值分级覆盖换手率分级
        if market_cap > 1000:  # 超大市值
            adjusted_turnover = max(avg_turnover_120d, 5.0)  # 视为超高流动性
        elif market_cap > 500:  # 大市值
            adjusted_turnover = max(avg_turnover_120d, 3.0)  # 视为高流动性
        elif market_cap < 50:  # 小市值
            adjusted_turnover = min(avg_turnover_120d, 1.0)  # 视为低流动性
        else:
            adjusted_turnover = avg_turnover_120d
    else:
        adjusted_turnover = avg_turnover_120d
    
    # 应用分层调整
    return apply_liquidity_adjustments(base_params, adjusted_turnover)


def test_hierarchy():
    """测试分层参数效果"""
    print("分层参数架构测试")
    print("=" * 60)
    
    # 测试不同流动性级别的参数差异
    test_cases = [
        (0.5, "低流动性(换手0.5%)"),
        (1.5, "中流动性(换手1.5%)"),
        (3.5, "高流动性(换手3.5%)"),
        (8.0, "超高流动性(换手8.0%)"),
    ]
    
    for turnover, desc in test_cases:
        params = get_hierarchical_params('gem', turnover)
        print(f"\n{desc}:")
        print(f"  板块名称: {params.board_name}")
        print(f"  浮盈保护: {params.max_drawdown_from_peak}%")
        print(f"  MA20容忍度: {params.ma20_tolerance}")
        print(f"  允许二次上车: {params.allow_re_entry}")
        print(f"  入场量比要求: {params.signal_vol_ratio:.1f}x")
    
    # 测试市值覆盖
    print(f"\n{'='*60}")
    print("市值覆盖测试:")
    print(f"{'='*60}")
    
    # 小市值高换手 -> 应视为低流动性
    params1 = get_hierarchical_params('gem', 3.0, market_cap=30)
    print(f"\n小市值(30亿)高换手(3.0%):")
    print(f"  实际分级: {params1.liquidity}")
    print(f"  浮盈保护: {params1.max_drawdown_from_peak}% (应收紧)")
    
    # 大市值低换手 -> 应视为高流动性
    params2 = get_hierarchical_params('gem', 1.0, market_cap=800)
    print(f"\n大市值(800亿)低换手(1.0%):")
    print(f"  实际分级: {params2.liquidity}")
    print(f"  浮盈保护: {params2.max_drawdown_from_peak}% (应放宽)")


if __name__ == "__main__":
    test_hierarchy()