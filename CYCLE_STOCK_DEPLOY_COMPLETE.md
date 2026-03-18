# 周期股买点监控系统 - 部署完成

## ✅ 部署状态

| 项目 | 状态 | 备注 |
|------|------|------|
| 主脚本 | ✅ 已部署 | `cycle_stock_monitor.py` |
| 配置文件 | ✅ 已创建 | `cycle_stock_monitor.conf` |
| 部署指南 | ✅ 已创建 | `CYCLE_STOCK_DEPLOY.md` |
| 配置向导 | ✅ 已创建 | `setup_cycle_monitor.py` |
| 自动化任务 | ✅ 已创建 | 每周一至五 17:30 (已暂停) |

---

## 📂 项目文件清单

```
c:/Users/Lenovo/WorkBuddy/20260311213700/
├── cycle_stock_monitor.py          # 主监控脚本
├── cycle_stock_monitor.conf        # 配置说明文件
├── setup_cycle_monitor.py          # 交互式配置向导
└── CYCLE_STOCK_DEPLOY.md           # 详细部署指南
```

---

## 🚀 快速开始

### 步骤1：配置参数
编辑 `cycle_stock_monitor.py`，填入你的：
- **Tushare Token**（第20行）
- **飞书 Webhook 地址**（第21行）

```python
TUSHARE_TOKEN = "your_token_here"
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/..."
```

### 步骤2：验证依赖
```bash
pip install tushare requests numpy
```

### 步骤3：测试运行
```bash
cd c:/Users/Lenovo/WorkBuddy/20260311213700
python cycle_stock_monitor.py
```

### 步骤4：启用自动化
在 WorkBuddy 自动化面板中启用"周期股买点监控"任务。

---

## 📊 监控标的说明

### 1️⃣ 合盛硅业 (603260.SH)

- **行业**：有机硅龙头
- **等待信号**：Q1扣非转正 + MA20放量突破
- **预期年报**：2026-04-30
- **当前阶段**：等待扣非拐点确认

**技术指标**：
- MA20：短期支撑/阻力
- MA60：中期支撑/阻力
- 量比：≥1.5x 为放量

### 2️⃣ 海螺水泥 (600585.SH)

- **行业**：水泥龙头
- **等待信号**：MA20放量突破
- **预期年报**：2026-03-25
- **当前阶段**：等待技术面突破

### 3️⃣ 万华化学 (600309.SH)

- **行业**：MDI龙头
- **等待信号**：缩量企稳 + 重回MA20
- **预期年报**：2026-03-28
- **当前阶段**：底部区域，观察企稳

---

## 📬 飞书推送示例

### 正常日报
```
[D] 周期股三标的日报
时间: 2026-03-18 17:32
========================================

【合盛硅业】有机硅
策略: 等Q1扣非转正+MA20突破
股价: 45.67 [UP] +1.23%
MA20: 44.50 (偏离+2.63%)
MA60: 43.20 (偏离+5.68%)
MA20方向: 拐头向上
量比: 1.2x
PE 28.5 | PB 2.34(65%分位)
信号:
  [OK] 站在MA20之上
  [火] 今日站上MA20!
  [OK] 均线多头排列
```

### 买点信号 (alert_level=3)
```
[SOS] 合盛硅业买点信号!
股价: 45.67
信号: [火火] 放量突破MA20!(量比1.8x)
策略: 等Q1扣非转正+MA20突破

请立即查看并决策!
```

---

## ⚙️ 配置文件说明

### cycle_stock_monitor.conf
包含系统架构、信号级别、指标说明等文档说明

### cycle_stock_monitor.py
主要配置项（第19-21行）：
- `TUSHARE_TOKEN`：财务数据API Key
- `FEISHU_WEBHOOK`：飞书机器人推送地址
- `STOCKS`：监控标的列表（可自定义）

---

## 🔧 常见问题

### Q: 如何修改监控标的？
A: 编辑 `STOCKS` 列表，格式如下：
```python
STOCKS = [
    {
        "code": "新代码.SH",  # 上交所.SH 深交所.SZ
        "name": "股票名称",
        "sector": "行业",
        "strategy": "策略描述",
        "earnings_date": "YYYY-MM-DD",
        "earnings_desc": "报告说明",
    }
]
```

### Q: Token 过期了怎么办？
A: 重新从 tushare.pro 获取 Token，替换脚本中的值

### Q: 飞书推送没收到？
A: 
1. 检查 Webhook URL 是否正确
2. 检查机器人是否在群组中
3. 检查群组权限设置

---

## 📅 自动化运行设置

### WorkBuddy 自动化
- **任务名称**：周期股买点监控
- **执行周期**：每周一至五 17:30
- **状态**：已创建（暂停状态）
- **工作目录**：`c:/Users/Lenovo/WorkBuddy/20260311213700`

**启动步骤**：
1. 打开 WorkBuddy 自动化面板
2. 找到"周期股买点监控"任务
3. 将状态从"PAUSED"改为"ACTIVE"

---

## 💡 使用建议

1. **首先测试**：手动运行脚本验证配置正确性
2. **逐步启用**：先启用一个标的，确认飞书推送正常
3. **关注信号**：重点关注 alert_level >= 2 的推送
4. **定期检查**：每周查看自动化任务执行日志

---

## 📞 技术支持

如遇问题，检查以下项目：
- ✅ Tushare Token 有效性
- ✅ 飞书 Webhook 正确性
- ✅ 网络连接状态
- ✅ Python 依赖包版本
- ✅ 股票代码格式 (.SH/.SZ 后缀)

---

## 🎯 下一步

1. ✅ 获取 Tushare Token
2. ✅ 获取飞书 Webhook
3. ✅ 配置脚本参数
4. ✅ 手动测试运行
5. ✅ 启用自动化任务
6. ✅ 关注飞书推送信号
7. ✅ 根据信号进行交易决策

---

**部署时间**：2026-03-18  
**脚本版本**：v1.0  
**作者**：WorkBuddy AI
