"""
Skill 2：现金流结构分析
──────────────────────
输入：Skill 1输出的CSV文件（或直接传入ts_code自动读取）
输出：在原表基础上新增分类标注，保存为新CSV + 打印分析结果

核心方法论：八种现金流组合 → 企业生命周期阶段判断

用法：
    python skill2_cashflow_classify.py 600900.SH
    python skill2_cashflow_classify.py 长江电力
"""

import sys
import io
import pandas as pd
from config import get_data_path, fmt_yi, fmt_yi_with_sign

# Windows GBK 终端兼容
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ============================================================
# 八种现金流组合框架
# ============================================================
# key: (经营符号, 投资符号, 筹资符号)  "+"=正, "−"=负
CASHFLOW_PATTERNS = {
    ("+", "−", "+"): {
        "name": "扩张型",
        "stage": "高速成长期",
        "desc": "经营造血+外部融资→大举投资扩张",
        "risk": "关注投资回报率是否覆盖融资成本",
        "health": 3,  # 1-5，5最健康
    },
    ("+", "−", "−"): {
        "name": "成熟型",
        "stage": "成熟稳定期",
        "desc": "经营造血→支撑投资+偿债/分红，最健康的结构",
        "risk": "关注投资是否足以维持竞争力",
        "health": 5,
    },
    ("+", "+", "+"): {
        "name": "异常聚集型",
        "stage": "需特别关注",
        "desc": "三项均为正：经营+处置资产+融资，现金大量聚集",
        "risk": "可能在为重大投资/并购蓄力，或存在报表调节",
        "health": 2,
    },
    ("+", "+", "−"): {
        "name": "收缩偿债型",
        "stage": "收缩/转型期",
        "desc": "经营造血+处置资产→偿还债务",
        "risk": "关注资产处置是否为被动行为，业务是否萎缩",
        "health": 3,
    },
    ("−", "−", "+"): {
        "name": "烧钱融资型",
        "stage": "初创/重大投入期",
        "desc": "经营亏损+大举投资，全靠外部融资维持",
        "risk": "🔴 融资可持续性是关键，关注现金消耗速度",
        "health": 2,
    },
    ("−", "−", "−"): {
        "name": "全面失血型",
        "stage": "危机/衰退期",
        "desc": "三项均为负：全面失血，靠存量现金维持",
        "risk": "🔴🔴 最危险的结构，需立即关注存续能力",
        "health": 1,
    },
    ("−", "+", "+"): {
        "name": "变卖融资型",
        "stage": "濒危/特殊事件期",
        "desc": "经营亏损，靠变卖资产+融资维持",
        "risk": "🔴 若持续多年则濒危，需关注是否为一次性事件",
        "health": 1,
    },
    ("−", "+", "−"): {
        "name": "变卖偿债型",
        "stage": "衰退清算期",
        "desc": "经营亏损，变卖资产偿还债务",
        "risk": "🔴 清算特征，除非处于战略性业务剥离",
        "health": 1,
    },
}


def get_sign(val) -> str:
    """数值转符号"""
    if pd.isna(val):
        return "?"
    return "+" if val > 0 else "−"


def classify_row(row) -> dict:
    """
    对单年数据进行现金流组合分类
    返回: {pattern, name, stage, desc, risk, health}
    """
    o = get_sign(row.get("n_cashflow_act"))
    i = get_sign(row.get("n_cashflow_inv_act"))
    f = get_sign(row.get("n_cashflow_fin_act"))

    pattern_key = (o, i, f)
    pattern_str = f"{o}{i}{f}"

    info = CASHFLOW_PATTERNS.get(pattern_key, {
        "name": "数据缺失",
        "stage": "无法判断",
        "desc": "存在缺失数据",
        "risk": "需补全数据",
        "health": 0,
    })

    return {
        "cf_pattern": pattern_str,
        "cf_type": info["name"],
        "lifecycle_stage": info["stage"],
        "cf_desc": info["desc"],
        "risk_signal": info["risk"],
        "health_score": info["health"],
    }


