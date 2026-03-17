import shutil, os
src = r'C:\Users\Lenovo\Downloads'
dst = r'C:\Users\Lenovo\WorkBuddy\20260311213700'
files = [
    'skill1_cashflow_fetch.py',
    'skill2_cashflow_classify.py',
    'skill3_ma_events_fetch.py',
    'skill4_comprehensive.py',
    'pipeline_run.py',
]
for f in files:
    s = os.path.join(src, f)
    d = os.path.join(dst, f)
    shutil.copy2(s, d)
    print(f'copied: {f}')
print('done')
