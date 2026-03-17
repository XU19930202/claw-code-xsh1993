"""
并购公告全文分析模块
──────────────────────
从巨潮资讯网下载核心并购公告PDF → 提取文本 → DeepSeek结构化提取

只分析"核心公告"，跳过进展/回复/法律意见等噪音：
  核心公告 = 预案、草案、报告书、收购协议、交割公告

依赖安装：
  pip install pdfplumber requests

用法：
    # 独立运行（测试）
    python ma_pdf_analyzer.py 603197

    # 被skill3调用
    from ma_pdf_analyzer import analyze_ma_pdfs
    df_enriched = analyze_ma_pdfs(df_ma_events, verbose=True)
"""

import os
import sys
import time
import json
import tempfile
import requests
import pandas as pd

try:
    import pdfplumber
except ImportError:
    pdfplumber = None
    print("⚠️ pdfplumber 未安装，请执行: pip install pdfplumber")

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DATA_DIR


# ============================================================
# 配置
# ============================================================

# 只下载这些类型的公告（核心公告，信息密度最高）
CORE_TITLE_KEYWORDS = [
    "预案", "草案", "报告书",
    "收购协议", "股权收购协议",
    "完成交割", "交割完成",
    "发行股份购买资产",
    "拟收购", "签订股权收购",
]

# 排除这些（即使包含核心关键词也跳过）
EXCLUDE_KEYWORDS = [
    "摘要", "修订", "更正", "补充", "英文",
    "法律意见", "独立财务顾问", "验资",
    "审计报告", "评估报告",
]

# PDF提取最大页数（避免处理上百页的报告书全文）
MAX_PDF_PAGES = 15

# 每份公告提取的文本最大字符数（喂给DeepSeek的上限）
MAX_TEXT_CHARS = 8000

# PDF下载目录
PDF_DIR = os.path.join(DATA_DIR, "pdfs")
os.makedirs(PDF_DIR, exist_ok=True)


# ============================================================
# PDF 下载
# ============================================================

DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "http://www.cninfo.com.cn/",
}


def is_core_announcement(title: str) -> bool:
    """判断是否为核心公告（值得下载全文分析）"""
    title = str(title)
    # 先排除噪音
    if any(kw in title for kw in EXCLUDE_KEYWORDS):
        return False
    # 再检查是否包含核心关键词
    return any(kw in title for kw in CORE_TITLE_KEYWORDS)


def download_pdf(pdf_url: str, save_name: str) -> str:
    """
    下载PDF文件，返回本地路径
    """
    if not pdf_url or pdf_url == "nan":
        return ""

    save_path = os.path.join(PDF_DIR, save_name)

    # 如果已经下载过，直接返回
    if os.path.exists(save_path) and os.path.getsize(save_path) > 1024:
        return save_path

    try:
        resp = requests.get(pdf_url, headers=DOWNLOAD_HEADERS, timeout=30, stream=True)
        resp.raise_for_status()

        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        # 验证文件大小
        if os.path.getsize(save_path) < 1024:
            os.remove(save_path)
            return ""

        return save_path

    except Exception as e:
        print(f"    ⚠️ 下载失败: {e}")
        return ""


# ============================================================
# PDF 文本提取
# ============================================================

def extract_pdf_text(pdf_path: str, max_pages: int = MAX_PDF_PAGES) -> str:
    """
    从PDF中提取文本（前N页）
    """
    if not pdfplumber:
        return "[pdfplumber未安装，无法提取PDF文本]"

    if not pdf_path or not os.path.exists(pdf_path):
        return ""

    try:
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            pages_to_read = min(len(pdf.pages), max_pages)
            for i in range(pages_to_read):
                page = pdf.pages[i]
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        full_text = "\n".join(text_parts)

        # 截断到最大字符数
        if len(full_text) > MAX_TEXT_CHARS:
            full_text = full_text[:MAX_TEXT_CHARS] + "\n...[文本已截断]"

        return full_text

    except Exception as e:
        return f"[PDF解析失败: {e}]"


# ============================================================
# DeepSeek 结构化提取
# ============================================================

