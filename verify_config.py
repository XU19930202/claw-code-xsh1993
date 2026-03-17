import sys
sys.path.insert(0, r'C:\Users\Lenovo\WorkBuddy\20260311213700')
from config import TUSHARE_TOKEN, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DATA_DIR
print("TUSHARE_TOKEN:", TUSHARE_TOKEN[:8] + "...")
print("DEEPSEEK_API_KEY:", DEEPSEEK_API_KEY[:8] + "...")
print("DEEPSEEK_BASE_URL:", DEEPSEEK_BASE_URL)
print("DATA_DIR:", DATA_DIR)
