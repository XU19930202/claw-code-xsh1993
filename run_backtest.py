# -*- coding: utf-8 -*-
import sys
import os

# 设置环境变量以支持UTF-8
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 导入并执行backtest脚本
if __name__ == '__main__':
    # 动态加载模块
    import importlib.util
    spec = importlib.util.spec_from_file_location("backtest_signal_pool", "backtest_signal_pool.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
