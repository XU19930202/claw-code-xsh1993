#!/usr/bin/env python3
"""最小化测试2：验证backtest函数的正确调用方式"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

print("测试backtest函数的正确调用方式...")
print("=" * 60)

# 直接测试我们之前验证过的回测方式
try:
    # 测试我们之前成功过的回测方式
    import subprocess
    import re
    
    print("1. 测试之前成功的回测命令...")
    
    # 使用我们之前测试过的回测命令
    cmd = f"cd .. && python backtest_stock.py 300211.SZ"
    print(f"   执行命令: {cmd}")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    
    if result.returncode == 0:
        print("   命令执行成功")
        # 解析输出
        output = result.stdout
        
        # 提取关键信息
        import re
        total_return_match = re.search(r'总收益[：:]\s*([+-]?\d+\.?\d*)%', output)
        trade_count_match = re.search(r'交易\s*(\d+)\s*笔', output)
        win_rate_match = re.search(r'胜率[：:]\s*(\d+\.?\d*)%', output)
        
        if total_return_match:
            total_return = float(total_return_match.group(1))
            print(f"   总收益: {total_return}%")
        
        if trade_count_match:
            trades = int(trade_count_match.group(1))
            print(f"   交易笔数: {trades}")
        
        if win_rate_match:
            win_rate = float(win_rate_match.group(1))
            print(f"   胜率: {win_rate}%")
    else:
        print(f"   命令执行失败: {result.stderr}")
        
except Exception as e:
    print(f"测试错误: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("关键发现：")
print("1. 之前我们成功回测过300211")
print("2. 回测命令是: python backtest_stock.py 300211.SZ")
print("3. 我们需要确保并行脚本能正确调用相同的回测逻辑")