# 腾讯云函数部署指南 - A股热点追踪

本指南将帮助你将 A股热点追踪工具部署到腾讯云函数(SCF)。

## 📋 部署前准备

### 1. 准备腾讯云账号

- 注册腾讯云账号: https://cloud.tencent.com/
- 完成实名认证
- 确保账户有足够的余额

### 2. 安装依赖

```bash
pip install scf
```

或下载腾讯云 CLI: https://cloud.tencent.com/document/product/583/33446

### 3. 准备配置

确保以下文件已配置:
- `config.yaml` - 包含飞书 Webhook 和 DeepSeek API 密钥
- `hotspot_tracker.py` - 热点追踪主程序

## 🚀 部署方式

### 方式1: 使用腾讯云控制台(推荐)

#### 步骤1: 创建函数

1. 登录腾讯云控制台: https://console.cloud.tencent.com/scf
2. 点击"新建函数"
3. 选择"空白函数"
4. 配置函数信息:
   - **函数名称**: `a股热点追踪`
   - **地域**: 选择你所在地域(如:广州 ap-guangzhou)
   - **运行环境**: `Python 3.9`
   - **运行时内存**: `256 MB`
   - **超时时间**: `300 秒`

#### 步骤2: 上传代码

**方法A: 在线编辑(适合测试)**

1. 进入函数详情页
2. 点击"函数代码"标签
3. 创建以下文件:

**index.py** (入口文件):
```python
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from hotspot_tracker import main as tracker_main

def main_handler(event, context):
    """腾讯云函数入口"""
    result = tracker_main()
    return {
        "statusCode": 200,
        "body": str(result)
    }
```

**hotspot_tracker.py** (复制完整的程序代码)

**config.py** (配置加载):
```python
import yaml

def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
```

**config.yaml** (配置文件):
```yaml
feishu_webhook: "你的飞书Webhook地址"
llm:
  api_url: "https://api.deepseek.com/v1/chat/completions"
  api_key: "你的DeepSeek API密钥"
  model: "deepseek-chat"
```

**方法B: 上传压缩包(推荐)**

1. 本地创建部署包:
```bash
mkdir deploy_pkg
cd deploy_pkg

# 复制文件
cp ../hotspot_tracker.py .
cp ../config.yaml .
cp ../scf/index.py .
cp ../scf/config.py .

# 安装依赖
pip install jieba PyYAML requests openai -t . --no-user

# 创建目录
mkdir history
mkdir hotspot_data

# 压缩
cd ..
zip -r hotspot_tracker.zip deploy_pkg/*
```

2. 在控制台选择"本地上传zip包"
3. 上传 `hotspot_tracker.zip`

#### 步骤3: 配置函数

**入口配置**:
- **执行方法**: `index.main_handler`

**环境变量**:
- `FEISHU_WEBHOOK`: 你的飞书 Webhook 地址
- `LLM_API_KEY`: 你的 DeepSeek API 密钥

**网络配置**:
- 公网访问: 开启
- 私有网络: 可选

#### 步骤4: 配置定时触发器

1. 进入"触发管理"标签
2. 点击"创建触发器"
3. 选择"定时触发器"
4. 配置触发规则:
   - **名称**: `daily-trigger`
   - **Cron表达式**: `0 0 8 * * * *` (每天早上8点)
   - **触发周期**: 自定义触发周期

**常用 Cron 表达式**:
- 每天早上8点: `0 0 8 * * * *`
- 每天早上9点: `0 0 9 * * * *`
- 每天中午12点: `0 0 12 * * * *`
- 每天晚上8点: `0 0 20 * * * *`
- 每周一早上9点: `0 0 9 ? * 2 *`

#### 步骤5: 测试函数

1. 点击"测试"按钮
2. 查看执行日志
3. 检查飞书群是否收到推送

---

### 方式2: 使用命令行部署

#### Linux/macOS

```bash
# 进入项目目录
cd c:/Users/Lenovo/WorkBuddy/20260311213700

# 执行部署脚本
bash scf/deploy_scf.sh
```

#### Windows

```bash
# 进入项目目录
cd c:/Users/Lenovo/WorkBuddy/20260311213700

# 执行部署脚本
scf\deploy_scf.bat
```

---

## 🔧 配置说明

### 环境变量

可以在云函数中配置以下环境变量,避免将敏感信息写入代码:

