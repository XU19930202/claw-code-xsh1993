# 财经分析工具集 - 快速开始指南

欢迎使用财经分析工具集!本指南将帮助你在5分钟内完成配置和使用。

---

## 📋 工具概览

| 工具 | 功能 | 自动化 |
|:---|:---|:---|
| **证券早报** | 每日A股市场新闻AI摘要 | ✅ WorkBuddy(5:00) |
| **美股隔夜简报** | 美股财经新闻AI摘要 | ✅ WorkBuddy(22:11) |
| **A股热点追踪** | 多源新闻热词分析 | ⚡ 云函数(8:00) |
| **现金流查询** | 股票现金流三表数据 | - |
| **财务体检** | 四维度财务评分 | - |
| **Web应用** | 实时股票行情+新闻 | - |

---

## 🚀 三步快速开始

### 步骤1: 安装依赖

```powershell
pip install -r requirements.txt
```

### 步骤2: 配置API

所有API已配置完成!无需额外配置。

### 步骤3: 开始使用

```powershell
# 生成证券早报
python news_briefing.py

# 生成美股隔夜简报
python us_stock_briefing.py

# 查询股票财务体检
python checkup.py 600519

# 查询股票现金流
python cashflow_query.py 600519
```

---

## ☁️ 云函数部署(推荐)

一键部署到腾讯云,24小时自动运行,无需电脑开机。

### 快速部署

```powershell
# 1. 安装腾讯云CLI
pip install tencentcloud-scf

# 2. 配置腾讯云CLI (访问 https://console.cloud.tencent.com/cam/capi 获取密钥)
scf configure

# 3. 一键部署
deploy.bat
```

详细说明: [DEPLOYMENT.md](DEPLOYMENT.md)

---

## 📱 飞书自动推送

已配置完成!每天自动推送:

- **早上5:00** - 证券早报
- **晚上22:11** - 美股隔夜简报
- **早上8:00** - A股热点追踪(云函数部署后)

---

## 🌐 Web应用

打开 `web/index.html` 查看实时股票行情和新闻。

---

## 📚 详细文档

| 文档 | 说明 |
|:---|:---|
| [README.md](README.md) | 完整项目说明 |
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | 项目总览 |
| [USAGE.md](USAGE.md) | 详细使用说明 |
| [DEPLOYMENT.md](DEPLOYMENT.md) | 云函数部署指南 |
| [API_CONFIG.md](API_CONFIG.md) | API配置报告 |
| [AUTOMATION.md](AUTOMATION.md) | 自动化任务配置 |
| [web/README.md](web/README.md) | Web应用说明 |

---

## ✅ 配置清单

- ✅ Tushare API (现金流查询、财务体检)
- ✅ DeepSeek API (AI智能摘要)
- ✅ 飞书 Webhook (自动推送)
- ✅ WorkBuddy自动化 (证券早报5:00,美股简报22:11)
- ✅ 腾讯云函数部署脚本(就绪)

---

## 🎯 常用命令

```powershell
# 新闻简报
python news_briefing.py

# 美股简报
python us_stock_briefing.py

# 热点追踪
python hotspot_tracker.py

# 财务体检
python checkup.py 600519

# 现金流查询
python cashflow_query.py 600519

# 云函数部署
deploy.bat
```

---

## 💡 使用建议

**日常使用流程**:

1. **早上5:00** - 自动收到证券早报(飞书推送)
2. **早上8:00** - 自动收到A股热点追踪(云函数)
3. **晚上22:11** - 自动收到美股隔夜简报(飞书推送)
4. **股票研究** - 使用现金流查询和财务体检工具
5. **实时行情** - 打开Web应用查看实时数据

---

## 🔧 故障排查

### 问题: 提示"未找到依赖包"

```powershell
pip install -r requirements.txt
```

### 问题: 云函数部署失败

1. 确认已安装腾讯云CLI: `pip install tencentcloud-scf`
2. 确认已配置: `scf configure`
3. 查看 [DEPLOYMENT.md](DEPLOYMENT.md) 详细说明

### 问题: 飞书推送失败

检查 `config.yaml` 中的 `feishu_webhook` 是否正确。

---

## 📞 技术支持

如有问题,请查看详细文档或提Issue。

---

**开始使用财经分析工具集,提升你的投资决策效率!**
