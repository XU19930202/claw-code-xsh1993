#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置加载模块 - 云函数版本
"""

import os
import yaml
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent
CONFIG_PATH = SCRIPT_DIR / "config.yaml"


def load_config():
    """
    加载配置文件
    
    Returns:
        dict: 配置数据
    """
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        # 如果配置文件不存在,返回默认配置
        return {
            "feishu_webhook": os.getenv("FEISHU_WEBHOOK", ""),
            "llm": {
                "api_url": os.getenv("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions"),
                "api_key": os.getenv("LLM_API_KEY", ""),
                "model": os.getenv("LLM_MODEL", "deepseek-chat")
            }
        }
    except Exception as e:
        raise Exception(f"加载配置文件失败: {e}")
