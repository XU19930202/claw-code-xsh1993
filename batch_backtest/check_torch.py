#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查PyTorch和CUDA安装
"""

try:
    import torch
    print(f'PyTorch版本: {torch.__version__}')
    print(f'CUDA可用: {torch.cuda.is_available()}')
    
    if torch.cuda.is_available():
        print(f'GPU设备: {torch.cuda.get_device_name(0)}')
        props = torch.cuda.get_device_properties(0)
        print(f'显存: {props.total_mem / 1024**3:.1f} GB')
        print(f'CUDA核心: {props.multi_processor_count} SM')
        print(f'计算能力: {props.major}.{props.minor}')
    else:
        print('CUDA不可用，请安装CUDA版本的PyTorch')
        print('安装命令: pip install torch --index-url https://download.pytorch.org/whl/cu121')
        
except ImportError:
    print('PyTorch未安装')
    print('安装命令: pip install torch --index-url https://download.pytorch.org/whl/cu121')