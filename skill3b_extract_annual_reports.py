#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skill 3b：年度报告结构化提取工具（替代原skill3的一部分）
使用 DeepSeek AI 从年报 PDF 中提取关键信息

使用方法：
    python skill3b_extract_annual_reports.py --pdf xxx.pdf
    python skill3b_extract_annual_reports.py --dir ~/annual_reports/xxx/
"""

import os
import sys
import json
import re
import time
import argparse
import glob
import csv
from datetime import datetime

# PDF库：优先pdfplumber，回退PyPDF2
PDF_ENGINE = None
try:
    import pdfplumber
    PDF_ENGINE = "pdfplumber"
except ImportError:
    try:
        import PyPDF2
        PDF_ENGINE = "PyPDF2"
    except ImportError:
        print("请安装PDF解析库:")
        print("  pip install pdfplumber   （推荐，中文效果好）")
        print("  pip install PyPDF2       （备选）")
        sys.exit(1)

try:
    import requests
except ImportError:
    print("请安装requests: pip install requests")
    sys.exit(1)


# ============================================================
# 配置区
# ============================================================

# 从环境变量或config.py读取 DeepSeek API Key
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not DEEPSEEK_API_KEY:
    try:
        from config import DEEPSEEK_API_KEY as CFG_KEY
        DEEPSEEK_API_KEY = CFG_KEY
    except:
        pass

if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "your_deepseek_api_key_here":
    print("警告: 未设置DEEPSEEK_API_KEY，将使用占位符")
    DEEPSEEK_API_KEY = ""

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data", "annual_reports_extracted")

MAX_SECTION_CHARS = 30000
CHUNK_SIZE = 25000
API_DELAY = 2.0

# 调试模式
DEBUG = False


# ============================================================
# PDF文本提取
# ============================================================

def extract_text_from_pdf(pdf_path: str) -> list:
    """
    提取PDF每一页的文本
    返回: [(page_num, text), ...]
    """
    pages = []

    if PDF_ENGINE == "pdfplumber":
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total = len(pdf.pages)
                print(f"  PDF共 {total} 页 (引擎: pdfplumber)")
                for i, page in enumerate(pdf.pages):
                    try:
                        text = page.extract_text() or ""
                        pages.append((i + 1, text))
                    except Exception:
                        pages.append((i + 1, ""))
        except Exception as e:
            print(f"  [错误] pdfplumber读取失败: {e}")

    elif PDF_ENGINE == "PyPDF2":
        try:
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                total = len(reader.pages)
                print(f"  PDF共 {total} 页 (引擎: PyPDF2)")
                for i, page in enumerate(reader.pages):
                    try:
                        text = page.extract_text() or ""
                        pages.append((i + 1, text))
                    except Exception:
                        pages.append((i + 1, ""))
        except Exception as e:
            print(f"  [错误] PyPDF2读取失败: {e}")

    return pages


# ============================================================
# 章节定位
# ============================================================

def find_section_by_title(pages: list, start_patterns: list,
                          end_patterns: list) -> tuple:
    """
    通过检测"节标题行"精确定位章节
    """
    start_page = None
    end_page = None

    for page_num, text in pages:
        if not text or len(text) < 20:
            continue

        # 排除目录页：如果一页中出现3个以上"第X节"，大概率是目录
        section_count = len(re.findall(r"第[一二三四五六七八九十\d]+节", text))
        if section_count >= 3:
            continue

        # 逐行检查
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if len(line) < 4 or len(line) > 80:
                continue

            # 查找起始章节标题
            if start_page is None:
                for pattern in start_patterns:
                    title_pattern = rf"^第[一二三四五六七八九十\d]+节\s*{pattern}"
                    if re.search(title_pattern, line):
                        start_page = page_num
                        print(f"    → 起始: 第{page_num}页 [{line[:50]}]")
                        break

            # 查找结束章节标题
            elif end_page is None and page_num > start_page:
                for pattern in end_patterns:
                    title_pattern = rf"^第[一二三四五六七八九十\d]+节\s*{pattern}"
                    if re.search(title_pattern, line):
                        end_page = page_num - 1
                        print(f"    → 结束: 第{end_page}页")
                        break

        if start_page and end_page:
            break

    # 安全兜底
    if start_page and not end_page:
        end_page = min(start_page + 80, len(pages))
        print(f"    → 未找到结束标记，截止到第{end_page}页")

    return (start_page, end_page)


# 章节配置
SECTION_MDA = {
    "start": [
        r"管理层讨论与分析",
        r"经营情况讨论与分析",
        r"经营情况的讨论与分析",
        r"董事会报告",
    ],
    "end": [
        r"公司治理",
        r"环境和社会责任",
        r"重要事项",
        r"企业社会责任",
        r"内部控制",
    ],
}

SECTION_IMPORTANT = {
    "start": [
        r"重要事项",
        r"重大事项",
    ],
    "end": [
        r"股份变动",
        r"股本变动",
        r"优先股",
        r"董事、监事、高级管理人员",
        r"财务报告",
        r"备查文件",
    ],
}


def extract_section_text(pages: list, start_page: int, end_page: int,
                         max_chars: int = MAX_SECTION_CHARS) -> str:
    """提取指定页码范围的文本"""
    texts = []
    total_chars = 0

    for page_num, text in pages:
        if page_num < start_page or page_num > end_page:
            continue
        if not text:
            continue

        text = clean_text(text)

        if total_chars + len(text) > max_chars:
            remaining = max_chars - total_chars
            if remaining > 200:
                texts.append(text[:remaining])
            break

        texts.append(text)
        total_chars += len(text)

    return "\n".join(texts)


def clean_text(text: str) -> str:
    """清理PDF文本"""
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\d+\s*/\s*\d+", "", text)
    text = re.sub(r" {3,}", " ", text)
    return text.strip()


# ============================================================
# DeepSeek API
# ============================================================

def call_deepseek(system_prompt: str, user_content: str) -> str:
    """调用DeepSeek API"""
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "your_deepseek_api_key_here":
        print("  [错误] 未设置有效的DEEPSEEK_API_KEY")
        print("  提示: 请在 config.yaml 中设置 llm.api_key")
        return ""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
    }

    try:
        resp = requests.post(
            DEEPSEEK_API_URL, headers=headers, json=payload, timeout=180
        )
        resp.raise_for_status()
        result = resp.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"  [错误] API调用失败: {e}")
        return ""


def call_deepseek_chunked(system_prompt: str, text: str,
                          chunk_size: int = CHUNK_SIZE) -> str:
    """
    如果文本超长，分段发送后合并
    """
    if len(text) <= chunk_size:
        return call_deepseek(system_prompt, text)

    # 分段
    mid = len(text) // 2
    cut_point = text.rfind("\n", mid - 500, mid + 500)
    if cut_point == -1:
        cut_point = mid

    part1 = text[:cut_point]
    part2 = text[cut_point:]

    print(f"    文本过长({len(text)}字符)，分两段提取...")

    # 第一段
    result1 = call_deepseek(system_prompt, part1)
    time.sleep(API_DELAY)

    # 第二段：把第一段的结果作为上下文
    merge_prompt = system_prompt + f"""

