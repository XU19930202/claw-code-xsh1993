#!/bin/bash
# 腾讯云函数一键部署脚本 - A股热点追踪工具
# 使用说明: 先配置腾讯云CLI,然后运行此脚本

set -e  # 遇到错误立即退出

echo "======================================"
echo "腾讯云函数一键部署 - A股热点追踪"
echo "======================================"
echo ""

# 检查是否安装了腾讯云CLI
echo "【步骤1】检查腾讯云CLI..."
if ! command -v scf &> /dev/null; then
    echo "❌ 未检测到腾讯云CLI"
    echo "请先安装腾讯云CLI:"
    echo "pip install tencentcloud-scf"
    echo "配置命令: scf configure"
    exit 1
fi
echo "✅ 腾讯云CLI已安装"
echo ""

# 获取腾讯云账户信息
echo "【步骤2】获取腾讯云账户信息..."
ACCOUNT_INFO=$(scf info 2>&1)
echo "$ACCOUNT_INFO"
echo ""

# 提取Region和AppID
REGION=$(echo "$ACCOUNT_INFO" | grep "Region" | awk '{print $2}' || echo "ap-guangzhou")
APPID=$(echo "$ACCOUNT_INFO" | grep "AppID" | awk '{print $2}' || echo "")
echo "当前Region: $REGION"
echo "当前AppID: $APPID"
echo ""

# 函数配置
FUNCTION_NAME="hotspot_tracker"
RUNTIME="Python3.9"
MEMORY=256
TIMEOUT=300

echo "【步骤3】准备部署包..."
DEPLOY_DIR="deploy_temp"
rm -rf "$DEPLOY_DIR"
mkdir -p "$DEPLOY_DIR"

# 复制文件
echo "  - 复制主程序..."
cp hotspot_tracker.py "$DEPLOY_DIR/"

echo "  - 复制配置文件..."
cp config.yaml "$DEPLOY_DIR/"

echo "  - 创建云函数入口文件..."
cat > "$DEPLOY_DIR/index.py" << 'EOF'
import json
import sys
import os
from hotspot_tracker import main as hotspot_main

def main_handler(event, context):
    """
    腾讯云函数入口
    """
    try:
        print("开始执行A股热点追踪...")
        
        # 执行热点追踪
        hotspot_main()
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'success',
                'message': 'A股热点追踪执行完成'
            }, ensure_ascii=False)
        }
    except Exception as e:
        print(f"执行失败: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'message': str(e)
            }, ensure_ascii=False)
        }
EOF

echo "  - 安装依赖包..."
cd "$DEPLOY_DIR"
pip install jieba PyYAML requests openai -t . --quiet --no-user
cd ..

echo "  - 创建必要目录..."
mkdir -p "$DEPLOY_DIR/history"
mkdir -p "$DEPLOY_DIR/hotspot_data"

echo "✅ 部署包准备完成"
echo ""

# 创建压缩包
echo "【步骤4】创建部署压缩包..."
tar -czf "$FUNCTION_NAME.zip" -C "$DEPLOY_DIR" .
ZIP_SIZE=$(du -h "$FUNCTION_NAME.zip" | cut -f1)
echo "✅ 压缩包创建完成: $FUNCTION_NAME.zip ($ZIP_SIZE)"
echo ""

# 部署到云函数
echo "【步骤5】部署到腾讯云函数..."
echo "函数名称: $FUNCTION_NAME"
echo "运行环境: $RUNTIME"
echo "内存: ${MEMORY}MB"
echo "超时: ${TIMEOUT}秒"
echo ""

# 删除旧函数(如果存在)
echo "  - 检查旧函数..."
if scf list_functions 2>&1 | grep -q "$FUNCTION_NAME"; then
    echo "  - 删除旧函数..."
    scf delete_function --function_name "$FUNCTION_NAME" || true
fi

# 创建新函数
echo "  - 创建新函数..."
scf create_function \
    --function_name "$FUNCTION_NAME" \
    --runtime "$RUNTIME" \
    --memory "$MEMORY" \
    --timeout "$TIMEOUT" \
    --handler "index.main_handler" \
    --code_zip_file "$(pwd)/$FUNCTION_NAME.zip" \
    --region "$REGION"

echo "✅ 云函数部署成功"
echo ""

# 配置环境变量
echo "【步骤6】配置环境变量..."

# 读取配置文件
FEISHU_WEBHOOK=$(grep "feishu_webhook" config.yaml | awk -F'"' '{print $2}')
LLM_API_KEY=$(grep "api_key" config.yaml | awk -F'"' '{print $2}')

echo "  - 配置飞书Webhook..."
scf update_function_configuration \
    --function_name "$FUNCTION_NAME" \
    --region "$REGION" \
    --env_vars "{\"FEISHU_WEBHOOK\":\"$FEISHU_WEBHOOK\",\"LLM_API_KEY\":\"$LLM_API_KEY\"}"

echo "✅ 环境变量配置完成"
echo ""

# 配置定时触发器
echo "【步骤7】配置定时触发器..."
echo "触发时间: 每天早上8:00"

# 删除旧触发器(如果存在)
scf delete_trigger --function_name "$FUNCTION_NAME" --trigger_name "daily-timer" --region "$REGION" 2>/dev/null || true

# 创建新触发器
scf create_trigger \
    --function_name "$FUNCTION_NAME" \
    --trigger_name "daily-timer" \
    --trigger_type "Timer" \
    --trigger_desc "每天早上8点执行" \
    --trigger_attr "{\"cron_expression\":\"0 0 8 * * * *\",\"enable\":true}" \
    --region "$REGION"

echo "✅ 定时触发器配置完成"
echo ""

# 测试函数
echo "【步骤8】测试云函数..."
echo "  - 触发测试执行..."
RESULT=$(scf invoke --function_name "$FUNCTION_NAME" --region "$REGION" 2>&1)
echo "$RESULT"
echo ""

# 清理临时文件
echo "【步骤9】清理临时文件..."
rm -rf "$DEPLOY_DIR"
rm -f "$FUNCTION_NAME.zip"
echo "✅ 清理完成"
echo ""

# 完成
echo "======================================"
echo "✅ 部署完成!"
echo "======================================"
echo ""
echo "函数信息:"
echo "  函数名称: $FUNCTION_NAME"
echo "  Region: $REGION"
echo "  运行环境: $RUNTIME"
echo "  内存: ${MEMORY}MB"
echo "  超时: ${TIMEOUT}秒"
echo "  定时执行: 每天早上8:00"
echo ""
echo "管理地址:"
echo "  https://console.cloud.tencent.com/scf/list?rid=$REGION"
echo ""
echo "监控日志:"
echo "  https://console.cloud.tencent.com/scf/log?rid=$REGION&ns=default&fn=$FUNCTION_NAME"
echo ""
echo "下一步:"
echo "  1. 检查飞书群是否收到测试推送"
echo "  2. 在云函数控制台查看执行日志"
echo "  3. 如需修改执行时间,可在控制台调整触发器配置"
echo ""
