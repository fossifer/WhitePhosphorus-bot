import re
import sys
import datetime
import requests
from collections import defaultdict
from . import botsite
from .botsite import remove_nottext
from .core import EditQueue, Timestamp, now

arc_list_title = 'User talk:WhitePhosphorus/archives'
working_title = 'User talk:WhitePhosphorus'
working_id = '3951371'
days_delay = 30
section_re = re.compile(r'(^|[^=])==(?P<title>[^=].*?[^=])==([^=]|$)')


def split_sections(text):
    ret, tmp = [], 0
    for i, match in enumerate(section_re.finditer(text)):
        if i:
            ret.append(text[tmp:match.start()].strip().strip('\n'))
        tmp = match.start()
    ret.append(text[tmp:].strip().strip('\n'))
    return ret


def get_oldtext(pageid, ts):
    site = botsite.Site()
    r = site.api_get_long({'action': 'query', 'prop': 'revisions',
                          'rvprop': 'content', 'rvstart': str(ts),
                          'pageids': pageid, 'rvlimit': '1'}, 'query')
        
    for chunk in r:
        return chunk.get('pages', {}).get(pageid, {}).get('revisions', [{}]) \
                                  [0].get('*', '')


class thread:
    def __init__(self, wikitext):
        self.wikitext = wikitext
    
    def __str__(self):
        return self.wikitext
    
    def __eq__(self, other):
        return self.wikitext.strip() == other.wikitext.strip()


class talkpage:
    def __init__(self, pageid=working_id):
        site = botsite.Site()
        self.pageid = pageid
        self.text = site.get_text_by_id(pageid)
        oldts = now() - datetime.timedelta(days=days_delay)
        self.oldtext = get_oldtext(pageid, oldts)
        self.header = ''
        self.threads = []
        self.old_threads = []
        self.analyse()

    def analyse(self):
        tmp = 0
        for i, match in enumerate(section_re.finditer(self.text)):
            if i:
                self.threads.append(thread(self.text[tmp:match.start()]))
            else:
                self.header = self.text[:match.start()]
            tmp = match.start()
        self.threads.append(thread(self.text[tmp:]))
        tmp = 0
        for i, match in enumerate(section_re.finditer(self.oldtext)):
            if i:
                self.old_threads.append(thread(self.oldtext[tmp:match.start()]))
            tmp = match.start()


class archiver:
    def __init__(self, arc='', header='{{Talkarchive}}',
                 arc_to=lambda thread: '', nxt_arc=lambda arc: arc,
                 use_nxt=lambda arc, to_arc: False):
        self.talkpage = talkpage()
        self.header = header
        self.cur_arc = arc
        self.arc_to = arc_to
        self.nxt_arc = nxt_arc
        self.use_nxt = use_nxt

    def archive(self):
        site = botsite.Site()
        self.talkpage = talkpage()
        t = self.talkpage
        text = t.text
        to_arc = defaultdict(list)
        for thread in t.threads:
            if any([thread == o for o in t.old_threads]):
                text = text.replace(thread.wikitext, '')
                to_arc[self.arc_to(thread) or self.cur_arc].append(thread)
        arc_count = sum([len(lst) for lst in to_arc.values()])
        if not arc_count:
            return
        if self.use_nxt(self.cur_arc, to_arc[self.cur_arc]):
            nxt_arc = self.nxt_arc(self.cur_arc)
            to_arc[nxt_arc] = to_arc[self.cur_arc]
            del to_arc[self.cur_arc]
            self.cur_arc = nxt_arc
            arcs = site.get_text_by_title(arc_list_title)
            arcs = arcs.strip()
            old_ts = now() - datetime.timedelta(days=days_delay)
            old_ts = old_ts.strftime('%Y年%m月%d日')
            arcs += old_ts
            arcs += '\n* [[{title}|{abbr}]]：{date}－'.format(
                title=nxt_arc, abbr=nxt_arc[nxt_arc.rfind('/')+1:], date=old_ts)
            EditQueue().push(title=arc_list_title, text=arcs,
                             summary='机器人：+[[%s]]' % nxt_arc,
                             minor=True, bot=True)

        EditQueue().push(pageid=t.pageid, text=text,
                         summary='机器人：存档%d个讨论' % arc_count,
                         minor=True, bot=True)
        for arc_to, t_list in to_arc.items():
            arc_text = site.get_text_by_title(arc_to)
            if not arc_text:
                arc_text = self.header
            arc_text = arc_text.strip() + '\n\n'
            arc_text += ''.join([thread.wikitext for thread in t_list]).strip()
            EditQueue().push(title=arc_to, text=arc_text,
                             summary='机器人：存档%d个讨论' % len(t_list),
                             minor=True, bot=True)


def nxt_arc(arc):
    prefix = 'User talk:WhitePhosphorus/存档'
    count = int(arc[len(prefix):])
    return prefix + str(count+1)


def use_nxt(arc, to_arc):
    site = botsite.Site()
    rst = site.api_get({'action': 'query', 'prop': 'info', 'titles': arc},
                       'query')
    length = list(rst.get('pages', {}).values())[0].get('length', 0)
    new_len = sum([len(thread.wikitext.encode()) for thread in to_arc])
    return length + new_len >= 131702
    

def main(pwd):
    #site = botsite.Site()
    pass
    #site.client_login(pwd)
    """
    for id in site.what_embeds_it(title=config_template,
                                  ns='1|3|5|7|9|11|13|15|101|119|829'):
        #id = '3951371'
        arc = archiver()
        text = site.get_text_by_id(id)
        arc.load_talkpage(id).load_config()
        if arc.config is None:
            continue
        arc.judge()
    """


def default_config():
    return archiver(arc='User talk:WhitePhosphorus/存档2',
                    header='{{存档页}}\n{{User talk:WhitePhosphorus/header}}',
                    nxt_arc=nxt_arc, use_nxt=use_nxt)


if __name__ == '__main__':
    #print(get_oldtext(botsite.Site(), '5457145', '2015-02-26T10:18:43Z')[:80])
    #main(sys.argv[1])
    arc = archiver(arc='User talk:WhitePhosphorus/存档2',
                   header='{{存档页}}\n{{User talk:WhitePhosphorus/header}}',
                   nxt_arc=nxt_arc, use_nxt=use_nxt)
    arc.archive()
