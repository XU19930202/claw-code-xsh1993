#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试 API Key"""
from config import DEEPSEEK_API_KEY
print("API Key:", DEEPSEEK_API_KEY[:20] + '...' if DEEPSEEK_API_KEY else 'None')
print("长度:", len(DEEPSEEK_API_KEY) if DEEPSEEK_API_KEY else 0)