EXTRACT_SYSTEM_PROMPT = """你是一位专业的并购分析师，负责从上市公司公告中提取结构化的交易信息。

请从公告文本中提取以下字段，如果文本中找不到某个字段，填"未披露"：

必须以JSON格式返回，不要包含其他文字：
{
    "target_name": "交易标的名称（被收购公司/资产名称）",
    "target_business": "标的主营业务（一句话描述）",
    "deal_amount": "交易金额（数字+单位，如 12.5亿元）",
    "deal_ratio": "收购比例（如 100%、51%）",
    "payment_method": "支付方式（现金/股权/现金+股权）",
    "valuation_method": "估值方法（如 收益法、资产基础法）",
    "valuation_premium": "估值溢价率（如有）",
    "performance_commitment": "业绩承诺（如：2018-2020年净利润不低于1亿、1.2亿、1.5亿）",
    "strategic_purpose": "收购目的/战略意义（一句话）",
    "deal_status": "交易状态（已完成/进行中/已终止）",
    "key_risks": "关键风险点（一句话）"
}
"""

EXTRACT_USER_TEMPLATE = """以下是上市公司的一份并购相关公告，请提取结构化的交易信息。

公告标题：{title}
公告日期：{ann_date}

公告内容：
{text}

请返回JSON格式的结构化信息。"""


def extract_deal_info(title: str, ann_date: str, text: str) -> dict:
    """
    调用DeepSeek从公告文本中提取结构化交易信息
    """
    if not text or len(text) < 100:
        return {"error": "文本过短，无法分析"}

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
            {"role": "user", "content": EXTRACT_USER_TEMPLATE.format(
                title=title, ann_date=ann_date, text=text
            )},
        ],
        "temperature": 0.1,
        "max_tokens": 1500,
    }

    try:
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]

        # 尝试解析JSON
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]
        return json.loads(content)

    except json.JSONDecodeError:
        return {"raw_response": content, "error": "JSON解析失败"}
    except Exception as e:
        return {"error": f"API调用失败: {e}"}


# ============================================================
# 主流程
# ============================================================

def analyze_ma_pdfs(
    df_ma: pd.DataFrame,
    ts_code: str = "",
    verbose: bool = True,
) -> pd.DataFrame:
    """
    对并购事件表中的核心公告进行全文分析

    参数:
        df_ma: Skill 3输出的并购事件DataFrame（需含pdf_url列）
        ts_code: 股票代码（用于保存文件命名）
        verbose: 是否打印过程

    返回:
        增强后的DataFrame，新增 deal_info 列（JSON字符串）
    """
    if df_ma.empty:
        return df_ma

    if "pdf_url" not in df_ma.columns:
        if verbose:
            print("⚠️ 事件表中无pdf_url列，跳过全文分析")
        return df_ma

    # 筛选核心公告
    df_ma["is_core"] = df_ma["detail"].apply(is_core_announcement)
    core_events = df_ma[df_ma["is_core"] == True]

    if verbose:
        print(f"\n{'=' * 70}")
        print(f" 并购公告全文分析")
        print(f"{'=' * 70}")
        print(f" 总事件数: {len(df_ma)}")
        print(f" 核心公告: {len(core_events)} 条（将下载全文分析）")
        if len(core_events) > 0:
            print(f"\n 待分析的核心公告:")
            for _, row in core_events.iterrows():
                print(f"   [{row.get('event_date', '')}] {row.get('detail', '')[:60]}")

    # 逐个处理核心公告
    deal_infos = {}
    analyzed = 0

    for idx, row in core_events.iterrows():
        pdf_url = str(row.get("pdf_url", ""))
        title = str(row.get("detail", ""))
        ann_date = str(row.get("event_date", ""))

        if not pdf_url or pdf_url == "nan" or not pdf_url.startswith("http"):
            deal_infos[idx] = json.dumps({"error": "无PDF链接"}, ensure_ascii=False)
            continue

        if verbose:
            analyzed += 1
            print(f"\n  [{analyzed}/{len(core_events)}] {title[:50]}...")

        # 1. 下载PDF
        safe_name = f"{ts_code}_{ann_date}_{analyzed}.pdf".replace("/", "_").replace(":", "_")
        if verbose:
            print(f"    📥 下载PDF...")
        pdf_path = download_pdf(pdf_url, safe_name)

        if not pdf_path:
            deal_infos[idx] = json.dumps({"error": "PDF下载失败"}, ensure_ascii=False)
            if verbose:
                print(f"    ❌ 下载失败")
            continue

        if verbose:
            size_kb = os.path.getsize(pdf_path) / 1024
            print(f"    ✅ 已下载 ({size_kb:.0f} KB)")

        # 2. 提取文本
        if verbose:
            print(f"    📄 提取文本...")
        text = extract_pdf_text(pdf_path)

        if not text or len(text) < 100:
            deal_infos[idx] = json.dumps({"error": "文本提取失败或内容过少"}, ensure_ascii=False)
            if verbose:
                print(f"    ❌ 文本提取失败")
            continue

        if verbose:
            print(f"    ✅ 提取 {len(text)} 字符")

        # 3. DeepSeek结构化提取
        if verbose:
            print(f"    🤖 AI分析中...")
        info = extract_deal_info(title, ann_date, text)
        deal_infos[idx] = json.dumps(info, ensure_ascii=False)

        if verbose:
            if "error" not in info:
                target = info.get("target_name", "未知")
                amount = info.get("deal_amount", "未披露")
                method = info.get("payment_method", "未披露")
                print(f"    ✅ 标的: {target} | 金额: {amount} | 支付: {method}")
            else:
                print(f"    ⚠️ {info.get('error', '')}")

        time.sleep(1)  # API频率控制

    # 将deal_info合并回原表
    df_ma["deal_info"] = df_ma.index.map(lambda x: deal_infos.get(x, ""))

    # 保存增强后的事件表
    if ts_code:
        from config import get_data_path
        output_path = get_data_path(ts_code, "step3_ma_events_enriched")
        df_ma.to_csv(output_path, index=False, encoding="utf-8-sig")
        if verbose:
            print(f"\n  增强事件表已保存至: {output_path}")

    return df_ma


