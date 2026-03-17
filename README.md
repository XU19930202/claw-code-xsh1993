# 财经分析工具集

一套完整的A股市场财经分析工具，包含财务数据分析、新闻抓取、热点追踪等功能。

## 工具列表

### 1. 现金流查询 (cashflow_query.py)
查询指定股票上市以来的现金流三表数据，生成可视化报告。

**用法：**
```bash
python cashflow_query.py 603197
```

**输出：** `cashflow_603197.SH.png`

**功能：**
- 获取上市以来全部现金流数据（经营活动、投资活动、筹资活动）
- 显示历年净利润
- 自动计算年报合计
- 数值着色（正数为绿色，负数为红色）

---

### 2. 财务体检 (checkup.py)
对公司进行四维度财务体检：现金流能力、资产负债/杠杆、利润增长、估值水平。

**用法：**
```bash
python checkup.py 603197
```

**输出：** `checkup_603197.SH.png`

**评分维度：**
- 现金流能力 (5分)：经营CF/净利润、CF趋势、资金用途模式
- 资产负债 (5分)：负债率、商誉、资产类型、杠杆性质
- 利润增长 (5分)：营收增速、扣非增长、利润质量
- 估值水平 (5分)：PE、PB、PEG、历史分位

**总分：** 20分

---

### 3. 热点追踪 (hotspot_tracker.py)
每日抓取多源新闻，进行关键词提取和趋势分析，识别升温/降温的热点。

**用法：**
```bash
python hotspot_tracker.py
```

**数据源：**
- 东方财富（政策要闻、国内经济、美股导读、财经新闻）
- 证券时报
- 财联社电报

**输出：**
- `history/hotspot_2026-03-11.md` - 本地存档
- 飞书推送（需配置webhook）
- `hotspot_data/2026-03-11.json` - 历史排名数据

**功能：**
- 自定义词典（AI、算力、新质生产力等热点词）
- 停用词过滤
- 升温/降温趋势识别
- AI热点分析（需配置DeepSeek API）

---

### 4. 新闻简报 (news_briefing.py)
每日抓取证券时报电子版，生成AI摘要并推送。

**用法：**
```bash
python news_briefing.py
# 指定日期
python news_briefing.py 2026-03-10
```

**输出：**
- `history/2026-03-11.md` - 本地存档
- 飞书推送

**功能：**
- 抓取证券时报A版全部文章
- 标题过滤（过滤日常公告等）
- AI生成摘要（需配置DeepSeek API）
- 智能分板块：头条要闻、值得关注、操盘提示

---

### 5. 美股简报 (us_stock_briefing.py)
抓取美股隔夜新闻，生成对A股的影响分析。

**用法：**
```bash
python us_stock_briefing.py
```

**数据源：** 东方财富美股导读 + 美股聚焦

**输出：**
- `history/us_2026-03-11.md` - 本地存档
- 飞书推送

**功能：**
- 三大指数与市场概况
- 重要个股与板块（科技巨头、中概股）
- 宏观与政策（美联储、经济数据）
- 对今日A股的影响
- AI摘要（需配置DeepSeek API）

---

## 安装部署

### 1. 安装Python依赖

```bash
pip install -r requirements.txt
```

### 2. 配置文件

编辑 `config.yaml`，填入你的API密钥：

```yaml
# 飞书群机器人Webhook（可选）
feishu_webhook: "https://open.feishu.cn/open-apis/bot/v2/hook/你的webhook地址"

# DeepSeek API（可选，用于AI摘要）
llm:
  api_url: "https://api.deepseek.com/v1/chat/completions"
  api_key: "你的DeepSeek API密钥"
  model: "deepseek-chat"

# 抓取设置
max_full_articles: 10
```

**注意：**
- `cashflow_query.py` 和 `checkup.py` 需要在代码中配置 **Tushare Token**
- 其他工具（热点追踪、新闻简报、美股简报）如不需飞书推送和AI功能，可跳过配置

