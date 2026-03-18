# 水泥行业投资决策系统 - 完整部署指南

## 🎯 系统架构

已为你部署了**两个互补的脚本**，形成完整的水泥行业投资决策系统：

```
┌─────────────────────────────────────────────────────────┐
│           水泥行业投资决策系统 (完整版)                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1️⃣ 周期监控层                                          │
│     cement_coal_tracker.py                             │
│     ├─ 动力煤期货价格 (成本端)                          │
│     ├─ 水泥价格指数 (产品端)                            │
│     └─ 海螺水泥行情 (龙头表现)                          │
│                                                         │
│  2️⃣ 估值监控层                                          │
│     conch_valuation_monitor.py                         │
│     ├─ PB估值位置 (底部回升)                            │
│     ├─ 技术面信号 (MA突破)                              │
│     └─ 基本面验证 (季报拐点)                            │
│                                                         │
│  📊 综合输出                                            │
│     ├─ 控制台显示                                      │
│     ├─ 文件保存                                        │
│     └─ 飞书推送                                        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 📍 两个脚本的位置关系

### cement_coal_tracker.py - 周期监控脚本
**职责**：监控水泥行业周期的**成本-价格-利润**链条

| 监控指标 | 作用 | 触发条件 |
|---------|------|---------|
| 动力煤价格 | 成本端 | 月跌幅>5% → 成本利好 |
| 水泥价格 | 产品端 | 价格上升 → 需求向好 |
| 海螺股价 | 利润端 | 股价表现 → 市场预期 |

**输出信号示例**：
```
煤价↓ + 水泥价↑ + 股价↑ = 周期向上信号
```

### conch_valuation_monitor.py - 估值修复脚本
**职责**：监控海螺水泥的**估值修复进度**

| 监控维度 | 作用 | 触发条件 |
|---------|------|---------|
| PB估值 | 价格端 | PB<0.8 → 低估空间大 |
| 技术面 | 确认端 | MA20突破 → 趋势转好 |
| 基本面 | 支撑端 | 利润拐点 → 增长确认 |

**输出信号示例**：
```
PB低估 + MA20拐头 + 利润上升 = 估值修复确认
```

## 🔄 协同使用流程

### 场景1：日常监控（交易日每天）

```bash
# 早盘：监控周期信号
python cement_coal_tracker.py --output morning_check.txt

# 收盘：监控估值修复进度
python conch_valuation_monitor.py --output evening_check.txt

# 对比两个文件
# cement_coal_tracker.txt    → 周期位置 (宏观)
# conch_valuation_monitor.txt → 买点确认 (微观)
```

### 场景2：信号确认（关键时期）

```
Step 1: cement_coal_tracker 显示"周期向上信号"
  └─> 煤价下降 + 水泥价上升 + PE中等

Step 2: conch_valuation_monitor 确认"估值修复"
  └─> PB低估 + MA20拐头向上 + 利润增长

Step 3: 两个脚本信号一致
  └─> ✅ 可以考虑买入操作
```

### 场景3：实时推送（关键时刻）

```bash
# 推送周期信号到飞书
python cement_coal_tracker.py --feishu --webhook "URL1"

# 推送估值修复到飞书
python conch_valuation_monitor.py --feishu --webhook "URL2"

# 或统一Webhook地址
export FEISHU_WEBHOOK="YOUR_WEBHOOK"
python cement_coal_tracker.py --feishu
python conch_valuation_monitor.py --feishu
```

## 📊 信号矩阵（两个脚本的组合判断）

### 黄金买点（同时满足）

| 周期层信号 | 估值层信号 | 综合评估 | 操作建议 |
|----------|---------|--------|--------|
| 煤价↓ PE中 | PB<0.8 MA20↑ | ✅ 黄金买点 | **强烈买入** |
| 煤价↓ PE高 | PB<0.8 MA20↑ | ✅✅ 最优买点 | **坚定买入** |
| 水泥价↑ PE中 | PB修复中 MA20↑ | ✅ 确认买点 | **可以买入** |

### 谨慎区间（只有其一）

| 周期层信号 | 估值层信号 | 综合评估 | 操作建议 |
|----------|---------|--------|--------|
| 周期向上 | 估值未明 | ⚠️ 周期确认不足 | **继续观察** |
| 周期未明 | 估值低估 | ⚠️ 周期支撑不足 | **谨慎观察** |
| 周期向下 | 估值修复 | ⚠️ 周期与估值背离 | **避免操作** |

### 避免区间（两个都弱）

| 周期层信号 | 估值层信号 | 综合评估 | 操作建议 |
|----------|---------|--------|--------|
| 煤价↑ PE低 | PB高 MA20↓ | ❌ 完全避免 | **坚决不买** |
| 水泥价↓ | PB未修复 | ❌ 双重利空 | **继续等待** |

## ⏰ 推荐使用时间表

### 工作日定时任务

```bash
# Windows 任务计划配置

# 任务1：早盘信号 (9:30)
30 9 * * 1-5 python cement_coal_tracker.py --output ${date}_morning.txt

