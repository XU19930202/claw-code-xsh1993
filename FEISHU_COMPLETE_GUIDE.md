# 🚀 飞书推送配置完全指南

## 📌 快速概览

你的周期股监控系统已经配置好了，**只需 3 步** 就能启用飞书自动推送：

1. ✅ **脚本准备** — 已完成
2. ⏳ **配置 Webhook** — 需要你完成（5分钟）
3. ⏳ **激活自动化** — 需要你完成（1分钟）

---

## 🎯 立即开始：三步启用飞书推送

### 第1步：获取飞书 Webhook 地址（5分钟）

#### 方法 A：使用飞书应用（推荐）

1. **打开飞书开放平台**  
   https://open.feishu.cn

2. **创建应用**
   - 左侧菜单 → 应用开发 → 创建应用
   - 选择 **自建应用**
   - 输入应用名称：`周期股监控` （或其他名称）
   - 点击 **创建**

3. **配置权限**
   - 应用详情页 → 权限管理
   - 搜索并添加权限：`im:message:send_as_bot`
   - 保存

4. **获取 Webhook URL**
   - 开发配置 → 机器人
   - 找到并复制 **Webhook 地址**
   - 格式：`https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxxxxxxx`

#### 方法 B：快速测试（不需要创建应用）

如果你先想快速测试，可以：
1. 在飞书中创建一个私有群组
2. 在群组中添加「飞书机器人」
3. 获取该机器人的 Webhook 地址

---

### 第2步：配置 Webhook 到脚本（2种方法）

#### 方法 A：一键自动配置（推荐）

```bash
cd c:/Users/Lenovo/WorkBuddy/20260311213700
python setup_feishu.py
```

然后：
1. 按提示粘贴 Webhook 地址
2. 按 Enter 确认
3. 自动保存到脚本

#### 方法 B：手动编辑脚本

1. 打开文件：`cycle_stock_monitor.py`
2. 找到第 21 行：
   ```python
   FEISHU_WEBHOOK = "你的飞书Webhook地址"
   ```
3. 替换为你的地址：
   ```python
   FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/你的_token"
   ```
4. 保存文件

---

### 第3步：测试推送连接（1分钟）

运行测试脚本验证 Webhook 是否有效：

```bash
python test_feishu_webhook.py
```

然后按提示操作：
1. 输入你的 Webhook 地址
2. 脚本会发送一条测试消息到飞书
3. 检查飞书中是否收到消息

✅ **如果收到消息** — 配置成功！

❌ **如果没收到消息** — 检查：
- Webhook 地址是否正确复制
- 飞书应用权限是否完整
- 机器人是否已加入目标群组

---

## ⏰ 激活自动化任务

配置完成后，激活自动化任务让系统每日自动推送：

### 在 WorkBuddy 中激活

1. 打开 WorkBuddy
2. 左侧 → **自动化**（或 Automations）
3. 找到 **「周期股买点监控」** 任务
4. 改状态为 **ACTIVE** ✅
5. 设置触发时间（默认：每个工作日 17:30）

### 手动测试一次

激活后，可以手动运行一次确认推送：

```bash
python cycle_stock_monitor.py
```

查看输出中是否有：
```
✅ 消息已推送到飞书
```

---

## 📊 你会收到什么消息

配置完成后，每次脚本运行（每个工作日下午 5:30），飞书会收到类似这样的消息：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 周期股买点监控 | 2026-03-18 17:30
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 实时监控结果

海螺水泥 (600585) 🟡 关注
├─ 当前价: 25.07 元
├─ MA20: 25.23 元
├─ 偏离: -0.63% (即将突破!)
├─ PB值: 0.70 (历史 90% 分位)
├─ 股息: 3.79%
└─ 状态: 技术面强势，等待突破确认

合盛硅业 (603260) 🟢 可关注
├─ 当前价: 48.14 元
├─ 近期状态: 缩量整理
└─ 等待: Q1扣非转正确认

万华化学 (600309) 🔴 无
├─ 当前价: 80.15 元
├─ 状态: 缩量做底
└─ 等待: 企稳后重新入场

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ 更新时间: 2026-03-18 17:30:24
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🛠️ 常见问题排查

### Q1: 配置后还是收不到消息？

**检查清单：**
- ✓ Webhook URL 是否完整且复制正确
- ✓ 飞书应用权限是否添加了 `im:message:send_as_bot`
- ✓ 机器人是否已加入目标群组
- ✓ 网络连接是否正常
- ✓ Webhook URL 是否已过期（有些应用需要定期更新）

**解决方法：**
```bash
# 重新测试 Webhook
python test_feishu_webhook.py

# 查看脚本日志
python cycle_stock_monitor.py -v  # 如果支持详细模式
```

### Q2: 能否改变推送时间？

**可以！** 编辑自动化任务的触发时间：

在 WorkBuddy 自动化设置中：
- 现在: 每天 17:30（下午5:30）
- 改为 9:30: `FREQ=DAILY;BYHOUR=9;BYMINUTE=30`
- 改为 15:00: `FREQ=DAILY;BYHOUR=15;BYMINUTE=0`
- 多次推送: 可设置多个时间点

### Q3: 能否只在有买点信号时才推送？

**可以！** 在 `cycle_stock_monitor.py` 中修改推送条件：

```python
# 找到推送部分，改为：
if signal_level >= 1:  # 仅当信号等级 >= 1 时推送
    send_to_feishu(message)
```

### Q4: 能否推送到多个群组？

**可以！** 在飞书中：
1. 将机器人加入多个群组
2. 脚本会自动向所有包含该机器人的群组推送消息

---

## 🧠 快速命令参考

```bash
# 一键配置 Webhook
python setup_feishu.py

# 测试 Webhook 连接
python test_feishu_webhook.py

# 手动运行一次监控（并推送到飞书）
python cycle_stock_monitor.py

# 启动快速菜单（图形化界面）
python launch_menu.py

# 查看脚本帮助（如果实现了）
python cycle_stock_monitor.py --help
```

---

## 📚 相关文档

- **FEISHU_SETUP.md** — 详细飞书配置指南
- **QUICK_REFERENCE.md** — 系统快速参考卡
- **PRODUCTION_READY.md** — 生产部署说明
- **TEST_RESULT.md** — 系统测试报告

---

## 🎯 成功标志

✅ **配置成功的标志：**
1. Webhook 地址已填入脚本
2. `test_feishu_webhook.py` 能成功推送测试消息
3. 飞书中收到格式正确的监控信息
4. 自动化任务为 ACTIVE 状态

---

## 💡 使用建议

1. **先测试** — 激活前运行一次 `test_feishu_webhook.py`
2. **再激活** — 确认测试成功后激活自动化任务
3. **定期检查** — 每周查看飞书中的推送信息
4. **调整参数** — 根据实际交易结果微调监控指标

---

## 🚀 下一步

1. 获取飞书 Webhook 地址 → 运行 `setup_feishu.py`
2. 测试推送 → 运行 `test_feishu_webhook.py`
3. 激活自动化 → WorkBuddy 自动化设置
4. 坐等推送 → 每个工作日下午 5:30 收到信号

**祝你投资顺利！** 🎉

---

## 📞 需要帮助？

- 飞书开放平台文档：https://open.feishu.cn/document
- 飞书 Bot API：https://open.feishu.cn/document/ukTMukTMukTM/ucTM5YjL3ETO24yB5kDN

最后更新：2026-03-18
