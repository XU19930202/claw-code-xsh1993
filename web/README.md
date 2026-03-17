# 美股财经新闻 Web 应用

一个现代化的美股财经新闻展示应用,提供实时股票行情和新闻资讯。

## 功能特点

### 核心功能

#### 1. 实时股票行情
- 顶部滚动显示主要美股指数和热门股票
- 包含 SPY、QQQ、AAPL、MSFT、GOOGL、AMZN、NVDA、TSLA、META 等
- 实时更新价格和涨跌幅(每5秒自动刷新)
- 涨跌用颜色直观标识(绿色上涨,红色下跌)

#### 2. 新闻展示
- 卡片式布局展示财经新闻
- 包含新闻图片、标题、摘要、来源、时间和分类标签
- 支持点击查看详情(演示版本显示提示)
- 响应式布局,适配手机和桌面设备

#### 3. 分类筛选
- 全部、股市、科技、经济、加密货币五大分类
- 点击按钮快速筛选相关新闻
- 活动状态高亮显示

#### 4. 交互设计
- 卡片悬停动画效果
- 加载动画提升用户体验
- 刷新按钮手动更新新闻
- 渐变色背景,现代化设计风格

### 技术特点

- **纯前端实现**: 无需后端服务器
- **响应式设计**: 完美适配手机、平板和桌面设备
- **实时更新**: 股票价格每5秒自动刷新
- **现代化UI**: 渐变色背景、卡片阴影、流畅动画
- **易于扩展**: 可以轻松接入真实API

## 文件结构

```
web/
├── index.html      # 主HTML文件
├── styles.css      # 样式文件
├── app.js          # JavaScript逻辑文件
└── README.md       # 说明文档
```

## 使用方法

### 方法1: 直接打开文件

1. 打开 `web/` 目录
2. 双击 `index.html` 文件
3. 应用会在浏览器中打开

### 方法2: 使用本地服务器(推荐)

使用 Python 启动本地服务器:

```bash
# Python 3
cd web
python -m http.server 8000

# Python 2
cd web
python -m SimpleHTTPServer 8000
```

然后访问: `http://localhost:8000`

### 方法3: 使用 VS Code Live Server

1. 在 VS Code 中打开项目
2. 安装 "Live Server" 扩展
3. 右键点击 `index.html`
4. 选择 "Open with Live Server"

## 数据说明

### 当前状态: 模拟数据

当前应用使用的是模拟数据,仅供演示和测试使用:

- **股票数据**: 10只热门美股的模拟价格和涨跌幅
- **新闻数据**: 10条财经新闻的模拟数据
- **实时更新**: 每5秒随机更新股票价格

### 接入真实数据

要接入真实数据,需要修改 `app.js` 文件:

#### 接入股票行情API

```javascript
async function fetchStockData() {
    const response = await fetch('YOUR_STOCK_API_ENDPOINT');
    const data = await response.json();
    return data;
}
```

#### 接入新闻API

```javascript
async function fetchNewsData() {
    const response = await fetch('YOUR_NEWS_API_ENDPOINT');
    const data = await response.json();
    return data;
}
```

#### 推荐的API

**股票行情API**:
- Alpha Vantage: https://www.alphavantage.co/
- IEX Cloud: https://iexcloud.io/
- Yahoo Finance (非官方): https://github.com/pstadler/yahoo-finance-api

**新闻API**:
- NewsAPI: https://newsapi.org/
- Alpha Vantage News: https://www.alphavantage.co/news/
- Bloomberg (需要授权): https://www.bloomberg.com/professional/api/

## 自定义配置

### 修改股票列表

编辑 `app.js` 文件中的 `stockData` 数组:

```javascript
const stockData = [
    { symbol: 'SPY', price: 523.45, change: 1.23, changePercent: 0.24 },
    // 添加更多股票...
];
```

### 修改新闻数据

编辑 `app.js` 文件中的 `newsData` 数组:

```javascript
const newsData = [
    {
        id: 1,
        title: '新闻标题',
        summary: '新闻摘要',
        source: '来源',
        time: '时间',
        category: 'tech',
        image: '图片URL',
        icon: '📰'
    },
    // 添加更多新闻...
];
```

### 修改颜色主题

编辑 `styles.css` 文件中的渐变色:

```css
body {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
```

### 修改更新频率

编辑 `app.js` 文件中的 `setInterval`:

```javascript
setInterval(() => {
    // 更新逻辑...
}, 10000); // 改为10秒更新一次
```

## 浏览器兼容性

- Chrome/Edge: ✅ 完全支持
- Firefox: ✅ 完全支持
- Safari: ✅ 完全支持
- Opera: ✅ 完全支持
- IE11: ❌ 不支持(需要polyfill)

## 性能优化

当前应用已经实现了以下优化:

- ✅ CSS 动画使用 `transform` 和 `opacity` (GPU加速)
- ✅ 事件委托减少内存使用
- ✅ 懒加载图片(如果使用真实图片)
- ✅ 响应式图片适配不同设备

## 后续开发计划

### 第一阶段
- [ ] 接入真实的股票行情API
- [ ] 接入真实的新闻API
- [ ] 添加用户收藏功能
- [ ] 添加新闻搜索功能

### 第二阶段
- [ ] 添加用户登录系统
- [ ] 添加个性化推荐
- [ ] 添加推送通知
- [ ] 添加离线缓存

### 第三阶段
- [ ] 开发移动端APP
- [ ] 添加数据分析功能
- [ ] 添加社交分享功能
- [ ] 添加多语言支持

## 许可证

MIT License

## 作者

Stock News Team

## 更新日志

### v1.0.0 (2026-03-11)
- ✅ 初始版本发布
- ✅ 实时股票行情展示
- ✅ 新闻卡片展示
- ✅ 分类筛选功能
- ✅ 响应式设计
- ✅ 自动刷新功能
