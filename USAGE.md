# 使用说明

## 快速开始

### 1. 当前工作目录
```bash
c:/Users/Lenovo/WorkBuddy/20260311213700
```

### 2. 所有依赖已安装 ✓

以下依赖包已成功安装：
- tushare (1.4.24)
- pandas (3.0.1)
- numpy (2.4.2)
- matplotlib (3.10.8)
- requests (2.32.5)
- beautifulsoup4 (4.14.3)
- lxml (6.0.2)
- jieba (0.42.1)
- pyyaml (6.0.3)

---

## 配置说明

### 必需配置（使用现金流查询和财务体检）

编辑以下两个文件，填入你的 Tushare Token：

1. `cashflow_query.py`
2. `checkup.py`

找到这一行并替换：
```python
TUSHARE_TOKEN = "你的tushare_token"
```

替换为：
```python
TUSHARE_TOKEN = "你从 tushare.pro 获取的token"
```

**获取 Tushare Token：**
1. 访问 https://tushare.pro
2. 注册账号
3. 登录后在"个人中心"获取 Token

---

### 可选配置（使用飞书推送和AI摘要）

编辑 `config.yaml`：

```yaml
# 飞书群机器人Webhook
feishu_webhook: "你的飞书webhook地址"

# DeepSeek API
llm:
  api_url: "https://api.deepseek.com/v1/chat/completions"
  api_key: "你的DeepSeek API密钥"
  model: "deepseek-chat"
```

---

## 使用示例

### 在 PowerShell 中运行

```powershell
# 进入项目目录
cd c:/Users/Lenovo/WorkBuddy/20260311213700

# 查询某股票现金流（需要先配置 Tushare Token）
python cashflow_query.py 603197

# 生成财务体检报告（需要先配置 Tushare Token）
python checkup.py 603197

# 运行热点追踪（不需要配置也可运行）
python hotspot_tracker.py

# 运行新闻简报（不需要配置也可运行）
python news_briefing.py

# 运行美股简报（不需要配置也可运行）
python us_stock_briefing.py
```

### 在 CMD 中运行

```cmd
cd c:/Users/Lenovo/WorkBuddy/20260311213700

python cashflow_query.py 603197
python checkup.py 603197
python hotspot_tracker.py
python news_briefing.py
python us_stock_briefing.py
```

---

## 输出文件说明

运行后会在当前目录或子目录生成文件：

| 工具 | 输出文件 | 位置 |
|------|---------|------|
| cashflow_query.py | `cashflow_603197.SH.png` | 当前目录 |
| checkup.py | `checkup_603197.SH.png` | 当前目录 |
| hotspot_tracker.py | `hotspot_2026-03-11.md` | `history/` |
| news_briefing.py | `2026-03-11.md` | `history/` |
| us_stock_briefing.py | `us_2026-03-11.md` | `history/` |

---

## 测试运行

### 测试热点追踪（无需配置）

```powershell
cd c:/Users/Lenovo/WorkBuddy/20260311213700
python hotspot_tracker.py
```

如果成功，会看到：
```
2026-03-11 21:50:00 [INFO] [jieba] 57 自定义词
2026-03-11 21:50:05 [INFO] [东方财富] xxx 条
2026-03-11 21:50:10 [INFO] [证券时报] xxx 条
2026-03-11 21:50:15 [INFO] [财联社] xxx 条
...
```

并在 `history/hotspot_2026-03-11.md` 生成报告。

---

## 常见错误及解决

### 错误：找不到 requirements.txt

**原因：** 不在项目目录下运行

**解决：**
```powershell
cd c:/Users/Lenovo/WorkBuddy/20260311213700
pip install -r requirements.txt
```

### 错误：ModuleNotFoundError: No module named 'xxx'

**原因：** 依赖包未安装

**解决：**
```powershell
pip install xxx
# 或者重新安装所有依赖
pip install -r requirements.txt
```

### 错误：未找到 xxx 的数据

**原因：** Tushare Token 未配置或无效

**解决：**
1. 检查 Token 是否正确填入
2. 访问 https://tushare.pro 确认 Token 是否有效
3. 检查网络连接

---

## 下一步

1. 配置 Tushare Token（如需使用现金流查询和财务体检）
2. 配置飞书 Webhook 和 DeepSeek API（可选，用于推送和AI摘要）
3. 测试运行各个工具
4. 根据需要设置定时任务

更多详情请查看 `README.md`
