import re
import subprocess

with open('templates/index.html', encoding='utf-8') as f:
    html = f.read()

script = re.search(r'<script>(.*?)</script>', html, re.DOTALL).group(1)
fixed = script.replace("`' OR '1'='1`", "'\\' OR \\'1\\'=\\'1'")

with open('scratch/temp.js', 'w', encoding='utf-8') as f:
    f.write(fixed)

p = subprocess.run(['node', '--check', 'scratch/temp.js'], capture_output=True, text=True, encoding='utf-8')
print("STDOUT:", p.stdout)
print("STDERR:", p.stderr)
print("RETURNCODE:", p.returncode)
