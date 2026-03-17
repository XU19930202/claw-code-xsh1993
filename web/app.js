// 模拟股票数据
const stockData = [
    { symbol: 'SPY', price: 523.45, change: 1.23, changePercent: 0.24 },
    { symbol: 'QQQ', price: 468.92, change: 2.15, changePercent: 0.46 },
    { symbol: 'AAPL', price: 178.52, change: 3.21, changePercent: 1.83 },
    { symbol: 'MSFT', price: 425.67, change: -1.89, changePercent: -0.44 },
    { symbol: 'GOOGL', price: 178.23, change: 2.45, changePercent: 1.40 },
    { symbol: 'AMZN', price: 185.78, change: 4.12, changePercent: 2.27 },
    { symbol: 'NVDA', price: 924.56, change: 15.78, changePercent: 1.74 },
    { symbol: 'TSLA', price: 173.89, change: -5.67, changePercent: -3.16 },
    { symbol: 'META', price: 505.32, change: 8.45, changePercent: 1.70 },
    { symbol: 'AMD', price: 180.23, change: 6.34, changePercent: 3.65 },
];

// 模拟新闻数据
const newsData = [
    {
        id: 1,
        title: '英伟达GTC大会即将召开,AI算力板块迎来催化',
        summary: '英伟达年度开发者大会(GTC 2026)将于3月16日至19日举行,业内预计将展示多项前沿突破,CPO技术商业化落地有望成为本次大会的关键节点。',
        source: '财联社',
        time: '2小时前',
        category: 'tech',
        image: null,
        icon: '🤖'
    },
    {
        id: 2,
        title: '美股三大指数窄幅震荡,科技股表现分化',
        summary: '美股隔夜呈现窄幅震荡格局,甲骨文大涨超10%表现突出。市场静待英伟达GTC大会及美联储货币政策会议纪要。',
        source: '东方财富',
        time: '4小时前',
        category: 'market',
        image: null,
        icon: '📊'
    },
    {
        id: 3,
        title: '国际油价巨震,能源板块波动加大',
        summary: '受霍尔木兹海峡局势影响,国际油价上演"过山车"行情。IEA据悉提议史上最大规模战略石油储备释放,超过1.82亿桶。',
        source: '证券时报',
        time: '5小时前',
        category: 'economy',
        image: null,
        icon: '🛢️'
    },
    {
        id: 4,
        title: 'OpenRouter监测:中国大模型周调用量环比大增35%',
        summary: '上周(3月2日至3月8日)上榜大模型中,中国大模型的周调用量上升至4.19万亿Token,较前一周大幅增长34.9%。',
        source: '东方财富',
        time: '6小时前',
        category: 'tech',
        image: null,
        icon: '🚀'
    },
    {
        id: 5,
        title: '1.6T光模块迎首个规模化商用订单',
        summary: '美国光通信技术公司AOI公告称,已收到一家长期主要超大规模客户的1.6T数据中心光收发器首批量产订单,订单金额超2亿美元。',
        source: '财联社',
        time: '8小时前',
        category: 'tech',
        image: null,
        icon: '💡'
    },
    {
        id: 6,
        title: '比特币突破75,000美元,加密货币市场回暖',
        summary: '加密货币市场近期表现强劲,比特币价格突破75,000美元关口,以太坊同样表现亮眼,市场情绪持续改善。',
        source: 'CoinDesk',
        time: '10小时前',
        category: 'crypto',
        image: null,
        icon: '₿'
    },
    {
        id: 7,
        title: '中概股表现分化,新能源汽车股上涨',
        summary: '中概股隔夜表现分化,蔚来大涨14%(财报显示首次实现盈利),理想汽车、小鹏汽车亦有不同程度上涨。',
        source: '东方财富',
        time: '12小时前',
        category: 'market',
        image: null,
        icon: '🚗'
    },
    {
        id: 8,
        title: '美联储3月利率决议前瞻',
        summary: '市场普遍预期美联储将在3月会议上维持利率不变,但投资者将密切关注会议纪要中关于未来政策路径的线索。',
        source: '路透社',
        time: '14小时前',
        category: 'economy',
        image: null,
        icon: '🏦'
    },
    {
        id: 9,
        title: 'CPO概念再度走强,算力需求持续爆发',
        summary: '算力硬件方向延续升势,CPO概念股集体拉升。瑞斯康达收获两连板,沃格光电涨停,华工科技、光迅科技等多股跟涨。',
        source: '东方财富',
        time: '16小时前',
        category: 'tech',
        image: null,
        icon: '⚡'
    },
    {
        id: 10,
        title: 'Micro LED概念领涨,光进铜退趋势加速',
        summary: '随着生成式AI兴起,数据中心对高速传输的需求持续提升,Micro LED CPO方案有望凭节能优势成为光互连替代方案。',
        source: '东方财富',
        time: '18小时前',
        category: 'tech',
        image: null,
        icon: '💎'
    },
];

