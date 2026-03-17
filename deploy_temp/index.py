#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
腾讯云函数 - A股热点追踪
入口文件
"""

import os
import sys
import json
import time
import logging

# 设置日志
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(__file__))

# 导入热点追踪模块
try:
    from hotspot_tracker import main as tracker_main
    from config import load_config
except ImportError as e:
    logger.error(f"导入模块失败: {e}")
    def tracker_main(): pass
    def load_config(): return None


def main_handler(event, context):
    """
    腾讯云函数入口函数
    
    Args:
        event: 事件数据
        context: 上下文数据
    
    Returns:
        dict: 执行结果
    """
    logger.info("========== 开始执行 A股热点追踪 ==========")
    logger.info(f"Event: {json.dumps(event, ensure_ascii=False)}")
    logger.info(f"Request ID: {context.request_id}")
    
    start_time = time.time()
    
    try:
        # 执行热点追踪
        logger.info("开始执行热点追踪...")
        result = tracker_main()
        
        elapsed_time = time.time() - start_time
        logger.info(f"执行完成,耗时: {elapsed_time:.2f}秒")
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "status": "success",
                "message": "A股热点追踪执行成功",
                "data": result,
                "execution_time": f"{elapsed_time:.2f}s"
            }, ensure_ascii=False)
        }
        
    except Exception as e:
        logger.error(f"执行失败: {str(e)}", exc_info=True)
        
        elapsed_time = time.time() - start_time
        
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "status": "error",
                "message": f"执行失败: {str(e)}",
                "execution_time": f"{elapsed_time:.2f}s"
            }, ensure_ascii=False)
        }


def test_handler(event, context):
    """
    测试入口函数
    """
    logger.info("测试函数执行")
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "云函数测试成功",
            "event": str(event)
        }, ensure_ascii=False)
    }


# 本地测试
if __name__ == "__main__":
    # 模拟腾讯云函数的 event 和 context
    class MockContext:
        def __init__(self):
            self.request_id = "test-request-001"
    
    # 测试执行
    event = {}
    context = MockContext()
    
    result = main_handler(event, context)
    print(json.dumps(result, ensure_ascii=False, indent=2))
