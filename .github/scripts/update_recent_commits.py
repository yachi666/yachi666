import json
import os
import re
import sys
import urllib.request
from datetime import datetime

USERNAME = os.environ['GH_USERNAME']
TOKEN = os.environ.get('GH_TOKEN')
README_PATH = os.environ.get('README_PATH', 'README.md')
MAX_REPOS = int(os.environ.get('MAX_REPOS', '8'))
MAX_ITEMS = int(os.environ.get('MAX_ITEMS', '6'))

START = '<!--START_SECTION:recent-updates-->'
END = '<!--END_SECTION:recent-updates-->'
API = 'https://api.github.com'


def request_json(url: str):
    headers = {
        'Accept': 'application/vnd.github+json',
        'User-Agent': f'{USERNAME}-profile-readme-updater',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    if TOKEN:
        headers['Authorization'] = f'Bearer {TOKEN}'

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        charset = resp.headers.get_content_charset() or 'utf-8'
        return json.loads(resp.read().decode(charset))


def clean_message(message: str) -> str:
    first_line = (message or '').splitlines()[0].strip()
    first_line = re.sub(r'\s+', ' ', first_line)
    return first_line[:88] + ('…' if len(first_line) > 88 else '')


def iso_to_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def fetch_recent_commits():
    repos = request_json(f'{API}/users/{USERNAME}/repos?sort=updated&per_page={MAX_REPOS}&type=owner')
    items = []

    for repo in repos:
        if repo.get('fork') or repo.get('archived'):
            continue

        default_branch = repo.get('default_branch')
        if not default_branch:
            continue

        commits = request_json(
            f"{API}/repos/{USERNAME}/{repo['name']}/commits?sha={default_branch}&per_page=1"
        )
        if not commits:
            continue

        commit = commits[0]
        commit_info = commit.get('commit', {})
        author_info = commit_info.get('author') or {}
        commit_date = author_info.get('date')
        if not commit_date:
            continue

        items.append(
            {
                'repo': repo['name'],
                'repo_url': repo['html_url'],
                'commit_url': commit['html_url'],
                'message': clean_message(commit_info.get('message', 'Update repository')),
                'date': commit_date,
            }
        )

    items.sort(key=lambda item: iso_to_dt(item['date']), reverse=True)
    return items[:MAX_ITEMS]


def format_lines(items):
    if not items:
        return ['- 暂时还没有可展示的最近公开提交。 / No recent public commits found.']

    lines = []
    for item in items:
        date_text = iso_to_dt(item['date']).strftime('%Y-%m-%d')
        lines.append(
            f"- ✨ **{date_text}** · [{item['repo']}]({item['repo_url']}) — [{item['message']}]({item['commit_url']})"
        )
    return lines


def replace_section(content: str, new_lines):
    pattern = re.compile(rf'{re.escape(START)}.*?{re.escape(END)}', re.S)
    replacement = START + '\n' + '\n'.join(new_lines) + '\n' + END
    if not pattern.search(content):
        raise RuntimeError('Recent updates markers not found in README.md')
    return pattern.sub(replacement, content)


def main():
    items = fetch_recent_commits()
    lines = format_lines(items)

    with open(README_PATH, 'r', encoding='utf-8') as f:
        original = f.read()

    updated = replace_section(original, lines)

    if updated != original:
        with open(README_PATH, 'w', encoding='utf-8') as f:
            f.write(updated)
        print('README updated with recent commits.')
    else:
        print('No README changes needed.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Failed to update recent commits: {exc}', file=sys.stderr)
        raise
