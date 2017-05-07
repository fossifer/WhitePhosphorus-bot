import datetime
import botsite
from bs4 import BeautifulSoup

working_title = 'Template:Recent changes article requests/list'
delay_days = 7


def check_create_time(site, articles, exists):
    ret = [False] * len(articles)
    cts = datetime.datetime.utcnow()
    for i, title in enumerate(articles):
        if not exists[i]:
            continue
        r = site.api_get({'action': 'query', 'prop': 'revisions',
                          'rvdir': 'newer', 'rvlimit': 1, 'rvprop': 'timestamp',
                          'titles': title}, 'query')
        page = r.get('pages')
        create_ts = None
        for k, v in page.items():
            rev = v.get('revisions')
            if type(rev) is list and rev:
                create_ts = rev[0].get('timestamp')
        if create_ts is None:
            print('%s: Failed to parse created time of [[%s]]' % (cts, title))
            continue
        print(title, create_ts)
        create_ts = datetime.datetime.strptime(create_ts, '%Y-%m-%dT%H:%M:%SZ')
        if (cts - create_ts).days >= delay_days:
            ret[i] = True
    return ret


def main(site):
    if not site.check_user():
        site.client_login(__import__('getpass').getpass())
    text = site.get_text_by_title(working_title)
    lines = text.splitlines()
    articles = [line.strip()[1:] for line in lines[1:-2]]
    exists = [False] * len(articles)
    html = site.parse('[['+']][['.join(articles)+']]')
    soup = BeautifulSoup(html, 'html.parser')
    i = 0
    for a in soup.find_all('a'):
        if '&action=edit&redlink=1' not in a.get('href'):
            exists[i] = True
        i += 1
    to_remove = check_create_time(site, articles, exists)
    if not any(to_remove):
        return None
    n_articles = [a for i, a in enumerate(articles) if not to_remove[i]]
    prefix, suffix = lines[0], lines[-2] + '\n' + lines[-1]
    new_text = prefix + '\n |' + '\n |'.join(n_articles) + '\n' + suffix
    summary = '假装自己是机器人：移除%d个已存在条目' % (len(articles)-len(n_articles))
    site.edit(new_text, summary, title=working_title, bot=True, minor=True)


if __name__ == '__main__':
    main(botsite.Site())