### 3. Tushare Token 配置

编辑 `cashflow_query.py` 和 `checkup.py`，找到这一行：

```python
TUSHARE_TOKEN = "你的tushare_token"
```

替换为你自己的Tushare Token（在 https://tushare.pro 注册获取）。

---

## 目录结构

```
financial-tools/
├── cashflow_query.py      # 现金流查询
├── checkup.py              # 财务体检
├── hotspot_tracker.py      # 热点追踪
├── news_briefing.py        # 新闻简报
├── us_stock_briefing.py    # 美股简报
├── config.yaml             # 配置文件
├── requirements.txt        # 依赖包
├── README.md               # 说明文档
├── history/                # 历史数据目录（自动创建）
│   ├── 2026-03-11.md
│   ├── hotspot_2026-03-11.md
│   └── us_2026-03-11.md
└── hotspot_data/           # 热点排名数据（自动创建）
    ├── 2026-03-11.json
    └── ...
```

---

## 定时任务设置

### Linux/macOS (crontab)

```bash
# 每日早上7:00运行新闻简报
0 7 * * 1-5 cd /path/to/financial-tools && /usr/bin/python3 news_briefing.py

# 每日早上7:30运行热点追踪
30 7 * * 1-5 cd /path/to/financial-tools && /usr/bin/python3 hotspot_tracker.py

# 每日早上8:00运行美股简报（周一到周五）
0 8 * * 1-5 cd /path/to/financial-tools && /usr/bin/python3 us_stock_briefing.py
```

### Windows (任务计划程序)

创建批处理脚本 `run_tasks.bat`：

```batch
@echo off
cd /d "C:\path\to\financial-tools"

echo [%date% %time%] 开始运行新闻简报
python news_briefing.py

echo [%date% %time%] 开始运行热点追踪
python hotspot_tracker.py

echo [%date% %time%] 开始运行美股简报
python us_stock_briefing.py

echo [%date% %time%] 全部完成
pause
```

然后在任务计划程序中设置每日定时运行此脚本。

---

## 云函数一键部署

一键部署到腾讯云函数,24小时自动运行,无需电脑开机。

### 快速部署

**Windows 用户**:
```powershell
# 1. 安装腾讯云CLI
pip install tencentcloud-scf

# 2. 配置腾讯云CLI (访问 https://console.cloud.tencent.com/cam/capi 获取密钥)
scf configure

# 3. 一键部署
deploy.bat
```

**Linux/macOS 用户**:
```bash
# 1. 安装腾讯云CLI
pip install tencentcloud-scf

# 2. 配置腾讯云CLI
scf configure

# 3. 一键部署
chmod +x deploy.sh
./deploy.sh
```

详细说明请查看 `DEPLOYMENT.md`

---

## 常见问题

### Q1: 提示"请先安装依赖"怎么办？

```bash
pip install -r requirements.txt
```

### Q2: 现金流查询和财务体检提示"未找到数据"？

检查：
1. Tushare Token是否正确配置
2. 股票代码是否正确（如：603197 或 603197.SH）
3. 网络连接是否正常

### Q3: 飞书推送不成功？

检查：
1. `config.yaml` 中的 `feishu_webhook` 是否正确填写
2. webhook地址是否有效
3. 网络是否可以访问飞书API

### Q4: AI摘要失败？

检查：
1. `config.yaml` 中的 `llm.api_key` 是否正确填写
2. DeepSeek API是否有效
3. 网络是否可以访问DeepSeek API

---

## 数据来源声明

- **股票数据：** Tushare (https://tushare.pro)
- **新闻数据：** 东方财富、证券时报、财联社
- **AI服务：** DeepSeek (可选)

---

## 免责声明

本工具仅供学习和参考使用，不构成任何投资建议。使用者需自行承担投资风险，数据准确性以官方披露为准。

---

## 更新日志

### v1.0 (2026-03-11)
- 初始版本发布
- 包含5个核心工具
- 支持飞书推送和AI摘要功能
