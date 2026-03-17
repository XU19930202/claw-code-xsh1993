#!/bin/bash
# 腾讯云函数部署脚本

set -e

echo "======================================"
echo "腾讯云函数 - A股热点追踪 部署脚本"
echo "======================================"

# 检查是否安装了腾讯云 CLI
if ! command -v scf &> /dev/null; then
    echo "❌ 未检测到腾讯云 CLI"
    echo "请先安装: pip install scf"
    echo "或访问: https://cloud.tencent.com/document/product/583/33446"
    exit 1
fi

# 检查是否已登录
if ! scf config show &> /dev/null; then
    echo "⚠️  未登录腾讯云"
    echo "请先登录: scf login"
    exit 1
fi

echo ""
echo "📦 步骤1: 准备部署包"
echo "--------------------------------------"

# 创建临时目录
TEMP_DIR="deploy_temp"
rm -rf $TEMP_DIR
mkdir -p $TEMP_DIR

# 复制必要文件
cp hotspot_tracker.py $TEMP_DIR/
cp config.yaml $TEMP_DIR/
cp index.py $TEMP_DIR/
cp config.py $TEMP_DIR/

# 复制依赖包
echo "安装依赖包..."
pip install -r scf/requirements.txt -t $TEMP_DIR/ --no-user

# 创建目录结构
mkdir -p $TEMP_DIR/history
mkdir -p $TEMP_DIR/hotspot_data

echo "✅ 部署包准备完成"
ls -lh $TEMP_DIR/

echo ""
echo "📤 步骤2: 部署到云函数"
echo "--------------------------------------"

# 部署配置
FUNCTION_NAME="a股热点追踪"
REGION="ap-guangzhou"
RUNTIME="Python3.9"
HANDLER="index.main_handler"
TIMEOUT="300"
MEMORY="256"

echo "函数名称: $FUNCTION_NAME"
echo "地域: $REGION"
echo "运行时: $RUNTIME"
echo "入口: $HANDLER"
echo "超时时间: ${TIMEOUT}秒"
echo "内存: ${MEMORY}MB"

# 部署函数
scf deploy \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --runtime "$RUNTIME" \
    --handler "$HANDLER" \
    --timeout "$TIMEOUT" \
    --memory "$MEMORY" \
    --code-path "$TEMP_DIR"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 部署成功!"
    echo ""
    echo "下一步操作:"
    echo "1. 在腾讯云控制台配置环境变量"
    echo "2. 设置定时触发器"
    echo "3. 测试函数"
else
    echo ""
    echo "❌ 部署失败"
    exit 1
fi

# 清理临时文件
echo ""
echo "🧹 清理临时文件..."
rm -rf $TEMP_DIR

echo ""
echo "======================================"
echo "部署完成!"
echo "======================================"