注意：这是同一份年报的后续内容。前面部分已经提取的结果如下，请与之合并，补充新发现的信息，更新已有字段：
{result1}

请输出合并后的完整JSON。"""

    result2 = call_deepseek(merge_prompt, part2)

    return result2 if result2 else result1


# ============================================================
# 提取Prompt
# ============================================================

MDA_EXTRACT_PROMPT = """你是一个专业的A股上市公司年报分析师。请从以下年度报告"经营情况讨论与分析"章节中提取关键信息。

提取规则：
1. 只提取文本中明确出现的数据，不要猜测或推算
2. 如果某个字段在文本中确实没有提及，填null
3. 数字请保留原文的单位（万元、亿元、吨、万吨等）
4. 百分比保留到小数点后两位
5. 注意区分"设计产能"和"实际产量"

请严格按以下JSON格式输出：

```json
{
  "核心经营指标": {
    "营业收入": "xxx（含单位）",
    "营业收入同比": "xx.xx%",
    "归母净利润": "xxx（含单位）",
    "归母净利润同比": "xx.xx%",
    "扣非净利润": "xxx（含单位）",
    "扣非净利润同比": "xx.xx%",
    "经营活动现金流净额": "xxx（含单位）",
    "资本支出": "购建固定资产等支付的现金，含单位",
    "研发投入": "xxx（含单位）",
    "研发投入占营收比": "xx.xx%"
  },
  "主营业务构成": [
    {
      "业务或产品": "xxx",
      "营业收入": "xxx（含单位）",
      "占总营收比": "xx%",
      "同比变化": "xx%",
      "毛利率": "xx%"
    }
  ],
  "产能信息": [
    {
      "产品名称": "xxx",
      "设计产能": "xxx（含单位）",
      "实际产量": "xxx（含单位）",
      "产能利用率": "xx%",
      "产销率": "xx%",
      "同比变化": "说明"
    }
  ],
  "在建工程及募投项目": [
    {
      "项目名称": "xxx",
      "项目类型": "在建工程/募投项目/技改",
      "计划总投资": "xxx（含单位）",
      "累计投入": "xxx（含单位）",
      "投资进度": "xx%",
      "预计投产时间": "xxxx年",
      "预计新增产能": "xxx",
      "当前状态": "建设中/已投产/延期/终止"
    }
  ],
  "行业与竞争": "概括公司所处行业格局、竞争地位、市场份额等关键信息，100字以内",
  "管理层展望": "概括管理层对下一年度的经营计划、战略方向，100字以内"
}
```