| 变量名 | 说明 | 示例值 |
|:---|:---|:---|
| `FEISHU_WEBHOOK` | 飞书 Webhook 地址 | `https://open.feishu.cn/open-apis/bot/v2/hook/xxx` |
| `LLM_API_KEY` | DeepSeek API 密钥 | `sk-xxxxxxxxxxxxx` |
| `LLM_API_URL` | LLM API 地址(可选) | `https://api.deepseek.com/v1/chat/completions` |
| `LLM_MODEL` | LLM 模型名(可选) | `deepseek-chat` |

### 函数配置建议

| 配置项 | 推荐值 | 说明 |
|:---|:---|:---|
| 运行时 | Python 3.9 | 支持较新的 Python 特性 |
| 内存 | 256 MB | 足够运行热点追踪 |
| 超时时间 | 300 秒 | 5分钟足够完成抓取和分析 |
| 并发数 | 1-10 | 根据需求调整 |

---

## 📊 监控和日志

### 查看日志

1. 进入云函数详情页
2. 点击"日志查询"标签
3. 选择时间范围查询日志
4. 查看执行结果和错误信息

### 监控指标

- 调用次数
- 运行时间
- 错误率
- 内存使用

---

## 💰 成本估算

腾讯云函数计费规则:

- **调用次数**: 0.4元/百万次
- **资源使用**: 0.0000167元/GBs

**日成本估算**:
- 每天执行1次,256 MB,运行60秒
- 调用费用: 30次/月 × 0.4元/百万次 ≈ 0元
- 资源费用: 0.00025 GB × 60秒 × 30天 × 0.0000167元/GBs ≈ 0.0075元

**月成本估算**: < 0.01元

**免费额度**:
- 每月100万次调用
- 400,000 GBs资源使用

对于每天执行1次的场景,完全在免费额度内!

---

## 🔍 故障排查

### 问题1: 函数执行超时

**原因**: 网络请求时间过长

**解决**:
- 增加超时时间配置
- 检查网络连接
- 优化代码逻辑

### 问题2: 依赖包缺失

**原因**: 未正确安装依赖

**解决**:
```bash
pip install jieba PyYAML requests openai -t ./ --no-user
```

### 问题3: 飞书推送失败

**原因**: Webhook 配置错误或网络问题

**解决**:
- 检查环境变量配置
- 查看日志中的错误信息
- 测试飞书 Webhook 是否可用

### 问题4: LLM API调用失败

**原因**: API密钥错误或余额不足

**解决**:
- 检查 API 密钥配置
- 查看账户余额
- 检查 API 请求格式

---

## 📝 后续优化

### 1. 使用对象存储存储历史数据

将 `history/` 和 `hotspot_data/` 目录改为使用腾讯云 COS 存储

### 2. 添加告警功能

配置云监控告警,当函数执行失败时发送通知

### 3. 优化性能

- 使用缓存减少重复请求
- 异步处理提高效率
- 增加并发处理能力

### 4. 扩展功能

- 添加更多数据源
- 支持自定义热词词典
- 添加热词趋势分析

---

## 📚 相关文档

- [腾讯云函数官方文档](https://cloud.tencent.com/document/product/583)
- [Python运行时说明](https://cloud.tencent.com/document/product/583/11060)
- [触发器配置说明](https://cloud.tencent.com/document/product/583/18536)
- [环境变量配置](https://cloud.tencent.com/document/product/583/32747)

---

## ❓ 常见问题

**Q: 如何修改定时触发时间?**

A: 在云函数控制台的"触发管理"中,编辑或删除现有触发器,创建新的触发器并设置 Cron 表达式。

**Q: 如何查看函数执行历史?**

A: 在云函数详情页的"日志查询"中可以查看历史执行记录和日志。

**Q: 本地已经运行了,为什么还要部署到云函数?**

A: 云函数可以24小时运行,即使你的电脑关机也能自动执行,适合定时任务。

**Q: 需要维护服务器吗?**

A: 不需要。腾讯云函数是 Serverless 服务,无需管理服务器基础设施。

**Q: 可以同时部署多个工具吗?**

A: 可以。每个工具创建一个独立的云函数,分别配置定时触发器。

---

**部署状态**: ✅ 准备完成,可以开始部署

**最后更新**: 2026-03-11
