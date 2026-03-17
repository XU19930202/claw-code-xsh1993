#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skill 3：年度报告下载与提取（v3 - 整合版）
──────────────────────────────────────
输入：股票代码
输出：
  - Step3a: 下载年度报告PDF
  - Step3b: 提取年报结构化数据（DeepSeek AI）

数据源：
  - 巨潮资讯网（cninfo.com.cn）- 年度报告下载
  - DeepSeek AI - 结构化提取

用法：
    python skill3_ma_events_fetch.py 600900.SH
    python skill3_ma_events_fetch.py 长江电力
    python skill3_ma_events_fetch.py 603197 --skip-pdf      # 跳过下载
    python skill3_ma_events_fetch.py 603197 --years 5       # 最近5年
"""

import sys
import os
import pandas as pd
from config import get_data_path

# 导入新的两个技能
from skill3a_download_annual_reports import run as download_run
from skill3b_extract_annual_reports import run as extract_run


def run(ts_code_or_keyword: str, verbose: bool = True, skip_pdf: bool = False, 
        annual_years: int = 3, analyze_pdfs: bool = False) -> dict:
    """
    主入口：下载并提取年度报告
    
    参数：
        ts_code_or_keyword: 股票代码或简称
        skip_pdf: 跳过PDF下载，直接提取已有文件
        annual_years: 下载/提取最近几年的年报（0=全部）
        analyze_pdfs: 保留参数兼容性（已自动执行）
    
    返回：
        dict: 包含下载和提取结果
    """
    # 简化代码
    stock_code = ts_code_or_keyword.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    
    if verbose:
        print(f"\n{'=' * 70}")
        print(f"  年度报告下载与提取 v3")
        print(f"  标的：{stock_code}")
        print(f"  年份范围：{'全部' if annual_years == 0 else f'最近{annual_years}年'}")
        print(f"{'=' * 70}")
    
    result = {
        "stock_code": stock_code,
        "download": None,
        "extract": None,
        "success": False
    }
    
    # Step 3a: 下载年度报告PDF
    if not skip_pdf:
        if verbose:
            print(f"\n{'█' * 70}")
            print(f"█  STEP 3a: 下载年度报告PDF")
            print(f"{'█' * 70}\n")
        
        download_result = download_run(stock_code, annual_years=annual_years, verbose=verbose)
        result["download"] = download_result
        
        if not download_result.get("success"):
            if verbose:
                print(f"\n[失败] PDF下载失败")
            return result
        
        pdf_dir = download_result.get("pdf_dir")
    else:
        if verbose:
            print(f"\n[跳过] PDF下载已跳过")
        # 尝试自动找到PDF目录
        pdf_dir = os.path.join(os.path.dirname(__file__), "annual_reports", f"{stock_code}_*")
        import glob
        matches = glob.glob(pdf_dir)
        if matches:
            pdf_dir = matches[0]
            if verbose:
                print(f"[使用] 现有PDF目录: {pdf_dir}")
        else:
            pdf_dir = None
    
    # Step 3b: 提取年报结构化数据
    if pdf_dir and os.path.exists(pdf_dir):
        if verbose:
            print(f"\n{'█' * 70}")
            print(f"█  STEP 3b: 提取年报结构化数据（DeepSeek AI）")
            print(f"{'█' * 70}\n")
        
        extract_result = extract_run(pdf_dir, annual_years=annual_years, verbose=verbose)
        result["extract"] = extract_result
        
        if extract_result.get("success"):
            result["success"] = True
            
            # 保存结果到标准路径
            output_path = get_data_path(stock_code, "step3_ma_events")
            
            # 尝试读取提取的并购数据
            ma_summary_path = os.path.join(extract_result.get("output_dir", ""), "并购及重大投资汇总.csv")
            if os.path.exists(ma_summary_path):
                df = pd.read_csv(ma_summary_path, encoding="utf-8-sig")
                
                # 转换为标准格式
                events = []
                for _, row in df.iterrows():
                    year = str(row.get("年度", ""))
                    event_type = row.get("类型", "")
                    detail = f"{row.get('标的/项目', '')} - {row.get('对手方', '')} - {row.get('金额', '')}"
                    if row.get("支付方式"):
                        detail += f" ({row.get('支付方式')})"
                    if row.get("状态"):
                        detail += f" - {row.get('状态')}"
                    
                    events.append({
                        "event_date": f"{year}-12-31",
                        "year": year,
                        "event_type": event_type,
                        "detail": detail,
                        "source": "年度报告提取"
                    })
                
                if events:
                    df_events = pd.DataFrame(events)
                    df_events.to_csv(output_path, index=False, encoding="utf-8-sig")
                    if verbose:
                        print(f"\n[成功] Step 3 完成: {output_path}")
                        print(f"[统计] 提取到 {len(events)} 条并购事件")
                else:
                    # 创建空文件但添加年度记录
                    core_metrics_path = os.path.join(extract_result.get("output_dir", ""), "核心经营指标汇总.csv")
                    if os.path.exists(core_metrics_path):
                        df_metrics = pd.read_csv(core_metrics_path, encoding="utf-8-sig")
                        events = []
                        for _, row in df_metrics.iterrows():
                            year = str(row.get("年度", ""))
                            name = row.get("名称", "")
                            rev = row.get("营业收入", "")
                            rev_growth = row.get("营收同比", "")
                            profit = row.get("归母净利润", "")
                            profit_growth = row.get("净利同比", "")
                            cf = row.get("经营现金流", "")
                            rd = row.get("研发投入", "")
                            
                            detail = f"营收:{rev} 同比:{rev_growth} 净利:{profit} 经营现金流:{cf} 研发:{rd}"
                            
                            events.append({
                                "event_date": f"{year}-12-31",
                                "year": year,
                                "event_type": "年度经营数据",
                                "detail": detail,
                                "source": "年度报告提取"
                            })
                        
                        if events:
                            df_events = pd.DataFrame(events)
                            df_events.to_csv(output_path, index=False, encoding="utf-8-sig")
                            if verbose:
                                print(f"\n[成功] Step 3 完成: {output_path}")
                                print(f"[统计] 提取到 {len(events)} 年度经营数据记录")
            else:
                # 创建空文件
                df_empty = pd.DataFrame(columns=["event_date", "year", "event_type", "detail", "source"])
                df_empty.to_csv(output_path, index=False, encoding="utf-8-sig")
                if verbose:
                    print(f"\n[成功] Step 3 完成: {output_path}")
                    print(f"[提示] 未提取到并购或经营数据")
        else:
            if verbose:
                print(f"\n[提示] 提取失败或无新文件处理")
    else:
        if verbose:
            print(f"\n[失败] 未找到PDF目录")
    
    if verbose and result["success"]:
        print(f"\n{'=' * 70}")
        print(f"  [成功] Step 3 完成！")
        print(f"{'=' * 70}")
    
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="年度报告下载与提取")
    parser.add_argument("stock", help="股票代码或简称")
    parser.add_argument("--skip-pdf", action="store_true", help="跳过PDF下载")
    parser.add_argument("--years", type=int, default=3, help="最近几年（0=全部）")
    args = parser.parse_args()
    
    run(args.stock, skip_pdf=args.skip_pdf, annual_years=args.years)