只输出JSON，不要输出其他内容。"""


IMPORTANT_MATTERS_PROMPT = """你是一个专业的A股上市公司年报分析师。请从以下年度报告"重要事项"章节中提取关键信息。

提取规则：
1. 只提取文本中明确出现的数据
2. 如果某项信息年报中确实未提及，对应字段填null
3. 如果整个类别都没有相关内容（如没有并购），该数组填空数组[]
4. 金额保留原文单位

请严格按以下JSON格式输出：

```json
{
  "并购及重大投资": [
    {
      "事项类型": "收购/出售/合并/重组/对外投资",
      "标的或项目": "xxx",
      "交易对手方": "xxx",
      "交易金额": "xxx（含单位）",
      "支付方式": "现金/股份/混合",
      "估值及方法": "xxx",
      "业绩承诺": "承诺内容及期限",
      "完成状态": "已完成/进行中/已终止/审批中",
      "对公司影响": "简要说明对营收、利润、业务的影响"
    }
  ],
  "关联交易": [
    {
      "关联方": "xxx",
      "交易内容": "xxx",
      "交易金额": "xxx（含单位）",
      "定价依据": "市场价/协议价等"
    }
  ],
  "对外担保": {
    "担保总额": "xxx（含单位）",
    "占净资产比例": "xx%",
    "是否有逾期担保": "是/否"
  },
  "重大诉讼仲裁": "概括重大诉讼情况及可能影响，无则填null",
  "股权激励": "概括股权激励计划情况，无则填null",
  "承诺履行": "概括重要承诺及履行情况",
  "控制权变更风险": "是否存在控制权变更的风险或计划，无则填null"
}
```

