import os, re

PHP_PCT = float(os.getenv("PHP_PCT", "40"))
VUE_PCT = float(os.getenv("VUE_PCT", "40"))
OUTRAS_PCT = float(os.getenv("OUTRAS_PCT", "20"))

def render_mermaid(php, vue, outras):
    return (
        "```mermaid\n"
        "pie showData\n"
        "    title Linguagens usadas (estimativa)\n"
        f'    "PHP" : {php}\n'
        f'    "Vue.js" : {vue}\n'
        f'    "Outras" : {outras}\n'
        "```"
    )

def update_readme(content):
    with open("README.md", "r", encoding="utf-8") as f:
        readme = f.read()
    pattern = re.compile(r"<!--LANG-STATS-START-->.*<!--LANG-STATS-END-->", re.DOTALL)
    updated = pattern.sub(f"<!--LANG-STATS-START-->\n{content}\n<!--LANG-STATS-END-->", readme)
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(updated)

def main():
    total = PHP_PCT + VUE_PCT + OUTRAS_PCT
    if total <= 0:
        php, vue, outras = 40, 40, 20
    else:
        factor = 100.0 / total
        php = round(PHP_PCT * factor, 2)
        vue = round(VUE_PCT * factor, 2)
        outras = round(OUTRAS_PCT * factor, 2)
    block = render_mermaid(php, vue, outras)
    update_readme(block)
    print("README atualizado com gráfico estimado (PHP/Vue/Outras).")

if __name__ == "__main__":
    main()
