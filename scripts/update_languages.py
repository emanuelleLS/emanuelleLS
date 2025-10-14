import os, re, sys, time
import requests
from collections import defaultdict

USERNAME = os.getenv("USERNAME") or "emanuelleLS"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
API = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github+json"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

def list_repos():
    """Lista todos os repositórios do usuário autenticado (pessoais e orgs)"""
    repos = []
    params = {"visibility": "all", "affiliation": "owner,organization_member", "per_page": 100}
    while True:
        r = requests.get(f"{API}/user/repos", headers=HEADERS, params=params)
        r.raise_for_status()
        data = r.json()
        repos.extend(data)
        if 'next' not in r.links:
            break
        params = {}
        url = r.links['next']['url']
    return repos

def get_langs(owner, repo):
    r = requests.get(f"{API}/repos/{owner}/{repo}/languages", headers=HEADERS)
    if r.status_code == 204:
        return {}
    r.raise_for_status()
    return r.json()

def get_commit_ratio(owner, repo, user):
    """Retorna a fração de commits feitos pela usuária em um repo"""
    url = f"{API}/repos/{owner}/{repo}/stats/contributors"
    for _ in range(5):
        res = requests.get(url, headers=HEADERS)
        if res.status_code == 202:  # ainda processando
            time.sleep(1.5)
            continue
        res.raise_for_status()
        data = res.json()
        total = sum(c["total"] for c in data)
        mine = sum(c["total"] for c in data if c["author"] and c["author"]["login"] == user)
        return (mine / total) if total else 0
    return 0

def main():
    repos = list_repos()
    totals = defaultdict(float)

    for repo in repos:
        if repo.get("archived") or repo.get("fork"):
            continue
        owner = repo["owner"]["login"]
        name = repo["name"]
        langs = get_langs(owner, name)
        weight = 1.0
        if repo["owner"]["type"] == "Organization":
            weight = get_commit_ratio(owner, name, USERNAME) or 0
        for lang, bytes_ in langs.items():
            totals[lang] += bytes_ * weight
        time.sleep(0.2)

    if not totals:
        result = "Nenhum dado de linguagem encontrado."
    else:
        total = sum(totals.values())
        items = sorted(((k, v * 100 / total) for k, v in totals.items()), key=lambda x: x[1], reverse=True)
        table = "| Linguagem | % |\n|---|---:|\n" + "\n".join(f"| {k} | {v:.1f}% |" for k, v in items[:8])
        chart = "\n```mermaid\npie showData\n    title Linguagens usadas (ponderado)\n" + \
                "\n".join([f'    "{k}" : {v:.2f}' for k, v in items[:8]]) + "\n```"
        result = f"{table}\n\n{chart}"

    with open("README.md", encoding="utf-8") as f:
        readme = f.read()
    pattern = re.compile(r"<!--LANG-STATS-START-->.*<!--LANG-STATS-END-->", re.DOTALL)
    updated = pattern.sub(f"<!--LANG-STATS-START-->\n{result}\n<!--LANG-STATS-END-->", readme)
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(updated)
    print("README atualizado com estatísticas.")

if __name__ == "__main__":
    main()
