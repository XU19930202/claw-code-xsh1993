# 水泥-煤炭行业周期追踪部署指南

## 📋 部署完成

已将 `cement_coal_tracker.py` 部署到项目目录。

## 🚀 快速启动

### 1. 手动运行（查看实时数据）

```bash
cd c:/Users/Lenovo/WorkBuddy/20260311213700
python cement_coal_tracker.py
```

**输出示例：**
```
📊 水泥行业周期追踪 | 2025-03-18 14:30
====================================

🔥 【动力煤期货】
  收盘价: 825.5 元/吨 🔴 +1.20%
  日内: 823.0 - 830.0
  周涨跌: +2.50%
  月涨跌: -3.20%
  💡 煤价月跌幅>5%，利好水泥企业利润

🏗️ 【水泥价格指数】
  (数据获取中...)

🐚 【海螺水泥 600585】
  股价: 45.80 🟢 -0.50%
  PE(TTM): 12.5 (中等区间)
  PB: 1.8
  股息率: 2.50%
  MA20: 46.20 (当前跌破MA20)
  周涨跌: -1.20%
  月涨跌: +3.50%

📋 【周期位置综合判断】
  ✅ 煤价下行(成本利好)
  ➡️ PE中等(周期中段)
  ⚠️ 跌破MA20(短期趋势偏弱)
```

### 2. 推送到飞书（需配置Webhook）

```bash
# 方式A：指定Webhook地址
python cement_coal_tracker.py --feishu --webhook "https://open.feishu.cn/open-apis/bot/v2/hook/..."

# 方式B：通过环境变量（推荐用于自动化）
set FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/...
python cement_coal_tracker.py --feishu
```

## 📅 定时任务配置

### Windows 任务计划

**方案1：使用Python脚本包装**

创建 `run_cement_tracker.bat`：

```batch
@echo off
cd c:\Users\Lenovo\WorkBuddy\20260311213700

REM 每天17:30运行一次，推送到飞书
set FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_WEBHOOK_HERE

python cement_coal_tracker.py --feishu

REM 可选：记录日志
echo [%date% %time%] Cement tracker run completed >> cement_tracker.log
```

在 Windows 任务计划中配置：
- **触发时间**：每天 17:30（工作日 1-5）
- **执行程序**：`cmd.exe`
- **参数**：`/c "c:\path\to\run_cement_tracker.bat"`
- **运行用户**：当前用户

### Linux/Mac 定时任务

在 crontab 中添加：

```cron
# 每天17:30运行（工作日1-5）
30 17 * * 1-5 cd /path/to/project && python cement_coal_tracker.py --feishu
```

## 🔑 依赖项

**已有的：**
- ✅ `tushare` - 已在项目中配置，使用 `config.py` 中的 Token
- ✅ `requests` - 标准库
- ✅ `pandas` - Tushare 的依赖

**需要验证：**
```bash
pip list | find /i "tushare requests pandas"
```

如果缺失，运行：
```bash
pip install tushare requests
```

## 🎯 跟踪指标说明

### 动力煤期货 (ZC.ZCE)
- **周期性**：成本端的直接体现
- **关键指标**：
  - 月环比 < -5% → 成本下降，利好水泥企业
  - 月环比 > +5% → 成本上升，水泥企业承压

### 水泥价格指数
- **数据源**：百年建筑网 / 中国水泥网
- **关键价格**：P.O42.5散装水泥均价（全国平均）
- **自动获取失败时**：需手动查看
  - 中国水泥网：www.ccement.com
  - 百年建筑网：www.100njz.com

### 海螺水泥 (600585)
- **关键指标**：
  - **PE(TTM) > 20**：利润在底部，关注反转拐点 → 买点信号
  - **PE(TTM) < 10**：利润在高位，注意见顶风险 → 卖点信号
  - **MA20**：短期趋势判断
  - **股息率**：现金回报

## 💡 周期研判模型

**三维研判框架：**

```
煤价走势    水泥价格    PE位置         结论
─────────────────────────────────────────────
↓ 下行      ↑ 上行      高位(>18)      ✅ 买入信号强
↓ 下行      ↑ 上行      中等           ✅ 买入信号
↓ 下行      ↑ 上行      低位(<10)      ⚠️ 谨慎，市场已调整

↑ 上行      ↓ 下行      低位(<10)      ⚠️ 卖出信号
↑ 上行      ↓ 下行      中等           ⚠️ 卖出信号弱
↑ 上行      ↓ 下行      高位(>20)      ❌ 避免（最坏）
```

**核心逻辑：**
- 周期股看**拐点**，不看绝对PE高低
- 煤价下降 + 水泥价上升 + PE在顶部 = 最佳买点
- 关注**扣非利润**拐点（从财报中提取）

## 📊 与其他工具的协作

### 与现金流分析的连接

完成追踪后，可进一步深化分析：

```bash
# 深度分析海螺水泥的现金流
python skill1_cashflow_fetch.py 600585

# 获取并购重组事件（成本端变化的驱动因素）
python skill3_ma_events_fetch.py 600585.SH
```

### 与投资决策的连接

当周期信号转强时，使用 `trading-analysis` 进行完整投资研判：

```bash
# 完整的投资分析（多角色辩论）
# 使用 trading-analysis skill（需在 WorkBuddy IDE 中调用）
```

## 🔍 故障排查

### 问题1：Tushare 数据获取失败

**症状：** 显示 "⚠️ 数据获取失败"

**排查步骤：**
```bash
# 验证Token是否有效
python -c "import tushare as ts; ts.set_token('你的Token'); print(ts.pro_api().daily(ts_code='600585.SH', start_date='20250301', end_date='20250318'))"
```

**常见原因：**
- Token 已过期（需重新申请）
- 网络连接问题
- Tushare API 额度已用尽（免费版有限制）

### 问题2：飞书推送失败

**症状：** 显示 "❌ 飞书推送失败"

**排查步骤：**
```bash
# 测试Webhook地址
python -c "
import requests
webhook = 'https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_WEBHOOK'
msg = {'msg_type': 'text', 'content': {'text': 'Test message'}}
resp = requests.post(webhook, json=msg)
print(f'Status: {resp.status_code}')
print(f'Response: {resp.json()}')
"
```

**常见原因：**
- Webhook 地址格式错误
- 机器人权限设置不当
- 网络代理问题

### 问题3：水泥价格指数获取失败

**症状：** "⚠️ 自动获取失败"

**说明：** 这是正常的，第三方网站API可能变化。需要手动查看：
- 中国水泥网：www.ccement.com
- 百年建筑网：www.100njz.com

## 📝 日志和监控

**建议添加日志记录：**

```python
# 在脚本运行前添加日志配置
import logging
logging.basicConfig(
    filename='cement_tracker.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```

## 🎓 最佳实践

1. **定期检查信号变化**
   - 每周查看一次综合判断
   - 关注拐点变化

2. **结合其他数据**
   - 参考行业新闻（产能政策、环保政策）
   - 关注上游（煤炭供给）和下游（房地产）

3. **多指标验证**
   - 不要仅基于单一指标决策
   - 结合基本面分析（见cashflow分析）
   - 关注技术面（MA、MACD）

4. **自动化 + 人工review**
   - 让脚本自动推送到飞书
   - 人工review信号的可信度
   - 结合实盘的其他考量

## 📚 参考资源

- **Tushare 文档**：https://tushare.pro
- **飞书机器人文档**：https://open.feishu.cn/document/client-docs/bot/

---

**部署日期**：2025-03-18  
**脚本版本**：v1.0  
**维护者**：AI Assistant
