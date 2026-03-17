"""
Skill 4：综合研判
──────────────────────
输入：Skill 1的数据 + Skill 2的分类结果 + Skill 3a的年报 + Skill 3b的提取结果
输出：Markdown格式的综合研判报告

核心：将结构化数据喂给DeepSeek进行深度分析推理

用法：
    python skill4_comprehensive.py 600900.SH
    python skill4_comprehensive.py 长江电力
"""

import sys
import io
import json
import os
import glob
import time
import requests
import pandas as pd
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL,
    get_data_path, get_report_path, fmt_yi, fmt_yi_with_sign,
)

# Windows GBK 终端兼容
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ============================================================
# DeepSeek API 调用
# ============================================================

def call_deepseek(system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
    """
    调用 DeepSeek API 进行分析推理
    """
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": 4000,
    }

    try:
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[DeepSeek API调用失败: {e}]\n请检查API Key和网络连接。"


# ============================================================
# 数据准备：将CSV转为结构化文本，作为AI的上下文
# ============================================================

def prepare_cashflow_context(df_classified: pd.DataFrame, df_cashflow: pd.DataFrame) -> str:
    """
    将Skill 2的分类结果和Skill 1的现金流数据转为AI可读的文本
    """
    lines = []
    lines.append("## 历史现金流分类结果（单位：亿元）\n")
    lines.append(f"{'年份':<6} {'经营':>8} {'投资':>8} {'筹资':>8} │ {'模式':>4} {'类型':<10} {'阶段':<12} │ {'趋势变化'}")
    lines.append("─" * 90)

    for _, row in df_classified.iterrows():
        yr = str(int(row["year"]))
        o_str = fmt_yi_with_sign(row["n_cashflow_act"])
        i_str = fmt_yi_with_sign(row["n_cashflow_inv_act"])
        f_str = fmt_yi_with_sign(row["n_cashflow_fin_act"])
        lines.append(
            f"{yr:<6} {o_str:>8} {i_str:>8} {f_str:>8} │ "
            f"{row['cf_pattern']:<4} {row['cf_type']:<10} {row['lifecycle_stage']:<12} │ "
            f"{row.get('trend_change', '')}"
        )

    # 汇总统计
    lines.append(f"\n### 模式统计")
    type_counts = df_classified["cf_type"].value_counts()
    for t, c in type_counts.items():
        lines.append(f"  {t}: {c}年")

    # 累计数据
    lines.append(f"\n### 累计数据")
    lines.append(f"  经营活动累计: {fmt_yi(df_classified['n_cashflow_act'].sum())}亿元")
    lines.append(f"  投资活动累计: {fmt_yi(df_classified['n_cashflow_inv_act'].sum())}亿元")
    lines.append(f"  筹资活动累计: {fmt_yi(df_classified['n_cashflow_fin_act'].sum())}亿元")

    if "free_cashflow" in df_classified.columns:
        fcf_sum = df_classified["free_cashflow"].sum()
        lines.append(f"  自由现金流累计: {fmt_yi(fcf_sum)}亿元")

    # 投资活动明细（从 Skill 1）
    if "investment_in_assets" in df_cashflow.columns:
        lines.append(f"\n### 投资活动明细（累计）")
        lines.append(f"  购建固定资产等: {fmt_yi(df_cashflow['investment_in_assets'].sum())}亿元")
    if "investment_in_longterm" in df_cashflow.columns:
        lines.append(f"  长期投资支出: {fmt_yi(df_cashflow['investment_in_longterm'].sum())}亿元")

    return "\n".join(lines)


