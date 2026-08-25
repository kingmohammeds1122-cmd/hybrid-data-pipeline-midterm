from pathlib import Path
import re
import shutil

path = Path(r"D:\midterm-data-pipeline\src\quality_rules.py")
backup = path.with_name("quality_rules.py.broken")
shutil.copy2(path, backup)
text = path.read_text(encoding="utf-8-sig")

replacement = '''ARABIC_DIGIT_TRANSLATION = str.maketrans(
    {
        **{chr(0x660 + i): str(i) for i in range(10)},
        **{chr(0x6F0 + i): str(i) for i in range(10)},
    }
)
'''

pattern = r"ARABIC_DIGIT_TRANSLATION\s*=\s*str\.maketrans\(.*?\n\)\n"
text, replaced = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
if replaced != 1:
    raise SystemExit("Could not locate ARABIC_DIGIT_TRANSLATION block; no final repair made.")

if '"%d-%m-%Y %H:%M:%S",' not in text:
    target = '        "%d-%m-%Y",\n'
    if target not in text:
        raise SystemExit("Could not locate date-format line; no final repair made.")
    text = text.replace(
        target,
        '        "%d-%m-%Y %H:%M:%S",\n' + target,
        1,
    )

path.write_text(text, encoding="utf-8", newline="\n")
print("Repair completed; backup:", backup)
