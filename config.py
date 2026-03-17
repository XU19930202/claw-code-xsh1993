"""
共享配置：所有Skill共用的API密钥、工具函数
自动从同目录的 config.yaml 读取 DeepSeek API Key
"""
import os
import yaml

# ============================================================
# 读取 config.yaml（与本文件同目录）
# ============================================================
_HERE = os.path.dirname(os.path.abspath(__file__))
_YAML_PATH = os.path.join(_HERE, "config.yaml")

_yaml_cfg = {}
try:
    with open(_YAML_PATH, "r", encoding="utf-8") as _f:
        _yaml_cfg = yaml.safe_load(_f) or {}
except Exception:
    pass

# ============================================================
# API 配置
# ============================================================
TUSHARE_TOKEN = os.environ.get(
    "TUSHARE_TOKEN",
    "a009b833ddc8257726296c9d51574cb6c18315e937eeeeb79ce4e61e"
)

# DeepSeek：优先环境变量 → 其次 config.yaml → 兜底占位符
DEEPSEEK_API_KEY = (
    os.environ.get("DEEPSEEK_API_KEY")
    or _yaml_cfg.get("llm", {}).get("api_key", "")
    or "your_deepseek_api_key_here"
)
DEEPSEEK_BASE_URL = (
    os.environ.get("DEEPSEEK_BASE_URL")
    or "https://api.deepseek.com/v1"
)

# ============================================================
# 数据目录（中间结果存放）
# ============================================================
DATA_DIR = os.path.join(_HERE, "data")
os.makedirs(DATA_DIR, exist_ok=True)


def get_data_path(ts_code: str, step: str) -> str:
    """
    获取中间数据文件路径
    例: get_data_path("600900.SH", "step1_cashflow") -> data/600900_SH_step1_cashflow.csv
    """
    safe_code = ts_code.replace(".", "_")
    return os.path.join(DATA_DIR, f"{safe_code}_{step}.csv")


def get_report_path(ts_code: str) -> str:
    """获取最终报告路径"""
    safe_code = ts_code.replace(".", "_")
    return os.path.join(DATA_DIR, f"{safe_code}_综合研判报告.md")


def fmt_yi(val) -> str:
    """格式化为亿元字符串，保留2位小数"""
    if val is None or str(val) == "nan":
        return "—"
    try:
        return f"{float(val) / 1e8:.2f}"
    except Exception:
        return "—"


def fmt_yi_with_sign(val) -> str:
    """带正负号的亿元格式化"""
    if val is None or str(val) == "nan":
        return "—"
    try:
        v = float(val) / 1e8
        return f"+{v:.2f}" if v > 0 else f"{v:.2f}"
    except Exception:
        return "—"
