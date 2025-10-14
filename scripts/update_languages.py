import os, re, sys, time
import requests
from collections import defaultdict


USERNAME = os.getenv("USERNAME") or "emanuelleLS"
TOP_N = int(os.getenv("TOP_N", "8"))
EXCLUDE_FORKS = os.getenv("EXCLUDE_FORKS", "true").lower() == "true"
INCLUDE_ORG_CONTRIB = os.getenv("INCLUDE_ORG_CONTRIB", "false").lower() == "true"  
MAX_ORG_REPOS = int(os.getenv("MAX_ORG_REPOS", "0"))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  
API = "https://api.github.com"

HEADERS = {"Accept": "application/vnd.github+json"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"
else:
    pass

def get_with_retry(url, params=None, max_retries=3, backoff=1.5):
    last_err = None
    for i in range(max_retries):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=30)
            if r.status_code in (429, 502, 503, 504):
                time.sleep(backoff * (i + 1))
                continue
            r.raise_for_status()
            return r
        except requests.HTTPError as e:
            last_err = e
            time.sleep(backoff * (i + 1))
    if last_err:
        raise last_err
    raise RuntimeError("Falha de rede não tratada")

def paginated(url, params=None, limit=None):
    count = 0
    while True:
        r = get_with_retry(url, params=params)
        try:
            data = r.json()
        except Exception:
            break
        if isinstance(data, list):
            for item in data:
                yield item
                count += 1
                if limit and count >= limit:
                    return
        else:
            break
        if r.links and "next" in r.links:
            url = r.links["next"]["url"]
            params = None
            time.sleep(0.12)
        else:
            break

def list_personal_repos():
    """
    - Com token: /user/repos (owner) → públicos+privados.
    - Sem token: /users/{USERNAME}/repos (type=owner) → só públicos.
    Retorna apenas repos cujo owner == USERNAME (User).
    """
    if GITHUB_TOKEN:
        params = {"visibility": "all", "affiliation": "owner", "per_page": 100, "sort": "updated", "direction": "desc"}
        url = f"{API}/user/repos"
        raw = [r for r in paginated(url, params=params)]
    else:
        params = {"type": "owner", "per_page": 100}
        url = f"{API}/users/{USERNAME}/repos"
        raw = [r for r in paginated(url, params=params)]

    out = []
    for r in raw:
        owner = r.get("owner", {})
        if owner.get("type") == "User" and owner.get("login") == USERNAME:
            out.append(r)
    return out

def list_org_member_repos(limit):
    """Só com token. Sem token, retorna []."""
    if not GITHUB_TOKEN:
        return []
    params = {"visibility": "all", "affiliation": "organization_member", "per_page": 100, "sort": "updated"}
    url = f"{API}/user/repos"
    raw = [r for r in paginated(url, params=params, limit=limit)]
    return [r for r in raw if r.get("owner", {}).get("type") == "Organization"]

def repo_languages(owner, repo):
    r = get_with_retry(f"{API}/repos/{owner}/{repo}/languages")
    if r.status_code == 204:
        return {}
    return r.json() or {}

def contributors_ratio(owner, repo, username, max_waits=6, sleep_s=1.25):
    """
    Fração de commits do usuário no repositório (mine/total) via /stats/contributors.
    Se não estiver pronto (202), aguardamos algumas vezes; senão retornamos 0.0.
    """
    url = f"{API}/repos/{owner}/{repo}/stats/contributors"
    waits = 0
    while waits < max_waits:
        res = requests.get(url, headers=HEADERS, timeout=30)
        if res.status_code == 202:
            time.sleep(sleep_s)
            waits += 1
            continue
        if res.status_code == 204:
            return 0.0
        res.raise_for_status()
        data = res.json()
        if not isinstance(data, list):
            return 0.0
        total = 0
        mine = 0
        for entry in data:
            commits = entry.get("total", 0) or 0
            total += commits
            author = entry.get("author") or {}
            if author.get("login") == username:
                mine += commits
        return (mine / total) if total > 0 else 0.0
    return 0.0

def format_table(lang_pct, totals):
    lines = ["| Linguagem | % | Bytes (ponderado) |", "|---|---:|---:|"]
    for lang, pct in lang_pct:
        lines.append(f"| {lang} | {pct:.1f}% | {int(totals[lang])} |")
    return "\n".join(lines)

def mermaid_pie(lang_pct):
    out = ["```mermaid", "pie showData", "    title Linguagens usadas (ponderado)"]
    for lang, pct in lang_pct:
        out.append(f'    "{lang}" : {pct:.2f}')
    out.append("```")
    return "\n".join(out)

def update_readme(content):
    with open("README.md", "r", encoding="utf-8") as f:
        readme = f.read()
    pattern = re.compile(r"<!--LANG-STATS-START-->.*<!--LANG-STATS-END-->", re.DOTALL)
    updated = pattern.sub(f"<!--LANG-STATS-START-->\n{content}\n<!--LANG-STATS-END-->", readme)
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(updated)

def main():
    totals = defaultdict(float)

    # 1) Pessoais (100%)
    personal = list_personal_repos()
    for r in personal:
        if r.get("archived"):
            continue
        if EXCLUDE_FORKS and r.get("fork"):
            continue
        owner = r["owner"]["login"]
        name = r["name"]
        try:
            langs = repo_languages(owner, name)
        except Exception:
            continue
        for lang, b in langs.items():
            totals[lang] += float(b)
        time.sleep(0.1)

    if INCLUDE_ORG_CONTRIB and GITHUB_TOKEN:
        orgs = list_org_member_repos(limit=MAX_ORG_REPOS)
        for r in orgs:
            if r.get("archived"):
                continue
            if EXCLUDE_FORKS and r.get("fork"):
                continue
            owner = r["owner"]["login"]
            name = r["name"]
            try:
                frac = contributors_ratio(owner, name, USERNAME)
            except Exception:
                frac = 0.0
            if frac <= 0.0:
                continue
            try:
                langs = repo_languages(owner, name)
            except Exception:
                continue
            for lang, b in langs.items():
                totals[lang] += float(b) * float(frac)
            time.sleep(0.15)

    # 3) Saída
    if not totals:
        result = "Nenhum dado de linguagem encontrado (sem token: somente repositórios pessoais públicos; verifique também se há código detectável)."
    else:
        grand = sum(totals.values())
        items = [(lang, (b / grand) * 100.0) for lang, b in totals.items() if b > 0]
        items.sort(key=lambda x: x[1], reverse=True)
        top = items[:TOP_N]
        table = format_table(top, totals)
        chart = mermaid_pie(top)
        result = f"{table}\n\n{chart}"

    update_readme(result)
    print("README atualizado com estatísticas de linguagens (pessoais; orgs desativado).")

if __name__ == "__main__":
    main()
