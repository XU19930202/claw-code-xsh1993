# 财经分析工具集 - 项目总览

一个功能强大的 A股和美股财经分析工具集,包含 Python 命令行工具和现代化 Web 应用。

## 📁 项目结构

```
c:/Users/Lenovo/WorkBuddy/20260311213700/
├── 核心工具 (Python脚本)
│   ├── cashflow_query.py      # 现金流查询工具
│   ├── checkup.py              # 财务体检报告工具
│   ├── hotspot_tracker.py       # A股热点追踪工具
│   ├── news_briefing.py         # 证券时报新闻简报工具
│   └── us_stock_briefing.py     # 美股隔夜简报工具
│
├── Web应用
│   ├── web/
│   │   ├── index.html           # 主页面
│   │   ├── styles.css           # 样式文件
│   │   ├── app.js               # JavaScript逻辑
│   │   └── README.md            # Web应用说明文档
│   │
├── 配置文件
│   ├── config.yaml              # 统一配置文件
│   └── requirements.txt         # Python依赖包
│
├── 文档
│   ├── README.md                # 项目说明文档
│   ├── QUICKSTART.md            # 快速开始指南
│   ├── USAGE.md                 # 详细使用说明
│   ├── API_CONFIG.md            # API配置完成报告
│   ├── AUTOMATION.md            # 自动化任务配置文档
│   └── PROJECT_OVERVIEW.md      # 项目总览(本文件)
│
├── 数据目录
│   ├── history/                 # 历史报告存储目录
│   └── hotspot_data/            # 热点排名数据存储目录
│
└── 部署脚本
    ├── deploy.bat                # Windows自动部署脚本
    └── deploy.sh                # Linux/macOS自动部署脚本
```

## 🛠️ 工具列表

### 1. 新闻简报工具

**文件**: `news_briefing.py`

**功能**:
- 抓取证券时报电子版当日新闻
- 使用 DeepSeek AI 生成智能摘要
- 自动推送到飞书群(已配置)
- 本地保存 Markdown 格式报告

**输出**: `history/YYYY-MM-DD.md`

**使用**:
```bash
python news_briefing.py
```

**自动化**: 每天早上 5:00 自动执行

---

### 2. 美股隔夜简报工具

**文件**: `us_stock_briefing.py`

**功能**:
- 抓取东方财富美股导读和美股聚焦
- 使用 DeepSeek AI 生成智能摘要
- 自动推送到飞书群(已配置)
- 本地保存 Markdown 格式报告

**输出**: `history/us_YYYY-MM-DD.md`

**使用**:
```bash
python us_stock_briefing.py
```

**自动化**: 每天晚上 22:11 自动执行

---

### 3. A股热点追踪工具

**文件**: `hotspot_tracker.py`

**功能**:
- 抓取东方财富、证券时报、财联社新闻
- 使用 jieba 分词进行热词统计
- 使用 DeepSeek AI 生成热点分析
- 自动推送到飞书群(已配置)
- 本地保存 Markdown 格式报告

**输出**: `history/hotspot_YYYY-MM-DD.md`

**使用**:
```bash
python hotspot_tracker.py
```

---

### 4. 现金流查询工具

**文件**: `cashflow_query.py`

**功能**:
- 查询 A股股票上市以来完整的现金流三表
- 经营活动、投资活动、筹资活动现金流
- 净利润对比分析
- 生成可视化 PNG 报告

**输出**: `cashflow_{股票代码}.png`

**使用**:
```bash
python cashflow_query.py 600519
```

**需要**: Tushare API Token

---

### 5. 财务体检报告工具

**文件**: `checkup.py`

**功能**:
- 四维度财务分析:现金流能力、资产负债、利润增长、估值水平
- 自动评分(每维度5分,总分20分)
- 生成可视化 PNG 报告
- 专业的财务结论

**输出**: `checkup_{股票代码}.png`

**使用**:
```bash
python checkup.py 600519
```

**需要**: Tushare API Token

---

### 6. 美股财经新闻 Web 应用

**目录**: `web/`

**功能**:
- 实时股票行情滚动显示(每5秒自动更新)
- 卡片式新闻展示
- 分类筛选(全部、股市、科技、经济、加密货币)
- 响应式设计,适配手机和桌面
- 刷新按钮手动更新

