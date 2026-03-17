"""
Skill 1：现金流数据获取
──────────────────────
输入：股票代码或简称
输出：CSV文件 - 从上市至今的年度现金流表（经营/投资/筹资/自由现金流）

用法：
    python skill1_cashflow_fetch.py 600900
    python skill1_cashflow_fetch.py 长江电力
    python skill1_cashflow_fetch.py 000858.SZ
"""

import sys
import time
import tushare as ts
import pandas as pd
from config import TUSHARE_TOKEN, get_data_path, fmt_yi

ts.set_token(TUSHARE_TOKEN)
pro = ts.pro_api()


def resolve_ts_code(keyword: str) -> tuple:
    """
    股票代码/简称 → (ts_code, name)
    支持: 600900 / 600900.SH / 长江电力
    """
    keyword = keyword.strip()
    df = pro.stock_basic(
        exchange="",
        list_status="L",
        fields="ts_code,symbol,name,list_date"
    )

    # 精确匹配代码
    code_clean = keyword.split(".")[0]
    if code_clean.isdigit():
        match = df[df["symbol"] == code_clean]
        if not match.empty:
            row = match.iloc[0]
            return row["ts_code"], row["name"], row["list_date"]

    # 精确匹配简称
    match = df[df["name"] == keyword]
    if not match.empty:
        row = match.iloc[0]
        return row["ts_code"], row["name"], row["list_date"]

    # 模糊匹配简称
    match = df[df["name"].str.contains(keyword, na=False)]
    if not match.empty:
        row = match.iloc[0]
        return row["ts_code"], row["name"], row["list_date"]

    raise ValueError(f"未找到股票: {keyword}")


