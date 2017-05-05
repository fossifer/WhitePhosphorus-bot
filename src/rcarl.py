# Recent changes article requests/list
import botsite
from bs4 import BeautifulSoup

working_title = 'Template:Recent changes article requests/list'


def main(site):
    if not site.check_user():
        site.client_login(__import__('getpass').getpass())
    text = site.get_text_by_title(working_title)
    lines = text.splitlines()
    articles = [line.strip()[1:] for line in lines[1:-2]]
    html = site.parse('[['+']][['.join(articles)+']]')
    soup = BeautifulSoup(html, 'html.parser')
    i = 0
    for a in soup.find_all('a'):
        if '&action=edit&redlink=1' not in a.get('href'):
            articles.pop(i)
        else:
            i += 1
    prefix, suffix = lines[0], lines[-2] + '\n' + lines[-1]
    new_text = prefix + '\n |' + '\n |'.join(articles) + '\n' + suffix
    summary = '机器人：移除%d个已存在条目' % (len(lines) - 3 - i)
    #site.edit(new_text, summary, title=working_title, bot=True, minor=True)
    __import__('os').system('echo "%s" | pbcopy' % summary)


if __name__ == '__main__':
    main(botsite.Site())