只输出JSON，不要输出其他内容。"""


# ============================================================
# 核心处理
# ============================================================

def parse_json_response(raw_text: str) -> dict:
    """解析DeepSeek返回的JSON"""
    if not raw_text:
        return {}

    text = raw_text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError) as e:
            print(f"  [警告] JSON解析失败: {str(e)[:80]}")
            return {"_raw_response": raw_text[:3000]}


def parse_filename(filename: str) -> dict:
    """从文件名解析信息"""
    info = {"code": "", "name": "", "year": ""}
    match = re.match(r"(\d{6})_(.+?)_(\d{4})年", filename)
    if match:
        info["code"] = match.group(1)
        info["name"] = match.group(2)
        info["year"] = match.group(3)
    return info


def process_single_pdf(pdf_path: str, output_dir: str) -> dict:
    """处理单个年报PDF"""
    filename = os.path.basename(pdf_path)
    print(f"\n{'='*60}")
    print(f"处理: {filename}")
    print(f"{'='*60}")

    info = parse_filename(filename)

    # 1. 提取PDF文本
    print(f"  [1/5] 提取PDF文本...")
    pages = extract_text_from_pdf(pdf_path)
    if not pages:
        print(f"  [错误] 无法提取PDF文本")
        return None

    total_text = sum(len(t) for _, t in pages)
    print(f"  总计 {total_text:,} 字符，{len(pages)} 页")

    # 2. 定位经营分析章节
    print(f"  [2/5] 定位经营分析章节...")
    mda_start, mda_end = find_section_by_title(
        pages, SECTION_MDA["start"], SECTION_MDA["end"]
    )

    mda_text = ""
    if mda_start:
        mda_text = extract_section_text(pages, mda_start, mda_end)
        print(f"  经营分析: 第{mda_start}~{mda_end}页, {len(mda_text):,}字符")
    else:
        print(f"  [警告] 未定位到经营分析章节")

    # 3. 定位重要事项章节
    print(f"  [3/5] 定位重要事项章节...")
    im_start, im_end = find_section_by_title(
        pages, SECTION_IMPORTANT["start"], SECTION_IMPORTANT["end"]
    )

    im_text = ""
    if im_start:
        im_text = extract_section_text(pages, im_start, im_end)
        print(f"  重要事项: 第{im_start}~{im_end}页, {len(im_text):,}字符")
    else:
        print(f"  [警告] 未定位到重要事项章节")

    # 调试：保存切片文本
    if DEBUG:
        debug_dir = os.path.join(output_dir, "_debug")
        os.makedirs(debug_dir, exist_ok=True)
        if mda_text:
            with open(os.path.join(debug_dir, f"{info['code']}_{info['year']}_mda.txt"),
                       "w", encoding="utf-8") as f:
                f.write(mda_text)
        if im_text:
            with open(os.path.join(debug_dir, f"{info['code']}_{info['year']}_important.txt"),
                       "w", encoding="utf-8") as f:
                f.write(im_text)

    # 4. AI提取经营分析
    print(f"  [4/5] AI提取经营分析...")
    mda_result = {}
    if mda_text and len(mda_text) > 200:
        raw = call_deepseek_chunked(MDA_EXTRACT_PROMPT, mda_text)
        mda_result = parse_json_response(raw)
        if mda_result and "_raw_response" not in mda_result:
            print(f"  [OK] 经营分析提取成功")
        else:
            print(f"  [WARN] 经营分析提取可能不完整")
    else:
        print(f"  [跳过] 文本不足")

    time.sleep(API_DELAY)

    # 5. AI提取重要事项
    print(f"  [5/5] AI提取重要事项...")
    im_result = {}
    if im_text and len(im_text) > 200:
        raw = call_deepseek_chunked(IMPORTANT_MATTERS_PROMPT, im_text)
        im_result = parse_json_response(raw)
        if im_result and "_raw_response" not in im_result:
            print(f"  [OK] 重要事项提取成功")
        else:
            print(f"  [WARN] 重要事项提取可能不完整")
    else:
        print(f"  [跳过] 文本不足")

    # 组装结果
    result = {
        "文件名": filename,
        "股票代码": info.get("code", ""),
        "股票名称": info.get("name", ""),
        "报告年度": info.get("year", ""),
        "处理时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "经营分析": mda_result,
        "重要事项": im_result,
        "元信息": {
            "PDF引擎": PDF_ENGINE,
            "PDF总页数": len(pages),
            "经营分析章节": f"第{mda_start}页~第{mda_end}页" if mda_start else "未定位",
            "重要事项章节": f"第{im_start}页~第{im_end}页" if im_start else "未定位",
            "经营分析文本长度": len(mda_text),
            "重要事项文本长度": len(im_text),
        },
    }

    # 保存JSON
    save_result(result, output_dir)
    return result


def save_result(result: dict, output_dir: str):
    """保存提取结果"""
    os.makedirs(output_dir, exist_ok=True)

    code = result.get("股票代码", "unknown")
    year = result.get("报告年度", "unknown")
    name = result.get("股票名称", "")

    filename = f"{code}_{name}_{year}年_提取结果.json"
    for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        filename = filename.replace(char, '_')

    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  → 保存: {filepath}")


def generate_summary(results: list, output_dir: str):
    """生成CSV汇总表"""
    if not results:
        return

    os.makedirs(output_dir, exist_ok=True)

    # 核心指标汇总
    path1 = os.path.join(output_dir, "核心经营指标汇总.csv")
    with open(path1, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["代码", "名称", "年度", "营业收入", "营收同比",
                     "归母净利润", "净利同比", "扣非净利润", "扣非同比",
                     "经营现金流", "资本支出", "研发投入", "研发占比",
                     "行业与竞争", "管理层展望"])
        for r in results:
            mda = r.get("经营分析", {})
            if not isinstance(mda, dict):
                continue
            c = mda.get("核心经营指标", {}) or {}
            w.writerow([
                r.get("股票代码"), r.get("股票名称"), r.get("报告年度"),
                c.get("营业收入"), c.get("营业收入同比"),
                c.get("归母净利润"), c.get("归母净利润同比"),
                c.get("扣非净利润"), c.get("扣非净利润同比"),
                c.get("经营活动现金流净额"), c.get("资本支出"),
                c.get("研发投入"), c.get("研发投入占营收比"),
                mda.get("行业与竞争", ""), mda.get("管理层展望", ""),
            ])
    print(f"  核心指标: {path1}")

    # 并购汇总
    path2 = os.path.join(output_dir, "并购及重大投资汇总.csv")
    with open(path2, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["代码", "名称", "年度", "类型", "标的/项目",
                     "对手方", "金额", "支付方式", "业绩承诺",
                     "状态", "影响"])
        for r in results:
            im = r.get("重要事项", {})
            if not isinstance(im, dict):
                continue
            for deal in (im.get("并购及重大投资") or []):
                if not isinstance(deal, dict):
                    continue
                w.writerow([
                    r.get("股票代码"), r.get("股票名称"), r.get("报告年度"),
                    deal.get("事项类型"), deal.get("标的或项目"),
                    deal.get("交易对手方"), deal.get("交易金额"),
                    deal.get("支付方式"), deal.get("业绩承诺"),
                    deal.get("完成状态"), deal.get("对公司影响"),
                ])
    print(f"  并购投资: {path2}")


def run(pdf_dir: str, annual_years: int = 3, verbose: bool = True, skip_existing: bool = True) -> dict:
    """
    主入口：提取目录下所有年报PDF
    pdf_dir: PDF文件目录
    annual_years: 只处理最近N年的年报（0=全部）
    """
    if verbose:
        print(f"{'=' * 70}")
        print(f" 年度报告结构化提取工具")
        print(f" 目录：{pdf_dir}")
        print(f"{'=' * 70}")
    
    # 收集PDF文件
    pdf_files = sorted(glob.glob(os.path.join(pdf_dir, "*年度报告*.pdf")))
    
    if not pdf_files:
        return {"success": False, "error": "未找到PDF文件"}
    
    # 如果指定年份，过滤文件
    if annual_years > 0:
        current_year = datetime.now().year
        years_to_process = set(str(y) for y in range(current_year - annual_years + 1, current_year + 1))
        filtered = []
        for pdf in pdf_files:
            info = parse_filename(os.path.basename(pdf))
            if info.get("year") in years_to_process:
                filtered.append(pdf)
        pdf_files = filtered
    
    if not pdf_files:
        return {"success": False, "error": "未找到指定年份的PDF文件"}
    
    # 跳过已处理
    if skip_existing:
        filtered = []
        for pdf in pdf_files:
            info = parse_filename(os.path.basename(pdf))
            expected = os.path.join(
                OUTPUT_DIR,
                f"{info['code']}_{info['name']}_{info['year']}年_提取结果.json")
            if os.path.exists(expected):
                if verbose:
                    print(f"  [跳过] {os.path.basename(pdf)}")
            else:
                filtered.append(pdf)
        pdf_files = filtered
    
    if not pdf_files:
        return {"success": True, "processed": 0, "message": "所有文件已处理"}
    
    if verbose:
        print(f"\n待处理: {len(pdf_files)} 份")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    all_results = []
    for i, pdf in enumerate(pdf_files, 1):
        if verbose:
            print(f"  >>> [{i}/{len(pdf_files)}]")
        result = process_single_pdf(pdf, OUTPUT_DIR)
        if result:
            all_results.append(result)
        if i < len(pdf_files):
            time.sleep(API_DELAY)
    
    # 生成汇总
    if all_results:
        if verbose:
            print(f"\n{'='*60}")
            print("生成汇总表...")
        generate_summary(all_results, OUTPUT_DIR)
    
    return {
        "success": True,
        "processed": len(all_results),
        "total": len(pdf_files),
        "output_dir": OUTPUT_DIR,
        "results": all_results
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="年度报告结构化提取工具")
    parser.add_argument("--pdf", type=str, help="单个PDF路径")
    parser.add_argument("--dir", type=str, help="PDF目录")
    parser.add_argument("--years", type=int, default=3, help="只处理最近几年")
    args = parser.parse_args()
    
    if args.pdf:
        result = process_single_pdf(args.pdf, OUTPUT_DIR)
    elif args.dir:
        result = run(args.dir, annual_years=args.years)
    else:
        print("请指定 --pdf 或 --dir")
        sys.exit(1)
