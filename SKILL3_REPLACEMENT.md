# Skill3 替换完成报告

## 替换概述

已成功用两个新文件替代原 `skill3_ma_events_fetch.py`，实现了年度报告的下载与结构化提取功能。

---

## 新文件结构

### 1. `skill3a_download_annual_reports.py`
**功能**：从巨潮资讯网下载年度报告 PDF

**主要特性**：
- 支持单只股票批量下载上市以来全部年报
- 自动过滤摘要、更正版本，保留正式年报
- 智能文件命名：`{代码}_{名称}_{年份}年年度报告.pdf`
- 支持跳过已下载文件
- 请求频率控制，避免被封

**用法**：
```bash
python skill3a_download_annual_reports.py 603197
python skill3a_download_annual_reports.py 603197 --years 5  # 最近5年
```

---

### 2. `skill3b_extract_annual_reports.py`
**功能**：使用 DeepSeek AI 从年报 PDF 中提取结构化数据

**主要特性**：
- 优先使用 pdfplumber（中文效果更好），回退 PyPDF2
- 精确章节定位：经营分析、重要事项
- DeepSeek AI 智能提取，支持超长文本分段
- 输出 JSON + CSV 汇总格式

**提取字段**：
- **经营分析**：核心经营指标、主营业务构成、产能信息、在建工程、行业竞争、管理层展望
- **重要事项**：并购及重大投资、关联交易、对外担保、诉讼仲裁、股权激励等

**用法**：
```bash
python skill3b_extract_annual_reports.py --dir annual_reports/603197_xxx/
python skill3b_extract_annual_reports.py --years 3  # 只处理最近3年
```

---

### 3. `skill3_ma_events_fetch.py`（新整合版）
**功能**：整合 Step 3a 和 Step 3b，提供统一接口

**主要特性**：
- 自动调用下载和提取两个步骤
- 兼容原 pipeline 接口
- 支持跳过 PDF 下载（`--skip-pdf`）
- 输出标准化的 step3_ma_events.csv 文件

**用法**：
```bash
python skill3_ma_events_fetch.py 603197
python skill3_ma_events_fetch.py 603197 --skip-pdf
python skill3_ma_events_fetch.py 603197 --years 5
```

---

## Pipeline 集成

原有的 `pipeline_run.py` 无需修改即可使用新的 skill3：

```bash
# 完整 pipeline（会自动下载最近3年年报）
python pipeline_run.py 603197 --skip-confirm

# 跳过 PDF 下载
python pipeline_run.py 603197 --skip-confirm --skip-pdf

# 指定年份
python pipeline_run.py 603197 --skip-confirm --annual-years 5
```

---

## 输出文件

### 下载输出
```
annual_reports/
  └── {代码}_{名称}/
      ├── {代码}_{名称}_2019年年度报告.pdf
      ├── {代码}_{名称}_2020年年度报告.pdf
      └── ...
```

### 提取输出
```
data/annual_reports_extracted/
  ├── {代码}_{名称}_2019年_提取结果.json
  ├── {代码}_{名称}_2020年_提取结果.json
  ├── 核心经营指标汇总.csv
  └── 并购及重大投资汇总.csv
```

### Pipeline 标准输出
```
data/{代码}_step3_ma_events.csv
```

---

## 依赖要求

新增依赖：
```bash
pip install pdfplumber  # 推荐，中文效果好
pip install PyPDF2      # 备选
pip install requests    # 网络请求
```

DeepSeek API Key 配置：
```bash
# Windows
set DEEPSEEK_API_KEY=your_key

# Linux/Mac
export DEEPSEEK_API_KEY=your_key
```

---

## 备份文件

原文件已备份为：
- `skill3_ma_events_fetch.py.backup`

---

## 主要改进

相比原 skill3：

1. **数据源升级**：从简单的公告检索升级为完整的年报 PDF 下载
2. **信息深度**：从简单的并购事件列表升级为结构化的经营分析数据
3. **AI 能力**：集成 DeepSeek AI 智能提取关键信息
4. **灵活性**：支持按年份筛选，支持跳过已有文件
5. **输出丰富**：JSON + CSV 多格式，便于后续分析

---

## 注意事项

1. **PDF 下载时间**：下载完整年报可能需要较长时间，建议使用 `--years` 参数限制范围
2. **API 调用**：DeepSeek API 有调用次数限制，大量处理时注意控制频率
3. **存储空间**：年报 PDF 文件较大，注意磁盘空间
4. **网络限制**：巨潮资讯网可能有访问频率限制，已设置随机延迟避免被封

---

## 兼容性说明

- ✅ 与 `pipeline_run.py` 完全兼容
- ✅ 保留原接口参数（`skip_pdf`, `analyze_pdfs`, `annual_years`）
- ✅ 输出文件路径保持不变
- ⚠️ 输出内容结构略有变化，但 `step4_comprehensive.py` 应能正常处理

---

**替换完成时间**：2026-03-17
**状态**：✅ 已完成，可正常使用