def prepare_annual_reports_context(extracted_dir: str, stock_name: str) -> str:
    """
    将Skill 3b的年报提取结果转为AI可读的文本
    """
    lines = []
    lines.append("## 年度报告提取结果\n")

    # 查找所有提取结果JSON文件
    json_pattern = os.path.join(extracted_dir, f"{stock_name}_*年_提取结果.json")
    json_files = sorted(glob.glob(json_pattern))

    if not json_files:
        lines.append("未找到年报提取结果。")
        return "\n".join(lines)

    # 读取核心经营指标汇总CSV
    core_metrics_csv = os.path.join(extracted_dir, "核心经营指标汇总.csv")
    if os.path.exists(core_metrics_csv):
        lines.append("### 核心经营指标趋势\n")
        try:
            df_metrics = pd.read_csv(core_metrics_csv)
            lines.append("| 年度 | 营业收入 | 营收同比 | 归母净利润 | 经营现金流 | 研发投入 | 研发占比 |")
            lines.append("|:----:|----------:|----------:|----------:|----------:|----------:|----------:|")
            for _, row in df_metrics.iterrows():
                lines.append(
                    f"| {row['报告年度']} | {row['营业收入']} | {row['营业收入同比']} | "
                    f"{row['归母净利润']} | {row['经营活动现金流净额']} | {row['研发投入']} | {row['研发投入占营收比']} |"
                )
            lines.append("")
        except Exception as e:
            lines.append(f"（读取核心经营指标失败：{e}）\n")

    # 读取并购及重大投资汇总CSV
    ma_csv = os.path.join(extracted_dir, "并购及重大投资汇总.csv")
    if os.path.exists(ma_csv):
        lines.append("### 并购及重大投资事件\n")
        try:
            df_ma = pd.read_csv(ma_csv)
            if not df_ma.empty:
                lines.append(f"共发现 {len(df_ma)} 条并购/投资事件：\n")
                for _, row in df_ma.iterrows():
                    lines.append(f"**{row['报告年度']}年**：【{row['事件类型']}】{row['事件描述']}")
                    if pd.notna(row.get('交易金额')):
                        lines.append(f"  - 交易金额: {row['交易金额']}")
                    if pd.notna(row.get('标的名称')):
                        lines.append(f"  - 标的名称: {row['标的名称']}")
                    if pd.notna(row.get('交易进展')):
                        lines.append(f"  - 交易进展: {row['交易进展']}")
                    lines.append("")
            else:
                lines.append("未发现重大并购/投资事件。\n")
        except Exception as e:
            lines.append(f"（读取并购事件失败：{e}）\n")

    # 提取各年度主营业务构成
    lines.append("### 主营业务构成变化\n")
    for json_file in json_files[-3:]:  # 只取最近3年
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            year = data.get('报告年度', '未知')
            mda = data.get('经营分析', {})
            main_business = mda.get('主营业务构成', [])
            
            lines.append(f"#### {year}年")
            if main_business:
                for business in main_business[:5]:  # 只取前5个业务
                    lines.append(f"- {business.get('业务或产品', '未知')}: "
                               f"营收{business.get('营业收入', '未知')} "
                               f"({business.get('占总营收比', '未知')}) "
                               f"毛利率{business.get('毛利率', '未知')}")
            else:
                lines.append("（未提取到主营业务构成）")
            lines.append("")
        except Exception as e:
            continue

    return "\n".join(lines)


def prepare_management_analysis_context(extracted_dir: str, stock_name: str) -> str:
    """
    提取管理层讨论与分析的关键信息
    """
    lines = []
    lines.append("## 管理层讨论与分析摘要\n")

    # 查找所有提取结果JSON文件
    json_pattern = os.path.join(extracted_dir, f"{stock_name}_*年_提取结果.json")
    json_files = sorted(glob.glob(json_pattern))

    if not json_files:
        lines.append("未找到年报提取结果。")
        return "\n".join(lines)

    # 提取最近3年的经营分析摘要
    for json_file in json_files[-3:]:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            year = data.get('报告年度', '未知')
            mda = data.get('经营分析', {})
            
            lines.append(f"### {year}年\n")
            
            # 提取经营回顾
            business_review = mda.get('经营情况回顾', '')
            if business_review and business_review != 'null':
                lines.append(f"**经营回顾**: {business_review[:300]}...\n")
            
            # 提取未来展望
            future_outlook = mda.get('未来展望', '')
            if future_outlook and future_outlook != 'null':
                lines.append(f"**未来展望**: {future_outlook[:300]}...\n")
            
            # 提取风险因素
            risk_factors = mda.get('风险因素', '')
            if risk_factors and risk_factors != 'null':
                lines.append(f"**风险因素**: {risk_factors[:300]}...\n")
            
        except Exception as e:
            continue

    return "\n".join(lines)


# ============================================================
# 综合研判：调用DeepSeek进行分析
# ============================================================

