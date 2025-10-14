import os, re, sys, time
import requests
from collections import defaultdict

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
USERNAME = os.getenv("USERNAME") or "emanuelleLS"  # fallback seguro
EXCLUDE_FORKS = os.getenv("EXCLUDE_FORKS", "true").lower() == "true"
TOP_N = int(os.getenv("TOP_N", "8"))

API = "https://api.github.com"
HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

def paginated(url, params=None):
    params = params or {}
    while True:
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            yield from data
        else:
            break
        links = r.headers.get("Link", "")
        next_link = None
        for part in links.split(","):
            if 'rel="next"' in part:
                next_link = part[part.find("<")+1:part.find(">")]
                break
        if not next_link:
            break
        url, params = next_link, {}

def list_repos(user):
    return [repo for repo in paginated(f"{API}/users/{user}/repos", {"type":"owner","per_page":100})]

def repo_languages(owner, repo):
    r = requests.get(f"{API}/repos/{owner}/{repo}/languages", headers=HEADERS, timeout=30)
    if r.status_code == 204:
        return {}
    r.raise_for_status()
    return r.json() or {}

def generate_mermaid_pie(lang_pct):
    lines = ['```mermaid', 'pie showData', '    title Linguagens mais usadas (por bytes de código)']
    for lang, pct in lang_pct:
        lines.append(f'    "{lang}" : {pct:.2f}')
    lines.append('```')
    return "\n".join(lines)

def format_table(lang_pct, totals):
    out = ["| Linguagem | % | Bytes |", "|---|---:|---:|"]
    for lang, pct in lang_pct:
        out.append(f"| {lang} | {pct:.1f}% | {totals[lang]} |")
    return "\n".join(out)

def main():
    repos = list_repos(USERNAME)
    filtered = [r for r in repos if not r.get("archived") and (not EXCLUDE_FORKS or not r.get("fork"))]

    totals = defaultdict(int)
    for r in filtered:
        langs = repo_languages(USERNAME, r["name"])
        for lang, bytes_ in langs.items():
            totals[lang] += int(bytes_)
        time.sleep(0.2)  # polidez

    if not totals:
        content = "Nenhum dado de linguagem encontrado."
        lang_pct_sorted = []
    else:
        grand_total = sum(totals.values())
        pct = [(lang, (bytes_/grand_total)*100.0) for lang, bytes_ in totals.items()]
        pct.sort(key=lambda x: x[1], reverse=True)
        lang_pct_sorted = pct[:TOP_N]
        content = format_table(lang_pct_sorted, totals) + "\n\n" + generate_mermaid_pie(lang_pct_sorted)

    with open("README.md", "r", encoding="utf-8") as f:
        readme = f.read()

    start_tag = r"<!--LANG-STATS-START-->"
    end_tag = r"<!--LANG-STATS-END-->"
    pattern = re.compile(start_tag + r".*?" + end_tag, flags=re.DOTALL)
    replacement = f"<!--LANG-STATS-START-->\n{content}\n<!--LANG-STATS-END-->"

    if not pattern.search(readme):
        print("Marcadores não encontrados no README.md", file=sys.stderr)
        sys.exit(1)

    updated = pattern.sub(replacement, readme)
    if updated != readme:
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(updated)
        print("README.md atualizado.")
    else:
        print("Sem mudanças nos dados.")

if __name__ == "__main__":
    main()