def format_deal_summary(df_enriched: pd.DataFrame) -> str:
    """
    将增强后的并购事件表格式化为可读的Markdown摘要
    用于喂给Step 4的综合分析
    """
    lines = []
    lines.append("## 并购交易结构化信息\n")

    has_info = df_enriched[df_enriched["deal_info"].str.len() > 10]
    if has_info.empty:
        lines.append("*无核心公告全文分析数据*\n")
        return "\n".join(lines)

    deal_num = 0
    for _, row in has_info.iterrows():
        try:
            info = json.loads(row["deal_info"])
        except (json.JSONDecodeError, TypeError):
            continue

        if "error" in info:
            continue

        deal_num += 1
        date = row.get("event_date", "")
        title = row.get("detail", "")

        lines.append(f"### 交易{deal_num}: {date} {title[:40]}")
        lines.append("")

        field_map = {
            "target_name": "交易标的",
            "target_business": "标的业务",
            "deal_amount": "交易金额",
            "deal_ratio": "收购比例",
            "payment_method": "支付方式",
            "valuation_premium": "估值溢价",
            "performance_commitment": "业绩承诺",
            "strategic_purpose": "战略目的",
            "deal_status": "交易状态",
            "key_risks": "关键风险",
        }

        for key, label in field_map.items():
            val = info.get(key, "未披露")
            if val and val != "未披露":
                lines.append(f"- **{label}**: {val}")

        lines.append("")

    if deal_num == 0:
        lines.append("*核心公告分析未提取到有效交易信息*\n")

    return "\n".join(lines)


# ============================================================
# 独立运行
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python ma_pdf_analyzer.py <股票代码>")
        print("示例: python ma_pdf_analyzer.py 603197")
        print("注意: 需先运行 skill3 生成事件表")
        sys.exit(1)

    stock = sys.argv[1]

    # 尝试读取skill3输出
    from config import get_data_path

    # 解析代码
    if "." in stock:
        ts_code = stock
    else:
        import tushare as ts
        from config import TUSHARE_TOKEN
        ts.set_token(TUSHARE_TOKEN)
        pro = ts.pro_api()
        df_basic = pro.stock_basic(exchange="", list_status="L", fields="ts_code,symbol,name")
        code_clean = stock.split(".")[0]
        if code_clean.isdigit():
            match = df_basic[df_basic["symbol"] == code_clean]
        else:
            match = df_basic[df_basic["name"].str.contains(stock, na=False)]
        if match.empty:
            print(f"未找到: {stock}")
            sys.exit(1)
        ts_code = match.iloc[0]["ts_code"]

    step3_path = get_data_path(ts_code, "step3_ma_events")
    try:
        df_ma = pd.read_csv(step3_path)
        print(f"读取事件表: {step3_path} ({len(df_ma)} 条)")
    except FileNotFoundError:
        print(f"未找到: {step3_path}")
        print("请先运行 skill3_ma_events_fetch.py")
        sys.exit(1)

    # 分析
    df_enriched = analyze_ma_pdfs(df_ma, ts_code=ts_code, verbose=True)

    # 输出摘要
    summary = format_deal_summary(df_enriched)
    print(f"\n{'=' * 70}")
    print(summary)
