@echo off
REM 腾讯云函数部署脚本 - Windows版本

echo ======================================
echo 腾讯云函数 - A股热点追踪 部署脚本
echo ======================================

REM 检查是否安装了腾讯云 CLI
python -c "import scf" 2>nul
if %errorlevel% neq 0 (
    echo ❌ 未检测到腾讯云 CLI
    echo 请先安装: pip install scf
    echo 或访问: https://cloud.tencent.com/document/product/583/33446
    pause
    exit /b 1
)

echo.
echo 📦 步骤1: 准备部署包
echo --------------------------------------

REM 创建临时目录
set TEMP_DIR=deploy_temp
if exist %TEMP_DIR% rmdir /s /q %TEMP_DIR%
mkdir %TEMP_DIR%

REM 复制必要文件
copy hotspot_tracker.py %TEMP_DIR%\
copy config.yaml %TEMP_DIR%\
copy scf\index.py %TEMP_DIR%\
copy scf\config.py %TEMP_DIR%\
copy scf\requirements.txt %TEMP_DIR%\

REM 安装依赖包
echo 安装依赖包...
cd %TEMP_DIR%
pip install -r requirements.txt -t . --no-user
cd ..

REM 创建目录结构
mkdir %TEMP_DIR%\history
mkdir %TEMP_DIR%\hotspot_data

echo ✅ 部署包准备完成
dir %TEMP_DIR%\

echo.
echo 📤 步骤2: 部署到云函数
echo --------------------------------------

REM 提示用户手动部署
echo ⚠️  Windows系统建议使用腾讯云控制台或在线编辑器部署
echo.
echo 部署步骤:
echo 1. 打开腾讯云云函数控制台
echo 2. 点击"新建函数"
echo 3. 选择"空白函数"
echo 4. 函数名称: a股热点追踪
echo 5. 运行环境: Python 3.9
echo 6. 将 %TEMP_DIR% 目录下的所有文件上传到函数代码
echo 7. 设置环境变量和定时触发器
echo.
pause

echo.
echo ======================================
echo 部署准备完成!
echo ======================================
echo.
echo 请按照上述步骤在腾讯云控制台完成部署