def fetch_annual_cashflow(ts_code: str) -> pd.DataFrame:
    """
    获取年度现金流量表数据
    返回DataFrame，包含：
      - 三大活动净额 + 期末现金
      - 投资活动分解：自建扩产(资本支出) vs 并购(取得子公司)
      - 自由现金流
    """
    # 主表：三大活动净额 + 期末现金
    # 注意：Tushare cashflow 接口筹资活动字段名为 n_cash_flows_fnc_act，
    # 而 cashflow_vip 接口为 n_cashflow_fin_act，两者不同，需要兼容处理
    fields_main = (
        "ts_code,end_date,report_type,"
        "n_cashflow_act,"          # 经营活动现金流净额
        "n_cashflow_inv_act,"      # 投资活动现金流净额
        "n_cashflow_fin_act,"      # 筹资活动现金流净额（vip 接口字段）
        "n_cash_flows_fnc_act,"    # 筹资活动现金流净额（普通接口字段）
        "c_cash_equ_end_period"    # 期末现金及等价物
    )

    df = pro.cashflow_vip(
        ts_code=ts_code,
        report_type="1",  # 合并报表
        fields=fields_main
    )
    time.sleep(0.3)  # 频率控制

    if df.empty:
        # 降级到cashflow接口
        df = pro.cashflow(
            ts_code=ts_code,
            report_type="1",
            fields=fields_main
        )
        time.sleep(0.3)

    if df.empty:
        raise ValueError(f"未获取到 {ts_code} 的现金流数据")

    # 兼容 cashflow 普通接口的筹资活动字段名 n_cash_flows_fnc_act → n_cashflow_fin_act
    if "n_cashflow_fin_act" not in df.columns and "n_cash_flows_fnc_act" in df.columns:
        df = df.rename(columns={"n_cash_flows_fnc_act": "n_cashflow_fin_act"})
    elif "n_cash_flows_fnc_act" in df.columns:
        df = df.drop(columns=["n_cash_flows_fnc_act"])

    # 只保留年报
    df = df[df["end_date"].str.endswith("1231")].copy()
    df = df.drop_duplicates(subset="end_date", keep="first")
    df = df.sort_values("end_date").reset_index(drop=True)

    # ── 获取投资活动明细（分解自建 vs 并购）──
    fields_inv_detail = (
        "end_date,report_type,"
        "c_pay_acq_const_fiolta,"   # 购建固定资产、无形资产等支付的现金（=资本支出/自建扩产）
        "c_pay_acq_subcom,"         # 取得子公司及其他营业单位支付的现金净额（=并购）
        "c_recp_disp_subcom"        # 处置子公司及其他营业单位收到的现金净额
    )
    df_inv = pro.cashflow_vip(
        ts_code=ts_code,
        report_type="1",
        fields=fields_inv_detail
    )
    time.sleep(0.3)

    if df_inv.empty:
        df_inv = pro.cashflow(
            ts_code=ts_code,
            report_type="1",
            fields=fields_inv_detail
        )
        time.sleep(0.3)

    if not df_inv.empty:
        df_inv = df_inv[df_inv["end_date"].str.endswith("1231")].copy()
        df_inv = df_inv.drop_duplicates(subset="end_date", keep="first")
        # 仅保留实际存在的列，避免部分股票字段缺失报错
        inv_cols = ["end_date"]
        for col in ["c_pay_acq_const_fiolta", "c_pay_acq_subcom", "c_recp_disp_subcom"]:
            if col in df_inv.columns:
                inv_cols.append(col)
            else:
                df_inv[col] = None
                inv_cols.append(col)
        df_inv = df_inv[inv_cols]
        df = df.merge(df_inv, on="end_date", how="left")
    else:
        df["c_pay_acq_const_fiolta"] = None
        df["c_pay_acq_subcom"] = None
        df["c_recp_disp_subcom"] = None

    # ── 获取资产负债表：固定资产 + 在建工程（反映产能变化）──
    fields_bs = "end_date,report_type,fix_assets,cip,lt_amor_exp"
    df_bs = pro.balancesheet_vip(
        ts_code=ts_code,
        report_type="1",
        fields=fields_bs
    )
    time.sleep(0.3)

    if df_bs.empty:
        df_bs = pro.balancesheet(
            ts_code=ts_code,
            report_type="1",
            fields=fields_bs
        )
        time.sleep(0.3)

    if not df_bs.empty:
        df_bs = df_bs[df_bs["end_date"].str.endswith("1231")].copy()
        df_bs = df_bs.drop_duplicates(subset="end_date", keep="first")
        df_bs = df_bs[["end_date", "fix_assets", "cip"]]
        df = df.merge(df_bs, on="end_date", how="left")
    else:
        df["fix_assets"] = None
        df["cip"] = None

    # ── 计算衍生指标 ──
    # 自由现金流 = 经营活动净额 - 资本支出
    df["free_cashflow"] = df["n_cashflow_act"] - df["c_pay_acq_const_fiolta"].fillna(0)

    # 投资分解占比（当投资活动净流出时）
    # capex_ratio = 自建扩产占投资流出的比例
    # ma_ratio = 并购占投资流出的比例
    df["capex"] = df["c_pay_acq_const_fiolta"].fillna(0)
    df["ma_cash"] = df["c_pay_acq_subcom"].fillna(0)

    # 在建工程同比变化（反映产能建设进度）
    df["cip_chg"] = pd.to_numeric(df["cip"], errors="coerce").diff()

    # 固定资产同比变化（反映产能投产情况）
    df["fix_assets_chg"] = pd.to_numeric(df["fix_assets"], errors="coerce").diff()

    # 提取年份列，便于阅读
    df["year"] = df["end_date"].str[:4].astype(int)

    # 选择输出列
    cols = [
        "year", "end_date",
        "n_cashflow_act",          # 经营
        "n_cashflow_inv_act",      # 投资
        "n_cashflow_fin_act",      # 筹资
        "capex",                   # 资本支出（自建扩产）
        "ma_cash",                 # 取得子公司（并购）
        "free_cashflow",           # 自由现金流
        "c_cash_equ_end_period",   # 期末现金
        "fix_assets",              # 固定资产
        "cip",                     # 在建工程
        "fix_assets_chg",          # 固定资产同比变化
        "cip_chg",                 # 在建工程同比变化
        # 保留原始字段备用
        "c_pay_acq_const_fiolta",
        "c_pay_acq_subcom",
        "c_recp_disp_subcom",
    ]
    # 只保留实际存在的列
    cols = [c for c in cols if c in df.columns]
    return df[cols]


def fetch_latest_quarter(ts_code: str, last_annual_date: str) -> pd.DataFrame:
    """
    获取比最新年报更新的季报数据（如有）
    """
    fields = (
        "ts_code,end_date,report_type,"
        "n_cashflow_act,n_cashflow_inv_act,n_cashflow_fin_act,"
        "n_cash_flows_fnc_act,"
        "c_cash_equ_end_period"
    )
    df = pro.cashflow_vip(ts_code=ts_code, report_type="1", fields=fields)
    time.sleep(0.3)

    if df.empty:
        df = pro.cashflow(ts_code=ts_code, report_type="1", fields=fields)
        time.sleep(0.3)

    if df.empty:
        return pd.DataFrame()

    # 兼容普通接口字段名
    if "n_cashflow_fin_act" not in df.columns and "n_cash_flows_fnc_act" in df.columns:
        df = df.rename(columns={"n_cash_flows_fnc_act": "n_cashflow_fin_act"})
    elif "n_cash_flows_fnc_act" in df.columns:
        df = df.drop(columns=["n_cash_flows_fnc_act"])

    # 筛选比最新年报更新的记录
    df = df[df["end_date"] > last_annual_date].copy()
    if df.empty:
        return pd.DataFrame()

    df = df.sort_values("end_date", ascending=False)
    latest = df.iloc[[0]].copy()
    latest["year"] = latest["end_date"].str[:4].astype(int)
    latest["c_pay_acq_const_fiolta"] = None
    latest["free_cashflow"] = None
    return latest


