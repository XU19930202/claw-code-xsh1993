"""
Pipeline Runner v3
用法：
    python pipeline_run.py 拓普集团
    python pipeline_run.py 601689 --skip-confirm
    python pipeline_run.py 601689 --skip-confirm --skip-pdf
    python pipeline_run.py 601689 --from-step 3
"""

import sys
import argparse
from config import get_data_path, get_report_path


def parse_args():
    parser = argparse.ArgumentParser(description="现金流分析Pipeline v3")
    parser.add_argument("stock", help="股票代码或简称")
    parser.add_argument("--from-step", type=int, default=1, choices=[1, 2, 3, 4])
    parser.add_argument("--only-step", type=int, default=None, choices=[1, 2, 3, 4])
    parser.add_argument("--skip-confirm", action="store_true")
    parser.add_argument("--skip-pdf", action="store_true", help="Step3跳过PDF下载")
    parser.add_argument("--annual-years", type=int, default=3, help="下载最近几年年报")
    return parser.parse_args()


def main():
    args = parse_args()
    stock = args.stock

    if args.only_step:
        steps = [args.only_step]
    else:
        steps = list(range(args.from_step, 5))

    print(f"\n{'═' * 70}")
    print(f"  现金流分析Pipeline v3")
    print(f"  标的：{stock}")
    print(f"  步骤：{' → '.join([f'Step{s}' for s in steps])}")
    print(f"{'═' * 70}")

    from skill1_cashflow_fetch import resolve_ts_code
    ts_code, name, list_date = resolve_ts_code(stock)
    print(f"\n  {name}（{ts_code}）上市日期：{list_date}\n")

    # Step 1
    if 1 in steps:
        print(f"\n{'█' * 70}")
        print(f"█  STEP 1: 现金流数据获取（含投资分解+资产负债表）")
        print(f"{'█' * 70}\n")
        import skill1_cashflow_fetch as s1
        df = s1.run(ts_code, verbose=True)
        if df.empty:
            print("❌ 数据获取失败"); sys.exit(1)
        print(f"\n✅ Step 1 完成: {get_data_path(ts_code, 'step1_cashflow')}")
        if not args.skip_confirm and len(steps) > 1:
            r = input("\n继续? [Y/n] ").strip().lower()
            if r == "n": sys.exit(0)

    # Step 2
    if 2 in steps:
        print(f"\n{'█' * 70}")
        print(f"█  STEP 2: 现金流结构分析（八种组合框架）")
        print(f"{'█' * 70}\n")
        import skill2_cashflow_classify as s2
        df = s2.run(ts_code, verbose=True)
        if df.empty:
            print("❌ 分析失败"); sys.exit(1)
        print(f"\n✅ Step 2 完成: {get_data_path(ts_code, 'step2_classified')}")
        if not args.skip_confirm and len(steps) > 1 and 3 in steps:
            r = input("\n继续? [Y/n] ").strip().lower()
            if r == "n": sys.exit(0)

    # Step 3
    if 3 in steps:
        print(f"\n{'█' * 70}")
        print(f"█  STEP 3: 事件获取 + PDF下载")
        print(f"{'█' * 70}\n")
        import skill3_ma_events_fetch as s3
        df = s3.run(ts_code, verbose=True,
                     skip_pdf=args.skip_pdf, annual_years=args.annual_years)
        print(f"\n✅ Step 3 完成: {get_data_path(ts_code, 'step3_ma_events')}")
        if not args.skip_confirm and len(steps) > 1 and 4 in steps:
            r = input("\n继续? [Y/n] ").strip().lower()
            if r == "n": sys.exit(0)

    # Step 4
    if 4 in steps:
        print(f"\n{'█' * 70}")
        print(f"█  STEP 4: 综合研判（DeepSeek AI）")
        print(f"{'█' * 70}\n")
        import skill4_comprehensive as s4
        report = s4.run(ts_code, verbose=True)
        print(f"\n✅ Step 4 完成: {get_report_path(ts_code)}")

    print(f"\n{'═' * 70}")
    print(f"  ✅ Pipeline 完成！")
    print(f"{'═' * 70}")


if __name__ == "__main__":
    main()
