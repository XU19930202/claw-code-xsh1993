import sys
missing = []
for mod in ["tushare", "pandas", "requests", "yaml"]:
    try:
        __import__(mod)
    except ImportError:
        missing.append(mod)
if missing:
    print("MISSING:", missing)
else:
    print("all deps ok")
