@echo off
REM 腾讯云函数一键部署脚本 - A股热点追踪工具
REM 使用说明: 先配置腾讯云CLI,然后运行此脚本

chcp 65001 >nul
setlocal enabledelayedexpansion

echo ======================================
echo 腾讯云函数一键部署 - A股热点追踪
echo ======================================
echo.

REM 检查是否安装了腾讯云CLI
echo 【步骤1】检查腾讯云CLI...
where scf >nul 2>&1
if errorlevel 1 (
    echo ❌ 未检测到腾讯云CLI
    echo 请先安装腾讯云CLI:
    echo pip install tencentcloud-scf
    echo 配置命令: scf configure
    pause
    exit /b 1
)
echo ✅ 腾讯云CLI已安装
echo.

REM 获取腾讯云账户信息
echo 【步骤2】获取腾讯云账户信息...
for /f "tokens=2 delims= " %%i in ('scf info 2^>^&1 ^| findstr /C:"Region"') do set REGION=%%i
if "%REGION%"=="" set REGION=ap-guangzhou
echo 当前Region: %REGION%
echo.

REM 函数配置
set FUNCTION_NAME=hotspot_tracker
set RUNTIME=Python3.9
set MEMORY=256
set TIMEOUT=300

echo 【步骤3】准备部署包...
set DEPLOY_DIR=deploy_temp
if exist "%DEPLOY_DIR%" rmdir /s /q "%DEPLOY_DIR%"
mkdir "%DEPLOY_DIR%"

echo   - 复制主程序...
copy /Y hotspot_tracker.py "%DEPLOY_DIR%\" >nul

echo   - 复制配置文件...
copy /Y config.yaml "%DEPLOY_DIR%\" >nul

echo   - 创建云函数入口文件...
(
echo import json
echo import sys
echo import os
echo from hotspot_tracker import main as hotspot_main
echo.
echo def main_handler^(event, context^):
echo     """
echo     腾讯云函数入口
echo     """
echo     try:
echo         print^( "开始执行A股热点追踪..."^)
echo         
echo         # 执行热点追踪
echo         hotspot_main^(^)
echo         
echo         return ^{
echo             'statusCode': 200,
echo             'body': json.dumps^({
echo                 'status': 'success',
echo                 'message': 'A股热点追踪执行完成'
echo             }, ensure_ascii=False^)
echo         }
echo     except Exception as e:
echo         print^(f"执行失败: {str^(e^)}"^)
echo         import traceback
echo         traceback.print_exc^(^)
echo         
echo         return ^{
echo             'statusCode': 500,
echo             'body': json.dumps^({
echo                 'status': 'error',
echo                 'message': str^(e^)
echo             }, ensure_ascii=False^)
echo         }
) > "%DEPLOY_DIR%\index.py"

echo   - 安装依赖包...
cd "%DEPLOY_DIR%"
pip install jieba PyYAML requests openai -t . --quiet --no-user
cd ..

echo   - 创建必要目录...
mkdir "%DEPLOY_DIR%\history" 2>nul
mkdir "%DEPLOY_DIR%\hotspot_data" 2>nul

echo ✅ 部署包准备完成
echo.

REM 创建压缩包
echo 【步骤4】创建部署压缩包...
cd "%DEPLOY_DIR%"
tar -czf "..\%FUNCTION_NAME%.zip" .
cd ..
for %%A in ("%FUNCTION_NAME%.zip") do set ZIP_SIZE=%%~zA
set /a ZIP_SIZE_MB=!ZIP_SIZE!/1048576
echo ✅ 压缩包创建完成: %FUNCTION_NAME%.zip (!ZIP_SIZE_MB! MB)
echo.

REM 部署到云函数
echo 【步骤5】部署到腾讯云函数...
echo 函数名称: %FUNCTION_NAME%
echo 运行环境: %RUNTIME%
echo 内存: %MEMORY%MB
echo 超时: %TIMEOUT%秒
echo.

REM 删除旧函数(如果存在)
echo   - 检查旧函数...
scf list_functions 2>nul | findstr "%FUNCTION_NAME%" >nul
if not errorlevel 1 (
    echo   - 删除旧函数...
    scf delete_function --function_name "%FUNCTION_NAME%" --region "%REGION%" >nul 2>&1
)

REM 创建新函数
echo   - 创建新函数...
scf create_function ^
    --function_name "%FUNCTION_NAME%" ^
    --runtime "%RUNTIME%" ^
    --memory %MEMORY% ^
    --timeout %TIMEOUT% ^
    --handler "index.main_handler" ^
    --code_zip_file "%cd%\%FUNCTION_NAME%.zip" ^
    --region "%REGION%"

echo ✅ 云函数部署成功
echo.

REM 配置环境变量
echo 【步骤6】配置环境变量...

REM 读取配置文件
for /f "tokens=2 delims= " %%i in ('findstr "feishu_webhook" config.yaml ^| findstr /C:"http"') do set FEISHU_WEBHOOK=%%i
for /f "tokens=2 delims= " %%i in ('findstr "api_key" config.yaml ^| findstr /C:"sk-"') do set LLM_API_KEY=%%i

echo   - 配置飞书Webhook...
scf update_function_configuration ^
    --function_name "%FUNCTION_NAME%" ^
    --region "%REGION%" ^
    --env_vars "{\"FEISHU_WEBHOOK\":\"%FEISHU_WEBHOOK%\",\"LLM_API_KEY\":\"%LLM_API_KEY%\"}"

echo ✅ 环境变量配置完成
echo.

REM 配置定时触发器
echo 【步骤7】配置定时触发器...
echo 触发时间: 每天早上8:00

REM 删除旧触发器(如果存在)
scf delete_trigger --function_name "%FUNCTION_NAME%" --trigger_name "daily-timer" --region "%REGION%" >nul 2>&1

REM 创建新触发器
scf create_trigger ^
    --function_name "%FUNCTION_NAME%" ^
    --trigger_name "daily-timer" ^
    --trigger_type "Timer" ^
    --trigger_desc "每天早上8点执行" ^
    --trigger_attr "{\"cron_expression\":\"0 0 8 * * * *\",\"enable\":true}" ^
    --region "%REGION%"

echo ✅ 定时触发器配置完成
echo.

REM 测试函数
echo 【步骤8】测试云函数...
echo   - 触发测试执行...
scf invoke --function_name "%FUNCTION_NAME%" --region "%REGION%"
echo.

REM 清理临时文件
echo 【步骤9】清理临时文件...
rmdir /s /q "%DEPLOY_DIR%"
del "%FUNCTION_NAME%.zip"
echo ✅ 清理完成
echo.

REM 完成
echo ======================================
echo ✅ 部署完成!
echo ======================================
echo.
echo 函数信息:
echo   函数名称: %FUNCTION_NAME%
echo   Region: %REGION%
echo   运行环境: %RUNTIME%
echo   内存: %MEMORY%MB
echo   超时: %TIMEOUT%秒
echo   定时执行: 每天早上8:00
echo.
echo 管理地址:
echo   https://console.cloud.tencent.com/scf/list?rid=%REGION%
echo.
echo 监控日志:
echo   https://console.cloud.tencent.com/scf/log?rid=%REGION%^&ns=default^&fn=%FUNCTION_NAME%
echo.
echo 下一步:
echo   1. 检查飞书群是否收到测试推送
echo   2. 在云函数控制台查看执行日志
echo   3. 如需修改执行时间,可在控制台调整触发器配置
echo.

pause
