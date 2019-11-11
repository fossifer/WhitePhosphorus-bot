import datetime
from . import botsite
from bisect import insort_right
from dateutil.relativedelta import relativedelta
from .botsite import get_summary
from .core import EditQueue, check

result_page = 'User:WhitePhosphorus-bot/AbandonedDrafts'
draftlist = [[] for i in range(5)]
week_list = ['一', '二', '三', '四', '五', '六', '日']
R2 = {}


def draft_generator():
    site = botsite.Site()
    for ap in site.api_get_long({'action': 'query', 'apnamespace': '118',
                                 'list': 'allpages', 'aplimit': 'max'}, 'query'):
        if not ap['allpages']:
            raise StopIteration()
        for page in ap['allpages']:
            yield page


def last_ts(idlist):
    site = botsite.Site()
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
        if months < 3:
            continue
        index = min(months - 3, 4)
        insort_right(draftlist[index], ((curtime-dts).total_seconds(), title, dts))


def init():
    global draftlist, R2
    draftlist = [[] for i in range(5)]
    R2 = {}


@check('draft')
def main():
    init()
    site = botsite.Site()
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
    last_ts(tmplist)
    total_num = 0
    content = ('本页记录了全部最后编辑大于等于3个月的草稿页面。'
               '这个列表不包含跨名字空间的重定向，后者列出于[[/DraftsNeedR2]]。\n\n'
               '本页由机器人每天更新，上次更新时间为~~~~~\n\n')
    for i, drafts in enumerate(draftlist):
        title = '== %s%d个月 ==\n' % ('大于等于' * (i == 4), i + 3)
        total_num += len(draftlist[i])
        body = '# ' + '\n# '.join(['[[%s]]，最后编辑于%s' % (t[1],
                                   '{y}年{m}月{d}日 ({w}) {hh:02d}:{mm:02d} (UTC)'.format(
            y=t[2].year, m=t[2].month, d=t[2].day, w=week_list[t[2].weekday()],
            hh=t[2].hour, mm=t[2].minute)) for t in draftlist[i]]) + '\n\n'
        content += (title + body)

    EditQueue().push(text=content, title=result_page, bot=True, task='draft',
                     summary=get_summary('draft', '更新疑似废弃草稿列表，共%d个' % total_num))
    content = ('本页列出了草稿页中的跨名字空间重定向，请管理员根据CSD R2快速删除。\n\n'
               '本页由机器人每天更新，上次更新时间为~~~~~\n\n')
    EditQueue().push(text=content + '# [[' + ']]\n# [['.join(R2.keys()) + ']]',
                     summary=get_summary('draft', '更新需要[[WP:CSD#R2|快速删除]]'
                                                  '的草稿页列表，共%d个' % len(R2.keys())),
                     title=result_page+'/DraftsNeedR2', bot=True, task='draft')


if __name__ == '__main__':
    pass