def run(keyword: str, verbose: bool = True) -> pd.DataFrame:
    """
    主入口：获取完整现金流数据并保存
    """
    ts_code, name, list_date = resolve_ts_code(keyword)

    if verbose:
        print(f"{'=' * 60}")
        print(f" {name}（{ts_code}）历史现金流数据获取")
        print(f" 上市日期：{list_date}")
        print(f"{'=' * 60}")

    # 获取年度数据
    df = fetch_annual_cashflow(ts_code)

    if verbose:
        print(f"\n获取到 {len(df)} 年年报数据（{df['year'].min()}-{df['year'].max()}）")

    # 尝试获取最新季报
    if not df.empty:
        last_annual = df["end_date"].iloc[-1]
        df_q = fetch_latest_quarter(ts_code, last_annual)
        if not df_q.empty:
            q_date = df_q["end_date"].iloc[0]
            if verbose:
                print(f"附加最新季报数据：{q_date}")
            # 标记为季报
            df["is_quarterly"] = False
            df_q["is_quarterly"] = True
            cols = df.columns.tolist()
            df_q = df_q.reindex(columns=cols)
            df = pd.concat([df, df_q], ignore_index=True)

    # 保存CSV
    output_path = get_data_path(ts_code, "step1_cashflow")
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    if verbose:
        print(f"\n数据已保存至：{output_path}")

        # 主表
        print(f"\n{'─' * 90}")
        print(f"{'年份':<6} {'经营活动':>8} {'投资活动':>8} {'筹资活动':>8} │{'自建扩产':>8} {'并购支出':>8} │{'自由现金流':>8} {'在建工程':>8}")
        print(f"{'─' * 90}")
        for _, row in df.iterrows():
            yr = str(row["year"])
            if "is_quarterly" in df.columns and row.get("is_quarterly"):
                yr = row["end_date"][:7].replace("-", "Q")
            capex = fmt_yi(row.get("capex")) if "capex" in df.columns else "—"
            ma = fmt_yi(row.get("ma_cash")) if "ma_cash" in df.columns else "—"
            cip_val = fmt_yi(row.get("cip")) if "cip" in df.columns else "—"
            print(
                f"{yr:<6} "
                f"{fmt_yi(row.get('n_cashflow_act')):>8} "
                f"{fmt_yi(row.get('n_cashflow_inv_act')):>8} "
                f"{fmt_yi(row.get('n_cashflow_fin_act')):>8} │"
                f"{capex:>8} "
                f"{ma:>8} │"
                f"{fmt_yi(row.get('free_cashflow')):>8} "
                f"{cip_val:>8}"
            )

        # 年报口径累计
        df_annual = df[~df.get("is_quarterly", False)] if "is_quarterly" in df.columns else df
        print(f"\n{'─' * 90}")
        print(f" 年报口径累计：")
        if "n_cashflow_act" in df_annual.columns:
            print(f"   经营活动合计：{fmt_yi(df_annual['n_cashflow_act'].sum())} 亿元")
        if "n_cashflow_inv_act" in df_annual.columns:
            print(f"   投资活动合计：{fmt_yi(df_annual['n_cashflow_inv_act'].sum())} 亿元")
        if "n_cashflow_fin_act" in df_annual.columns:
            print(f"   筹资活动合计：{fmt_yi(df_annual['n_cashflow_fin_act'].sum())} 亿元")
        if "free_cashflow" in df_annual.columns:
            print(f"   自由现金流合计：{fmt_yi(df_annual['free_cashflow'].sum())} 亿元")
        if "capex" in df_annual.columns:
            print(f"\n 投资活动分解：")
            print(f"   自建扩产累计：{fmt_yi(df_annual['capex'].sum())} 亿元")
            print(f"   并购支出累计：{fmt_yi(df_annual['ma_cash'].sum())} 亿元")
            other_inv = abs(df_annual['n_cashflow_inv_act'].sum()) - df_annual['capex'].sum() - df_annual['ma_cash'].sum()
            print(f"   其他投资支出：{fmt_yi(other_inv)} 亿元")

    return df


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python skill1_cashflow_fetch.py <股票代码或简称>")
        print("示例：python skill1_cashflow_fetch.py 600900")
        print("      python skill1_cashflow_fetch.py 长江电力")
        sys.exit(1)

    keyword = sys.argv[1]
    run(keyword)