**使用**:
1. 双击 `web/index.html` 直接打开
2. 或使用本地服务器: `python -m http.server 8000`
3. 访问 `http://localhost:8000`

**当前状态**: 使用模拟数据,可接入真实API

---

## ⚙️ 配置状态

### 已配置的 API

| API | 状态 | 配置文件 | 用途 |
|:---|:---|:---|:---|
| **Tushare** | ✅ 已配置 | `cashflow_query.py`, `checkup.py` | A股数据查询 |
| **DeepSeek** | ✅ 已配置 | `config.yaml` | AI智能摘要 |
| **飞书 Webhook** | ✅ 已配置 | `config.yaml` | 自动推送报告 |

### 已配置的自动化任务

| 任务 | 执行时间 | 工具 | 状态 |
|:---|:---|:---|:---|
| **证券早报推送** | 每天 5:00 | `news_briefing.py` | 🟢 已激活 |
| **美股隔夜简报推送** | 每天 22:11 | `us_stock_briefing.py` | 🟢 已激活 |

---

## 📊 数据流

### 新闻简报流程
```
证券时报网站 → 抓取新闻 → DeepSeek AI摘要 → 推送到飞书 → 保存到本地
```

### 美股隔夜简报流程
```
东方财富网站 → 抓取美股新闻 → DeepSeek AI摘要 → 推送到飞书 → 保存到本地
```

### A股热点追踪流程
```
三大财经网站 → 抓取新闻 → jieba分词统计 → DeepSeek AI分析 → 推送到飞书 → 保存到本地
```

### 财务体检流程
```
用户输入股票代码 → Tushare API获取数据 → 四维度分析 → 生成PNG报告
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd c:/Users/Lenovo/WorkBuddy/20260311213700
pip install -r requirements.txt
```

### 2. 运行工具

```bash
# 生成证券早报
python news_briefing.py

# 生成美股隔夜简报
python us_stock_briefing.py

# A股热点追踪
python hotspot_tracker.py

# 查询股票现金流
python cashflow_query.py 600519

# 财务体检
python checkup.py 600519
```

### 3. 打开 Web 应用

```bash
# 方法1: 直接打开
双击 web/index.html

# 方法2: 本地服务器
cd web
python -m http.server 8000
# 访问 http://localhost:8000
```

---

## 📚 文档索引

- **README.md** - 项目完整说明文档
- **QUICKSTART.md** - 快速开始指南
- **USAGE.md** - 详细使用说明
- **API_CONFIG.md** - API配置完成报告
- **AUTOMATION.md** - 自动化任务配置文档
- **web/README.md** - Web应用说明文档

---

## 🎯 使用场景

### 场景1: 每日晨间阅读
- 每天早上5点自动收到证券早报
- 每天早上打开 Web 应用查看实时股票行情

### 场景2: 晚间美股分析
- 每天晚上22:11自动收到美股隔夜简报
- 了解美股走势,为次日交易做准备

### 场景3: 股票研究
- 使用现金流查询工具查看历史现金流数据
- 使用财务体检工具了解股票财务状况

### 场景4: 市场热点追踪
- 运行热点追踪工具了解当前市场热点
- 通过热词排名发现投资机会

---

## 📈 项目特色

1. **AI赋能**: 使用 DeepSeek AI 自动生成专业级摘要
2. **自动化**: 定时任务自动推送,无需手动操作
3. **可视化**: 财务报告自动生成图表,直观易读
4. **多平台**: Python 命令行工具 + Web 应用
5. **实时性**: 股票行情每5秒自动更新

---

## 🔧 技术栈

- **Python 3.x**: 核心工具开发
- **HTML/CSS/JavaScript**: Web 应用开发
- **DeepSeek API**: AI 智能摘要
- **Tushare API**: A股数据查询
- **飞书 API**: 消息推送
- **jieba**: 中文分词
- **matplotlib**: 数据可视化

---

## 📝 版本历史

### v1.0.0 (2026-03-11)
- ✅ 创建5个核心工具
- ✅ 配置所有 API
- ✅ 设置2个自动化任务
- ✅ 开发 Web 应用
- ✅ 完成所有文档

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request!

---

**项目状态**: ✅ 完全配置,可正常使用

**最后更新**: 2026-03-11