SYSTEM_PROMPT = """你是一位资深的A股投资分析师，擅长通过现金流分析结合年报深度信息判断企业价值和投资风险。

你的分析框架：
1. 从现金流结构判断企业所处生命周期阶段
2. 将并购事件与现金流变化进行因果关联
3. 结合年报中的经营分析，验证现金流模式的真实性
4. 识别风险信号和投资机会
5. 评估管理层的战略执行能力

分析要求：
- 用数据说话，每个结论都要有具体数字支撑
- 关注现金流模式的"转折点"，分析背后的驱动因素
- 重点评估并购对经营现金流的实际贡献
- 结合年报中的业务构成和经营分析，判断主营业务的质量
- 语言简洁精准，避免套话
- 如果数据不足以支持某个结论，明确标注"需进一步验证"
"""

ANALYSIS_TEMPLATE = """请基于以下数据，对该公司进行现金流综合研判分析。

{cashflow_context}

{annual_reports_context}

{management_analysis_context}

请按以下结构输出分析报告：

# [公司代码] 现金流综合研判报告

## 一、现金流生命周期概览
（3-5句话概括公司从上市至今的现金流演变路径，指出主导模式和关键阶段）

## 二、关键转折点分析
（逐个分析现金流模式发生重大变化的年份，格式如下：）

### 转折点N：XXXX年 — 从XX期进入XX期
- **触发因素**：（关联并购事件或年报中披露的驱动因素）
- **现金流变化**：（具体数字对比）
- **后续影响**：（对后续年份的影响）

## 三、业务质量与并购效果评估
（结合年报主营业务构成和经营分析）
- 主营业务收入结构的变化趋势
- 各业务板块的盈利能力（毛利率）分析
- 并购事件对业务结构的影响
- 并购前后经营现金流的对比
- 整体并购策略和转型方向评价

## 四、当前状态与风险信号
（基于最近2-3年的数据，结合年报分析）
- 当前所处阶段
- 管理层披露的风险因素
- 存在的风险信号（如有）
- 积极因素

## 五、前瞻判断
（基于历史模式、当前状态和年报中的未来展望）
- 最可能的现金流模式演变方向
- 管理层提到的战略规划和预期
- 需要关注的关键变量
- 投资含义（对估值/分红/再融资的影响）
"""


def generate_appendix_cashflow(df_classified: pd.DataFrame) -> str:
    """
    生成附表一：历史现金流数据表（Markdown格式）
    """
    lines = []
    lines.append("\n---\n")
    lines.append("## 附表一：历史现金流数据表")
    lines.append("")
    lines.append("*单位：亿元*")
    lines.append("")

    # 表头
    lines.append(
        "| 年份 | 经营活动净额 | 投资活动净额 | 筹资活动净额 | 自由现金流 | 期末现金 | 模式 | 类型 | 阶段 |"
    )
    lines.append(
        "|:----:|----------:|----------:|----------:|----------:|----------:|:----:|:----:|:----:|"
    )

    # 逐行
    for _, row in df_classified.iterrows():
        yr = str(int(row["year"]))
        o = fmt_yi(row.get("n_cashflow_act"))
        i = fmt_yi(row.get("n_cashflow_inv_act"))
        f = fmt_yi(row.get("n_cashflow_fin_act"))
        fcf = fmt_yi(row.get("free_cashflow"))
        cash_end = fmt_yi(row.get("c_cash_equ_end_period"))
        pattern = str(row.get("cf_pattern", ""))
        cf_type = str(row.get("cf_type", ""))
        stage = str(row.get("lifecycle_stage", ""))

        lines.append(
            f"| {yr} | {o} | {i} | {f} | {fcf} | {cash_end} | {pattern} | {cf_type} | {stage} |"
        )

    # 累计行
    o_sum = fmt_yi(df_classified["n_cashflow_act"].sum())
    i_sum = fmt_yi(df_classified["n_cashflow_inv_act"].sum())
    f_sum = fmt_yi(df_classified["n_cashflow_fin_act"].sum())
    fcf_col = "free_cashflow"
    fcf_sum = fmt_yi(df_classified[fcf_col].sum()) if fcf_col in df_classified.columns else "—"
    lines.append(
        f"| **合计** | **{o_sum}** | **{i_sum}** | **{f_sum}** | **{fcf_sum}** | — | — | — | — |"
    )

    lines.append("")
    lines.append("*数据来源：Tushare Pro（合并报表年报口径）*")

    return "\n".join(lines)


