import sys
import datetime
import botsite
from bisect import insort_right
from dateutil.relativedelta import relativedelta

site = botsite.Site()
result_page = 'User:WhitePhosphorus-bot/AbandonedDrafts'
draftlist = [[] for i in range(25)]
week_list = ['一', '二', '三', '四', '五', '六', '日']
R2 = {}


def draft_generator():
    for ap in site.api_get_long({'action': 'query', 'apnamespace': '118',
                                 'list': 'allpages', 'aplimit': 'max'}, 'query'):
        if not ap['allpages']:
            raise StopIteration()
        for page in ap['allpages']:
            yield page


def last_ts(idlist):
    curtime = datetime.datetime.utcnow()
    r = site.api_get({'action': 'query', 'prop': 'revisions',
                      'rvprop': 'timestamp', 'pageids': '|'.join(idlist)}, 'query')
    t = site.api_get({'action': 'query', 'prop': 'revisions', 'redirects': '1',
                      'pageids': '|'.join(idlist)}, 'query')
    for rd in t.get('redirects', {}):
        if not rd.get('to', 'Draft:').startswith('Draft:'):
            R2[rd.get('from', '')] = 1
    for id, page in r.get('pages', {}).items():
        title = page.get('title', '')
        if R2.get(title):
            continue
        ts = page.get('revisions', [{}])[0].get('timestamp')
        dts = datetime.datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ')
        delta = relativedelta(curtime, dts)
        months = delta.months + delta.years*12
        if months < 6:
            continue
        index = min(months - 6, 24)
        insort_right(draftlist[index], ((curtime-dts).total_seconds(), title, dts))


def main(pwd):
    site.client_login(pwd)
    n, tmplist = 0, []
    for draft in draft_generator():
        id = draft.get('pageid', 0)
        if not id:
            continue
        tmplist.append(str(id))
        n += 1
        if n % 500 == 0:
            last_ts(tmplist)
            tmplist = []
            print(n)
    last_ts(tmplist)
    print(n)
    total_num = 0
    content = '本页记录了全部最后编辑大于等于6个月的草稿页面。这个列表不包含跨名字空间的重定向，后者列出于[[/DraftsNeedR2]]。\n\n'
    for i, drafts in enumerate(draftlist):
        title = '== %s%d个月 ==\n' % ('大于等于' * (i == 24), i + 6)
        total_num += len(draftlist[i])
        body = '# ' + '\n# '.join(['[[%s]]，最后编辑于%s' % (t[1],
            '{y}年{m}月{d}日 ({w}) {hh:02d}:{mm:02d} (UTC)'.format(
            y=t[2].year, m=t[2].month, d=t[2].day, w=week_list[t[2].weekday()],
            hh=t[2].hour, mm=t[2].minute)) for t in draftlist[i]]) + '\n\n'
        content += (title + body)
    site.edit(content, '机器人：更新疑似废弃草稿列表，共%d个' % total_num, title=result_page, bot=True, nocreate=False)
    content = '本页列出了草稿页中的跨名字空间重定向，请管理员根据CSD R2快速删除。\n\n'
    site.edit(content + '# [[' + ']]\n# [['.join(R2.keys()) + ']]', '机器人：更新需要[[WP:CSD#R2|快速删除]]的草稿页列表，共%d个' % len(R2.keys()), title=result_page+'/DraftsNeedR2', bot=True, nocreate=False)


if __name__ == '__main__':
    main(sys.argv[1])