def detect_trend_changes(df: pd.DataFrame) -> pd.DataFrame:
    """
    检测相邻年份的模式变化，标记转折点
    """
    changes = []
    for i in range(len(df)):
        if i == 0:
            changes.append("—")
            continue
        prev = df.iloc[i - 1]["cf_type"]
        curr = df.iloc[i]["cf_type"]
        if prev != curr:
            # 判断变化方向
            prev_health = df.iloc[i - 1]["health_score"]
            curr_health = df.iloc[i]["health_score"]
            direction = ""
            if curr_health < prev_health:
                direction = " 🔻恶化"
            elif curr_health > prev_health:
                direction = " 🔺改善"
            changes.append(f"{prev}→{curr}{direction}")
        else:
            changes.append(f"维持{curr}")

    df["trend_change"] = changes
    return df


def compute_quality_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算关键质量比率（如有净利润数据可扩展）
    """
    # 资本支出强度 = 资本支出 / 经营现金流
    if "c_pay_acq_const_fiolta" in df.columns:
        df["capex_intensity"] = df.apply(
            lambda r: (
                abs(r["c_pay_acq_const_fiolta"]) / r["n_cashflow_act"]
                if pd.notna(r["c_pay_acq_const_fiolta"])
                and pd.notna(r["n_cashflow_act"])
                and r["n_cashflow_act"] > 0
                else None
            ),
            axis=1,
        )
    else:
        df["capex_intensity"] = None

    return df


def analyze_persistence(df: pd.DataFrame) -> str:
    """
    分析模式持续性，返回文字描述
    """
    if df.empty:
        return "无数据"

    # 统计各模式出现次数
    type_counts = df["cf_type"].value_counts()
    dominant = type_counts.index[0]
    dominant_pct = type_counts.iloc[0] / len(df) * 100

    # 检测连续相同模式的最长段
    max_streak = 1
    current_streak = 1
    streak_type = df.iloc[0]["cf_type"]
    max_streak_type = streak_type

    for i in range(1, len(df)):
        if df.iloc[i]["cf_type"] == df.iloc[i - 1]["cf_type"]:
            current_streak += 1
            if current_streak > max_streak:
                max_streak = current_streak
                max_streak_type = df.iloc[i]["cf_type"]
        else:
            current_streak = 1

    # 最近3年模式
    recent_3 = df.tail(3)["cf_type"].tolist() if len(df) >= 3 else df["cf_type"].tolist()

    lines = []
    lines.append(f"主导模式：{dominant}（占比 {dominant_pct:.0f}%，{type_counts.iloc[0]}/{len(df)} 年）")
    lines.append(f"最长连续：{max_streak_type} 连续 {max_streak} 年")
    lines.append(f"最近趋势：{'→'.join(recent_3)}")

    # 稳定性判断
    unique_types = df["cf_type"].nunique()
    if unique_types <= 2:
        lines.append("稳定性：⭐⭐⭐ 高度稳定（仅出现1-2种模式）")
    elif unique_types <= 3:
        lines.append("稳定性：⭐⭐ 较稳定")
    else:
        lines.append("稳定性：⭐ 波动较大（出现4种以上模式）")

    return "\n".join(lines)


def run(ts_code_or_keyword: str, verbose: bool = True) -> pd.DataFrame:
    """
    主入口：读取Skill1输出 → 分类 → 保存
    """
    # 处理输入：如果是简称，先转代码
    if not ("." in ts_code_or_keyword and ts_code_or_keyword[-2:] in ("SH", "SZ")):
        # 需要解析，导入skill1的resolve函数
        from skill1_cashflow_fetch import resolve_ts_code
        ts_code, name, _ = resolve_ts_code(ts_code_or_keyword)
    else:
        ts_code = ts_code_or_keyword
        name = ts_code  # 后面从数据里补

    # 读取Skill1输出
    input_path = get_data_path(ts_code, "step1_cashflow")
    try:
        df = pd.read_csv(input_path)
    except FileNotFoundError:
        print(f"❌ 未找到Skill 1输出文件：{input_path}")
        print(f"   请先运行：python skill1_cashflow_fetch.py {ts_code}")
        sys.exit(1)

    if verbose:
        print(f"{'=' * 70}")
        print(f" {ts_code} 现金流结构分析（八种组合框架）")
        print(f"{'=' * 70}")
        print(f"读取数据：{input_path}（{len(df)} 条记录）\n")

    # 过滤掉季报行（仅分析年报）
    if "is_quarterly" in df.columns:
        df_annual = df[df["is_quarterly"] != True].copy()
    else:
        df_annual = df.copy()

    # 逐年分类
    classifications = df_annual.apply(classify_row, axis=1, result_type="expand")
    df_annual = pd.concat([df_annual, classifications], axis=1)

    # 趋势变化检测
    df_annual = detect_trend_changes(df_annual)

    # 质量比率
    df_annual = compute_quality_ratios(df_annual)

    # 保存
    output_path = get_data_path(ts_code, "step2_classified")
    df_annual.to_csv(output_path, index=False, encoding="utf-8-sig")

    if verbose:
        # 打印分类结果表
        print(f"{'年份':<6} {'经营':>8} {'投资':>8} {'筹资':>8} │ {'模式':<4} {'类型':<10} {'阶段':<12} │ {'趋势变化'}")
        print(f"{'─' * 90}")
        for _, row in df_annual.iterrows():
            yr = str(int(row["year"]))
            o_str = fmt_yi_with_sign(row.get("n_cashflow_act"))
            i_str = fmt_yi_with_sign(row.get("n_cashflow_inv_act"))
            f_str = fmt_yi_with_sign(row.get("n_cashflow_fin_act"))
            print(
                f"{yr:<6} {o_str:>8} {i_str:>8} {f_str:>8} │ "
                f"{row['cf_pattern']:<4} {row['cf_type']:<10} {row['lifecycle_stage']:<12} │ "
                f"{row['trend_change']}"
            )

        # 持续性分析
        print(f"\n{'=' * 70}")
        print(" 模式持续性分析")
        print(f"{'─' * 70}")
        persistence = analyze_persistence(df_annual)
        print(persistence)

        # 关键转折点
        print(f"\n{'=' * 70}")
        print(" 关键转折点（模式恶化的年份）")
        print(f"{'─' * 70}")
        turning_points = df_annual[df_annual["trend_change"].str.contains("恶化", na=False)]
        if turning_points.empty:
            print("  无显著恶化转折点")
        else:
            for _, tp in turning_points.iterrows():
                print(f"  ⚠️ {int(tp['year'])}年：{tp['trend_change']}")
                print(f"     经营={fmt_yi_with_sign(tp.get('n_cashflow_act'))}亿  "
                      f"投资={fmt_yi_with_sign(tp.get('n_cashflow_inv_act'))}亿  "
                      f"筹资={fmt_yi_with_sign(tp.get('n_cashflow_fin_act'))}亿")

        # 风险年份
        print(f"\n{'=' * 70}")
        print(" 风险年份（health_score ≤ 2）")
        print(f"{'─' * 70}")
        risky = df_annual[df_annual["health_score"] <= 2]
        if risky.empty:
            print("  ✅ 无高风险年份")
        else:
            for _, r in risky.iterrows():
                print(f"  🔴 {int(r['year'])}年 [{r['cf_type']}] {r['risk_signal']}")

        print(f"\n分析结果已保存至：{output_path}")

    return df_annual


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python skill2_cashflow_classify.py <股票代码>")
        print("示例：python skill2_cashflow_classify.py 600900.SH")
        print("注意：需先运行 skill1_cashflow_fetch.py 获取数据")
        sys.exit(1)

    run(sys.argv[1])