def run(ts_code_or_keyword: str, verbose: bool = True) -> str:
    """
    主入口：读取Skill 1 + Skill 2 + Skill 3a + Skill 3b输出 → 构建Prompt → 调用DeepSeek → 生成报告 → 追加附表
    """
    # 解析股票代码
    if not ("." in ts_code_or_keyword and ts_code_or_keyword[-2:] in ("SH", "SZ")):
        from skill1_cashflow_fetch import resolve_ts_code
        ts_code, name, _ = resolve_ts_code(ts_code_or_keyword)
    else:
        ts_code = ts_code_or_keyword
        # 尝试从文件路径中提取股票名称
        name = ts_code

    if verbose:
        print(f"{'=' * 70}")
        print(f" {ts_code} 现金流综合研判")
        print(f"{'=' * 70}")

    # 读取Skill 1输出
    step1_path = get_data_path(ts_code, "step1_cashflow")
    try:
        df_cashflow = pd.read_csv(step1_path)
        if verbose:
            print(f"✅ 读取现金流数据：{step1_path}（{len(df_cashflow)}条）")
    except FileNotFoundError:
        print(f"❌ 未找到Skill 1输出：{step1_path}")
        print(f"   请先运行 skill1_cashflow_fetch.py")
        sys.exit(1)

    # 读取Skill 2输出
    step2_path = get_data_path(ts_code, "step2_classified")
    try:
        df_classified = pd.read_csv(step2_path)
        if verbose:
            print(f"✅ 读取现金流分类数据：{step2_path}（{len(df_classified)}条）")
    except FileNotFoundError:
        print(f"❌ 未找到Skill 2输出：{step2_path}")
        print(f"   请先运行 skill2_cashflow_classify.py")
        sys.exit(1)

    # 读取Skill 3a/3b输出（年报提取结果）
    extracted_dir = os.path.join("data", "annual_reports_extracted")
    has_annual_reports = os.path.exists(extracted_dir)
    
    # 尝试从 annual_reports 目录中推断股票名称
    annual_reports_dir = os.path.join("annual_reports")
    if os.path.exists(annual_reports_dir):
        subdirs = [d for d in os.listdir(annual_reports_dir) 
                   if os.path.isdir(os.path.join(annual_reports_dir, d))]
        if subdirs:
            # 找到包含 ts_code 前6位或股票名称的目录
            for subdir in subdirs:
                if ts_code[:6] in subdir or name in subdir:
                    name = subdir
                    break

    if not has_annual_reports:
        if verbose:
            print(f"⚠️ 未找到年报提取结果目录：{extracted_dir}")
            print(f"   请先运行 skill3a_download_annual_reports.py 和 skill3b_extract_annual_reports.py")
    
    # 构建上下文
    cashflow_context = prepare_cashflow_context(df_classified, df_cashflow)
    
    if has_annual_reports:
        annual_reports_context = prepare_annual_reports_context(extracted_dir, name)
        management_analysis_context = prepare_management_analysis_context(extracted_dir, name)
    else:
        annual_reports_context = "## 年度报告提取结果\n\n未找到年报提取结果。"
        management_analysis_context = "## 管理层讨论与分析摘要\n\n未找到年报提取结果。"

    user_prompt = ANALYSIS_TEMPLATE.format(
        cashflow_context=cashflow_context,
        annual_reports_context=annual_reports_context,
        management_analysis_context=management_analysis_context,
    )

    if verbose:
        print(f"\n正在调用 DeepSeek API 进行综合分析...")
        print(f"（上下文长度：现金流 {len(cashflow_context)} 字符，年报 {len(annual_reports_context)} 字符）")

    # 调用 DeepSeek
    report = call_deepseek(SYSTEM_PROMPT, user_prompt)

    # 生成附表
    appendix_cf = generate_appendix_cashflow(df_classified)

    # 拼接完整报告：分析正文 + 附表
    full_report = report + "\n" + appendix_cf

    # 保存报告
    report_path = get_report_path(ts_code)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(full_report)

    if verbose:
        print(f"\n{'=' * 70}")
        print(full_report)
        print(f"\n{'=' * 70}")
        print(f"报告已保存至：{report_path}")

    return full_report


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python skill4_comprehensive.py <股票代码>")
        print("示例：python skill4_comprehensive.py 600900.SH")
        print("      python skill4_comprehensive.py 长江电力")
        print("注意：需先运行 skill1, skill2, skill3a, skill3b")
        sys.exit(1)

    run(sys.argv[1])
