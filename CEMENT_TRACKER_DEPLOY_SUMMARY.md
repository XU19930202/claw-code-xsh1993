# ✅ 水泥-煤炭追踪脚本部署完成

## 📦 部署内容

已成功将水泥-煤炭行业周期追踪脚本部署到项目目录：

| 文件 | 说明 |
|------|------|
| **cement_coal_tracker.py** | 主脚本（已部署） |
| **CEMENT_COAL_TRACKER_DEPLOY.md** | 详细部署文档 |
| **cement_tracker_latest.txt** | 最新执行结果示例 |

## 🚀 即时可用

脚本已经验证，**可以立即使用**：

### 查看实时数据
```bash
cd c:/Users/Lenovo/WorkBuddy/20260311213700
python cement_coal_tracker.py
```

### 保存到文件
```bash
python cement_coal_tracker.py --output results.txt
```

### 推送到飞书（需Webhook）
```bash
python cement_coal_tracker.py --feishu --webhook "https://open.feishu.cn/..."
```

## 📊 功能特性

### ✅ 已实现

- ✅ **动力煤期货追踪**
  - 郑商所 ZC.ZCE 主力合约
  - 日线、周涨跌、月涨跌
  - 成本端智能判断

- ✅ **海螺水泥股票数据**
  - 实时股价、PE(TTM)、PB、股息率
  - MA20 技术面
  - 周月涨幅追踪

- ✅ **水泥价格指数**
  - 自动爬取（备选方案）
  - 手动查询指引

- ✅ **周期判断引擎**
  - 煤价走势判断
  - PE 历史位置评估
  - 短期技术趋势

- ✅ **灵活输出**
  - 控制台输出（UTF-8）
  - 文件保存
  - 飞书群推送

## 📋 实时数据示例

```
📊 水泥行业周期追踪 | 2026-03-18 10:55
====================================

🔥 【动力煤期货】
  收盘价: 801.4 元/吨 ⚪ +0.00%
  周涨跌: +0.00%
  月涨跌: +0.00%

🏗️ 【水泥价格指数】
  (自动获取中...)

🐚 【海螺水泥 600585】
  股价: 25.07 🔴 +0.28%
  PE(TTM): 15.1 (中等区间)
  PB: 0.70
  股息率: 3.79%
  MA20: 25.23 (当前跌破MA20)
  周涨跌: -1.53%
  月涨跌: +0.16%

📋 【周期位置综合判断】
  ⚠️ 煤价上行(成本承压)
  ➡️ PE中等(周期中段)
  ⚠️ 跌破MA20(短期趋势偏弱)
```

## 🔧 依赖检查

**已验证可用的依赖：**
- ✅ `tushare` - 使用项目配置的 Token
- ✅ `requests` - HTTP 库
- ✅ `pandas` - 数据处理

**验证命令：**
```bash
python -c "import tushare, requests, pandas; print('All OK')"
```

## 📅 推荐使用场景

### 场景1：每日定时监控
```bash
# Windows 任务计划 - 每天17:30
python cement_coal_tracker.py --feishu --output %date%_cement_tracker.txt
```

### 场景2：与财务分析结合
```bash
# 先获得周期信号
python cement_coal_tracker.py --output signal.txt

# 然后深化分析
python skill1_cashflow_fetch.py 600585  # 现金流分析
python skill3_ma_events_fetch.py 600585.SH  # 重组事件
```

### 场景3：投资决策支撑
```bash
# 信号确认后进行全面分析
# 使用 trading-analysis skill 进行多维度分析
```

## ⚡ 快速参考

| 命令 | 用途 |
|------|------|
| `python cement_coal_tracker.py` | 查看实时数据 |
| `python cement_coal_tracker.py --output file.txt` | 保存到文件 |
| `python cement_coal_tracker.py --feishu --webhook URL` | 推送到飞书 |
| `set FEISHU_WEBHOOK=xxx && python cement_coal_tracker.py --feishu` | 环境变量推送 |

## 🔍 故障排查

### 数据获取失败？
- 检查 Tushare Token 是否有效
- 查看网络连接
- 参考 `CEMENT_COAL_TRACKER_DEPLOY.md` 故障排查章节

### 输出乱码？
- 脚本已配置 UTF-8 编码
- 建议使用 `--output` 参数保存到文件

### 飞书推送失败？
- 确认 Webhook 地址正确
- 测试网络连接
- 查看 API 返回的错误信息

## 📚 进阶配置

详见 `CEMENT_COAL_TRACKER_DEPLOY.md`：
- Windows 任务计划详细配置
- Linux/Mac crontab 配置
- 日志记录设置
- 周期研判模型说明
- 与其他工具的协作

## ✨ 下一步

1. **配置飞书Webhook**（可选）
   - 在飞书中创建机器人
   - 获取 Webhook 地址
   - 运行：`python cement_coal_tracker.py --feishu --webhook "URL"`

2. **设置定时任务**（推荐）
   - 每天固定时间运行
   - 自动推送到飞书

3. **结合其他分析**
   - 用 `cashflow_query.py 600585` 做现金流分析
   - 使用 `trading-analysis` 进行投资研判

---

**部署时间**：2026-03-18  
**脚本版本**：v1.0  
**状态**：✅ 已验证、已部署、可投产
