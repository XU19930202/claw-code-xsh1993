# 腾讯云函数一键部署指南

## 快速开始

### Windows 用户

```powershell
# 1. 安装腾讯云CLI
pip install tencentcloud-scf

# 2. 配置腾讯云CLI (获取 SecretId 和 SecretKey)
scf configure

# 3. 运行一键部署脚本
deploy.bat
```

### Linux/macOS 用户

```bash
# 1. 安装腾讯云CLI
pip install tencentcloud-scf

# 2. 配置腾讯云CLI
scf configure

# 3. 运行一键部署脚本
chmod +x deploy.sh
./deploy.sh
```

---

## 详细步骤

### 第一步: 安装腾讯云CLI

#### Windows

安装腾讯云函数 Serverless CLI:

```powershell
npm install -g @tencent-cloud/serverless-cloud-function
```

或者使用 Python 版本:

```powershell
pip install scfcli
```

#### Linux/macOS

使用 npm:

```bash
npm install -g @tencent-cloud/serverless-cloud-function
```

或使用 Python:

```bash
pip install scfcli
```

---

### 第二步: 配置腾讯云CLI

#### 1. 获取腾讯云API密钥

1. 访问腾讯云控制台: https://console.cloud.tencent.com/cam/capi
2. 创建新密钥或使用现有密钥
3. 记录 `SecretId` 和 `SecretKey`

#### 2. 配置CLI

运行配置命令:
```powershell
scf configure
```

按提示输入:
- SecretId: 你的腾讯云 SecretId
- SecretKey: 你的腾讯云 SecretKey
- Region: 选择区域 (推荐 `ap-guangzhou` 或 `ap-shanghai`)
- AppID: 直接回车使用默认值

配置示例:
```
TencentCloud API secretId []:
AKIDxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TencentCloud API secretKey []:
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Region []:
ap-guangzhou
AppID []:
```

---

### 第三步: 运行一键部署

#### Windows

双击运行 `deploy.bat` 或在 PowerShell 中运行:
```powershell
.\deploy.bat
```

#### Linux/macOS

```bash
chmod +x deploy.sh
./deploy.sh
```

---

## 部署脚本自动完成的操作

### ✅ 步骤1: 检查环境
- 检查腾讯云CLI是否安装
- 检查配置是否正确

### ✅ 步骤2: 准备部署包
- 复制主程序代码
- 创建云函数入口文件
- 安装所有依赖包
- 创建必要目录

### ✅ 步骤3: 创建压缩包
- 打包所有文件为ZIP格式

### ✅ 步骤4: 部署到云函数
- 删除旧函数(如果存在)
- 创建新函数
- 配置运行参数

### ✅ 步骤5: 配置环境变量
- 自动读取 `config.yaml` 中的配置
- 配置飞书 Webhook
- 配置 DeepSeek API 密钥

### ✅ 步骤6: 配置定时触发器
- 设置定时触发: 每天早上8:00
- Cron表达式: `0 0 8 * * * *`

### ✅ 步骤7: 测试函数
- 触发一次测试执行
- 显示执行结果

### ✅ 步骤8: 清理临时文件
- 删除临时部署目录
- 删除压缩包

---

## 部署完成后

### 1. 查看函数信息

部署完成后,脚本会显示:
- 函数名称: `hotspot_tracker`
- Region: 你的区域
- 运行环境: Python3.9
- 内存: 256MB
- 超时: 300秒
- 定时执行: 每天早上8:00

### 2. 访问管理控制台

**云函数列表**:
```
https://console.cloud.tencent.com/scf/list?rid=ap-guangzhou
```

**函数监控和日志**:
```
https://console.cloud.tencent.com/scf/log?rid=ap-guangzhou&ns=default&fn=hotspot_tracker
```

### 3. 验证部署

1. 检查飞书群是否收到测试推送
2. 在云函数控制台查看执行日志
3. 确认定时触发器已启用

---

## 修改定时执行时间

### 方法1: 通过控制台修改

1. 打开云函数控制台
2. 找到 `hotspot_tracker` 函数
3. 点击"触发管理"
4. 编辑定时触发器
5. 修改 Cron 表达式

### 方法2: 使用CLI命令修改

```powershell
# 删除旧触发器
scf delete_trigger --function_name hotspot_tracker --trigger_name daily-timer --region ap-guangzhou

# 创建新触发器(修改cron表达式)
scf create_trigger ^
    --function_name hotspot_tracker ^
    --trigger_name daily-timer ^
    --trigger_type Timer ^
    --trigger_desc "自定义时间" ^
    --trigger_attr "{\"cron_expression\":\"0 30 9 * * * *\",\"enable\":true}" ^
    --region ap-guangzhou
```

### Cron表达式说明

格式: `秒 分 时 日 月 星期 *`

示例:
- `0 0 8 * * * *` - 每天8:00执行
- `0 30 9 * * * *` - 每天9:30执行
- `0 0 12 * * 1-5` - 工作日12:00执行
- `0 0 */6 * * * *` - 每6小时执行一次

---

## 重新部署

如果修改了代码或配置,重新运行部署脚本:

```powershell
deploy.bat
```

脚本会自动:
- 删除旧函数
- 部署新版本
- 保留配置

---

## 删除云函数

如果不再需要云函数,可以通过以下方式删除:

### 方法1: 控制台删除

1. 打开云函数控制台
2. 找到函数
3. 点击"删除"

### 方法2: CLI命令删除

```powershell
scf delete_function --function_name hotspot_tracker --region ap-guangzhou
```

---

## 常见问题

### Q1: 提示"未检测到腾讯云CLI"

**A**: 需要先安装腾讯云CLI
```powershell
pip install tencentcloud-scf
```

### Q2: 提示"配置未找到"

**A**: 需要配置腾讯云CLI
```powershell
scf configure
```

### Q3: 部署时提示权限错误

**A**: 检查 SecretId 和 SecretKey 是否正确,确保账号有云函数操作权限

### Q4: 函数执行失败

**A**: 
1. 查看云函数控制台日志
2. 检查环境变量是否配置正确
3. 确认飞书 Webhook 是否有效

### Q5: 没有收到飞书推送

**A**:
1. 检查函数执行日志
2. 确认飞书 Webhook 地址正确
3. 确认飞书机器人未被禁用

---

## 成本说明

**完全免费!**

- 腾讯云函数免费额度: 100万次/月
- 本工具每天执行1次,每月约30次
- 远低于免费额度,无需担心费用

---

## 技术支持

如有问题,请参考:
- 腾讯云文档: https://cloud.tencent.com/document/product/583
- 云函数控制台: https://console.cloud.tencent.com/scf

---

## 部署脚本文件说明

| 文件 | 说明 |
|:---|:---|
| `deploy.bat` | Windows一键部署脚本 |
| `deploy.sh` | Linux/macOS一键部署脚本 |
| `DEPLOYMENT.md` | 本部署说明文档 |
