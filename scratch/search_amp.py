import glob

for fn in glob.glob("static/*.*") + glob.glob("*.py"):
    with open(fn, "r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f, 1):
            if '"&' in line or '&"' in line:
                print(f"{fn}:{i}: {line.strip()}")