// 类别映射
const categoryMap = {
    market: '股市',
    tech: '科技',
    economy: '经济',
    crypto: '加密货币'
};

// 渲染股票行情
function renderStockTicker() {
    const tickerContainer = document.getElementById('stockTicker');
    const tickerHTML = stockData.map(stock => `
        <div class="ticker-item">
            <span class="ticker-symbol">${stock.symbol}</span>
            <span class="ticker-price">$${stock.price.toFixed(2)}</span>
            <span class="ticker-change ${stock.change >= 0 ? 'positive' : 'negative'}">
                ${stock.change >= 0 ? '+' : ''}${stock.changePercent.toFixed(2)}%
            </span>
        </div>
    `).join('');

    tickerContainer.innerHTML = tickerHTML + tickerHTML; // 重复一遍实现循环滚动
}

// 渲染新闻卡片
function renderNewsCards(filter = 'all') {
    const newsContainer = document.getElementById('newsContainer');
    const filteredNews = filter === 'all' 
        ? newsData 
        : newsData.filter(news => news.category === filter);

    const cardsHTML = filteredNews.map(news => `
        <div class="news-card" onclick="showNewsDetail(${news.id})">
            <div class="news-card-image">
                ${news.image ? `<img src="${news.image}" alt="${news.title}">` : `<span class="placeholder-icon">${news.icon}</span>`}
            </div>
            <div class="news-card-content">
                <span class="news-card-category">${categoryMap[news.category]}</span>
                <h3 class="news-card-title">${news.title}</h3>
                <p class="news-card-summary">${news.summary}</p>
                <div class="news-card-meta">
                    <span class="news-card-source">${news.source}</span>
                    <span class="news-card-time">${news.time}</span>
                </div>
            </div>
        </div>
    `).join('');

    newsContainer.innerHTML = cardsHTML;
}

// 显示新闻详情(演示版本)
function showNewsDetail(newsId) {
    const news = newsData.find(n => n.id === newsId);
    alert(`📰 ${news.title}\n\n${news.summary}\n\n来源: ${news.source}\n发布时间: ${news.time}\n\n(演示版本 - 实际应用将显示完整新闻页面)`);
}

// 初始化筛选按钮
function initFilterButtons() {
    const filterButtons = document.querySelectorAll('.filter-btn');

    filterButtons.forEach(button => {
        button.addEventListener('click', () => {
            // 移除所有活动状态
            filterButtons.forEach(btn => btn.classList.remove('active'));
            // 添加当前按钮活动状态
            button.classList.add('active');
            // 筛选新闻
            const filter = button.dataset.filter;
            renderNewsCards(filter);
        });
    });
}

// 刷新按钮
function initRefreshButton() {
    const refreshBtn = document.getElementById('refreshBtn');

    refreshBtn.addEventListener('click', () => {
        const loadingOverlay = document.getElementById('loadingOverlay');
        loadingOverlay.classList.remove('hidden');

        // 模拟加载延迟
        setTimeout(() => {
            // 随机更新股票价格
            stockData.forEach(stock => {
                const change = (Math.random() - 0.5) * 2;
                stock.price += change;
                stock.change += (Math.random() - 0.5) * 0.5;
                stock.changePercent = (stock.change / stock.price) * 100;
            });

            renderStockTicker();
            renderNewsCards();
            loadingOverlay.classList.add('hidden');

            // 显示成功提示
            showToast('✅ 新闻已刷新!');
        }, 1500);
    });
}

// 显示提示消息
function showToast(message) {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 15px 25px;
        border-radius: 10px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);

    // 3秒后自动移除
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// 添加动画样式
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// 自动更新股票价格
function startAutoUpdate() {
    setInterval(() => {
        // 随机更新股票价格
        stockData.forEach(stock => {
            const change = (Math.random() - 0.5) * 0.5;
            stock.price += change;
            stock.change += (Math.random() - 0.5) * 0.1;
            stock.changePercent = (stock.change / stock.price) * 100;
        });

        renderStockTicker();
    }, 5000); // 每5秒更新一次
}

// 初始化页面
function init() {
    renderStockTicker();
    renderNewsCards();
    initFilterButtons();
    initRefreshButton();
    startAutoUpdate();

    // 隐藏加载动画
    setTimeout(() => {
        const loadingOverlay = document.getElementById('loadingOverlay');
        loadingOverlay.classList.add('hidden');
    }, 1000);
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', init);
