# TODO: cache the status of titles
import datetime
from bs4 import BeautifulSoup
from . import botsite
from .core import EditQueue, check, log
from .botsite import remove_nottext, get_summary

working_title = 'Template:Recent changes article requests/list'
delay_days = 7
whitelist_title = 'User:%s/controls/rcarl/whitelist' % botsite.bot_name
whitelist = []


def load_whitelist():
    global whitelist
    site = botsite.Site()
    text = site.get_text_by_title(whitelist_title)
    # The first line and the last line are respectively <pre> and </pre>, ignoring
    for line in text.splitlines()[1:-1]:
        try:
            index = line.index('#')
            line = line[:index]
        except ValueError:
            pass
        line = line.strip()
        if not line:
            continue
        whitelist.append(line)


def check_create_time(site, articles, exists):
    ret = [False] * len(articles)
    cts = datetime.datetime.utcnow()
    for i, title in enumerate(articles):
        if not exists[i] or title in whitelist:
            continue
        r = site.api_get({'action': 'query', 'prop': 'revisions',
                          'rvdir': 'newer', 'rvlimit': 1, 'rvprop': 'timestamp',
                          'titles': title, 'converttitles': 1}, 'query')
        page = r.get('pages')
        create_ts = None
        for k, v in page.items():
            rev = v.get('revisions')
            if type(rev) is list and rev:
                create_ts = rev[0].get('timestamp')
        if create_ts is None:
            log('%s: Failed to parse created time of [[%s]]' % (cts, title))
            log(r)
            continue
        create_ts = datetime.datetime.strptime(create_ts, '%Y-%m-%dT%H:%M:%SZ')
        if (cts - create_ts).days >= delay_days:
            ret[i] = True
    return ret


def gen_rev(site, text):
    lines = text.splitlines()
    articles = [remove_nottext(line.strip()[1:]) for line in lines[1:-2]]
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
    n_articles = [lines[i+1] for i in range(len(articles)) if not to_remove[i]]
    prefix, suffix = lines[0], lines[-2] + '\n' + lines[-1]
    new_text = prefix + '\n' + '\n'.join(n_articles) + '\n' + suffix
    summary = get_summary('rcarl', '移除%d个已存在条目' % (len(articles)-len(n_articles)))
    return {'text': new_text, 'summary': summary}


@check('rcarl')
def main():
    load_whitelist()
    EditQueue().push(title=working_title, text=gen_rev,
                     bot=1, minor=1, task='rcarl')


if __name__ == '__main__':
    site = botsite.Site()
    print(gen_rev(site, site.get_text_by_title(working_title))['text'])
