# 全板块批量回测框架

## 目标
策略收益 ÷ 股价区间涨幅 **≥ 60%** 即为合格

## 回测设定
- 区间: 2024-01-01 ~ 2025-12-31
- 板块: 创业板(300/301) + 科创板(688) + 主板(600/000)
- 每板块: 35只（分层抽样：大涨/中等/弱势各1/3）
- 初始资金: 20万

## 文件说明

| 文件 | 说明 |
|------|------|
| `adapt_guide.py` | **★ 第一步看这个** — 适配你的回测函数 |
| `batch_backtest_all_boards.py` | 主脚本 — 选股+回测+分析 |
| `generate_report.py` | 报告生成 — CSV转Excel |

## 使用步骤

### 1. 复制到项目目录
```bash
cp -r batch_backtest/ /path/to/your/project/
cd /path/to/your/project/batch_backtest/
```

### 2. 适配回测函数（关键步骤）
```bash
# 先看适配指南
python adapt_guide.py
```
根据你的 backtest() 函数签名修改 `run_single_backtest()`

### 3. 快速测试（3只股票）
```bash
python adapt_guide.py
```
确认3只测试股票都返回正常结果

### 4. 运行完整回测
```bash
python batch_backtest_all_boards.py
```
预计耗时: 30-60分钟（取决于Tushare API速度）

### 5. 生成Excel报告
```bash
python generate_report.py
```

## 输出文件

```
backtest_results/
├── gem_selected_stocks.csv      # 创业板选股清单
├── gem_backtest_detail.csv      # 创业板回测明细
├── star_selected_stocks.csv     # 科创板选股清单
├── star_backtest_detail.csv     # 科创板回测明细
├── main_selected_stocks.csv     # 主板选股清单
├── main_backtest_detail.csv     # 主板回测明细
├── all_boards_backtest_detail.csv  # 全量汇总
├── board_summary.csv            # 板块汇总
└── 回测报告_YYYYMMDD_HHMM.xlsx   # Excel报告
```

## 判定逻辑

| 场景 | 合格条件 |
|------|----------|
| 股价涨+策略盈 | 捕获率 ≥ 60% |
| 股价涨+策略亏 | ✗ 不合格 |
| 股价跌+策略盈 | ✓ 直接合格（逆势盈利） |
| 股价跌+策略亏 | 亏损 < 股价跌幅50% 视为合格 |
| 股价持平 | 策略盈利即合格 |

## 最终判定
- 总体合格率 ≥ 60% → **策略有效**，继续优化
- 总体合格率 < 60% → **需要重大调整**，分析失败案例