# 任务2：收盘监控 (16:30)
30 16 * * 1-5 python cement_coal_tracker.py --output ${date}_close.txt

# 任务3：盘后分析 (17:30)
30 17 * * 1-5 python conch_valuation_monitor.py --output ${date}_valuation.txt
```

### 关键时间节点

| 日期 | 事件 | 对应脚本 | 操作 |
|------|------|---------|------|
| 每月15日 | 水泥价格发布 | cement_coal_tracker | 重点关注 |
| 每季末 | 季报披露 | conch_valuation_monitor | 基本面验证 |
| 2026-03-25 | 海螺2025年报 | conch_valuation_monitor | 利润拐点确认 |
| 2026-04-30 | 一季报截止 | conch_valuation_monitor | 增长延续验证 |

## 🛠️ 实战应用案例

### 案例：确认买点流程

```
【2026-03-18 最新状态】

Step 1: 周期层信号检查
├─ cement_coal_tracker.py 输出:
│  ├─ 动力煤: 801.4 元/吨 (月涨跌 +0.00%) ⚠️ 煤价未下行
│  ├─ 水泥价: 自动获取失败 (需手动查询)
│  ├─ 海螺PE: 15.1 (中等区间)
│  └─ 综合判断: ⚠️ 煤价上行(成本承压)
│
└─ 周期信号: ❌ 未达成 (缺少"煤价下降"这一必要条件)

Step 2: 估值层信号检查
├─ conch_valuation_monitor.py 输出:
│  ├─ PB: 0.698 (1年范围 0.601~0.772)
│  ├─ PB阶段: 🟡 低估区间(修复空间43.3%)
│  ├─ 技术面: MA20拐头向上 ✅
│  ├─ 基本面: 2025H1净利+31% ✅
│  └─ 综合得分: 3/6 (继续观察)
│
└─ 估值信号: ✅ 部分确认 (低估+基本面好，缺少MA20突破)

Step 3: 综合判断
├─ 周期层: ❌ 未完全确认 (等待煤价下行)
├─ 估值层: ⚠️ 进行中 (3/6分，需要技术面突破)
└─ 结论: 🟡 【继续观察】
   等待条件: 
   1. 煤价出现下降信号
   2. MA20放量突破25.23
   3. 2025年报验证利润拐点

Action Plan:
→ 持续监控，每日运行两个脚本
→ 当两个脚本同时给出强信号时执行买入
→ 关注2026-03-25年报披露
```

## 📱 飞书推送配置

### 推送配置

```bash
# 方法1：同时推送两个脚本的结果
python cement_coal_tracker.py --feishu --webhook "WEBHOOK_URL"
python conch_valuation_monitor.py --feishu --webhook "WEBHOOK_URL"

# 方法2：使用环境变量（推荐）
export FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
python cement_coal_tracker.py --feishu
python conch_valuation_monitor.py --feishu

# 方法3：批量脚本
# save as run_all_monitor.bat
@echo off
set FEISHU_WEBHOOK=https://open.feishu.cn/...
python cement_coal_tracker.py --feishu
python conch_valuation_monitor.py --feishu
```

## 🎓 三维分析框架

### 维度1：周期分析（cement_coal_tracker）
**时间跨度**：中期（3-6个月）
**关键指标**：
- 动力煤月涨跌 (-5% 为临界点)
- 水泥价格趋势
- PE位置

### 维度2：估值分析（conch_valuation_monitor）
**时间跨度**：中期（3-6个月）
**关键指标**：
- PB历史分位数
- MA20/MA60突破
- 季报利润增速

### 维度3：时间确认
**关键节点**：
- 季度报告发布
- 年报披露
- 产业政策出台

## 📋 检查清单

运行前验证：

```bash
# 1. 检查 Tushare 连接
python -c "import tushare; print('Tushare OK')"

# 2. 检查脚本文件
ls -la cement_coal_tracker.py conch_valuation_monitor.py

# 3. 检查依赖
pip list | grep "tushare\|numpy\|requests"

# 4. 快速测试
python cement_coal_tracker.py
python conch_valuation_monitor.py
```

## 🚀 快速开始

### 第一天

```bash
cd c:/Users/Lenovo/WorkBuddy/20260311213700

# 运行两个脚本查看当前状态
python cement_coal_tracker.py
python conch_valuation_monitor.py

# 对比两个输出，理解当前周期和估值位置
```

### 第二周

```bash
# 设置每日定时任务
# Windows 任务计划 → 创建基本任务 → 指定脚本

# 每天17:30自动运行
python cement_coal_tracker.py --output daily_cement.txt
python conch_valuation_monitor.py --output daily_valuation.txt
```

### 第一个月

```bash
# 配置飞书推送
export FEISHU_WEBHOOK=你的Webhook地址

# 运行
python cement_coal_tracker.py --feishu
python conch_valuation_monitor.py --feishu

# 在飞书群中收到每日信号
```

---

**部署完成日期**：2026-03-18  
**系统版本**：v2.0 (双脚本协同)  
**状态**：✅ 生产就绪
