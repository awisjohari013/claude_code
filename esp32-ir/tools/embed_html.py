# Skrip pra-bina PlatformIO: tukar web/index.html -> src/web_ui.h
# supaya halaman web disimpan terus dalam firmware (tak perlu upload filesystem).
import os

try:
    Import("env")  # noqa: F821  (disediakan oleh PlatformIO)
    root = env["PROJECT_DIR"]  # noqa: F821
except NameError:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

src = os.path.join(root, "web", "index.html")
dst = os.path.join(root, "src", "web_ui.h")

with open(src, "r", encoding="utf-8") as f:
    html = f.read()

if ')HTMLRAW"' in html:
    raise SystemExit("index.html tidak boleh mengandungi ')HTMLRAW\"'")

out = (
    "// FAIL INI DIJANA AUTOMATIK daripada web/index.html - jangan edit terus.\n"
    "#pragma once\n#include <Arduino.h>\n\n"
    'static const char INDEX_HTML[] PROGMEM = R"HTMLRAW(' + html + ')HTMLRAW";\n'
)

old = None
if os.path.exists(dst):
    with open(dst, "r", encoding="utf-8") as f:
        old = f.read()
if old != out:
    with open(dst, "w", encoding="utf-8") as f:
        f.write(out)
    print("embed_html: src/web_ui.h dikemas kini")
