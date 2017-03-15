# TODO: <source lang='foo'> </source>

import re
import sys
import time
import queue
import datetime
import collections
import difflib
import botsite
from botsite import remove_nottext, cur_timestamp

botname_re = r'[Ww]hitePhosphorus-bot'
# FIXME: {{Nobots|allow=all}}  (Though I think nobody will do so)
nobots_re = re.compile(r'{{\s*[Nn]obots\s*}}|'
                       r'{{\s*[Bb]ots\s*\|\s*allow\s*=\s*(none|((?!%s).)*?)\s*}}|'
                       r'{{\s*[Bb]ots\s*\|\s*deny\s*=\s*(all|.*?%s.*?)\s*}}|'
                       r'{{\s*[Bb]ots\s*\|\s*optout\s*=\s*all\s*}}'  % ((
                       botname_re,)*2), re.DOTALL)

# update here when a new direct page to {{需要消歧义}} is created
dab_needed = r'(?:需要消歧[义義]|連結消歧義|链接消歧义|[Dd]isambiguation needed)'
link_re = re.compile(r'\[\[:?(.*?)(\|.*?)?\]\]')
link_t_re = re.compile(r'(\[\[:?((?:(?!\]\]).)*?)(?:\|(?:(?!\]\]).)*?)?\]\])'
                       r'(?:[ \t]*[\r\n]?{{\s*%s.*?}})?' % dab_needed)
link_invalid = '<>[]|{}'  # do not forget to use lower()
ns_re = re.compile(r'^category\s*:|^分[类類]\s*:|'
                   r'^file\s*:|^image\s*:|^文件\s*:|^[档檔]案\s*:|'
                   r'^wikipedia\s*:|^wp\s*:|^project\s*:|^[維维]基百科\s*:')
section_re = re.compile(r'(^|[^=])==(?P<title>[^=].*?[^=])==([^=]|$)')
sign_re = re.compile(r'--\[\[User:WhitePhosphorus-bot\|白磷的机器人\]\]' \
                     r'（\[\[User talk:WhitePhosphorus\|给主人留言\]\]）' \
                     r' \d{4}年\d{1,2}月\d{1,2}日 \([日一二三四五六]\)' \
                     r' \d{2}:\d{2} \(UTC\)')
pycomment_re = re.compile(r'[ \t]*#.*?[\r\n]')

last_log, ignoring_templates = '', ''

max_n = 200
delay = 600
debug = False


def judge_allowed(text):
    """
    if following patterns are found in a user's talk page, the bot is denied:
    {{nobots}},
    {{bots|allow=none}},
    {{bots|allow=<botlist>}} and bot_name not in <botlist>,
    {{bots|deny=all}},
    {{bots|deny=<botlist>}} and bot_name in <botlist>
    {{bots|optout=all}}
    """
    return nobots_re.search(text) is None


def contains_any(src, pat):
    for c in pat:
        if c in src:
            return c
    return None


def remove_templates(site, text):
    return re.sub(r'{{[\s\r\n]*(%s)\|[\s\S]*?}}' % ignoring_templates,
                  '', text)


def find_disambig_links(site, id_que, new_list, old_list):
    ret = [[] for i in range(len(new_list))]
    link_buffer, link_owner, count = [], [], 0
    for i in range(len(new_list)):
        old_list[i] = old_list[i]
        new_list[i] = new_list[i]

        # Step 1: find diff between new and old
        diff = difflib.unified_diff(old_list[i].splitlines(),
                                    new_list[i].splitlines(), lineterm='')
        removed_lines, added_lines = [], []
        for line in list(diff)[2:]:  # first 2 lines are '---' and '+++'
            if line[0] == '-':
                removed_lines.append(line[1:])
            elif line[0] == '+':
                added_lines.append(line[1:])

        # Step 2: find links added
        link_dict = {}
        for tuple in link_re.findall(remove_templates(site,
                remove_nottext('\n'.join(added_lines)))):
            if contains_any(tuple[0], link_invalid):
                continue
            if tuple[0]:
                link_dict[tuple[0]] = link_dict.get(tuple[0], 0) + 1
        for tuple in link_re.findall(remove_templates(site,
                remove_nottext('\n'.join(removed_lines)))):
            if tuple[0]:
                link_dict[tuple[0]] = link_dict.get(tuple[0], 0) - 1

        # Step 3: pick out disambig links
        dab_list = []
        for key, value in link_dict.items():
            # ignore categories, images, etc.
            if value > 0 and ns_re.search(key.lower()) is None:
                link_buffer.append(key)
                link_owner.append(i)
                if len(link_owner) == max_n:
                    rst = site.is_disambig(link_buffer)
                    for di, r in enumerate(rst):
                        if r:
                            ret[link_owner[di]].append('[[%s]]'
                                                       % link_buffer[di])
                    link_buffer, link_owner = [], []
    if link_buffer:
        rst = site.is_disambig(link_buffer)
        for di, r in enumerate(rst):
            if r:
                ret[link_owner[di]].append('[[%s]]' % link_buffer[di])

    return ret


def update_ignore_templates(site):
    return '|'.join(list(map(lambda s: s.strip(),
        [s for s in pycomment_re.sub('', site.get_text_by_title(
            'User:WhitePhosphorus-bot/misc/dablink/IgnoringTemplates'))
            .splitlines() if s])))


def is_disambig(site, ids):
    ret = [False] * len(ids)
    id_str = '|'.join(ids)
    id_dict = collections.defaultdict(list)
    for i, id in enumerate(ids):
        id_dict[id].append(i)
    try:
        r = site.api_post({'action': 'query', 'prop': 'pageprops',
                           'ppprop': 'disambiguation',
                           'pageids': id_str}).get('query')
    except requests.exceptions.ConnectionError as error:
        print(error)
        print('dablink.is_disambig: try again...')
        return is_disambig(site, ids)
    for k, v in r.get('pages', {}).items():
        tmp = 'disambiguation' in v.get('pageprops', [])
        for index in id_dict[k]:
            ret[index] = tmp
    return ret


def ts_delta(ts, ots):
    dt = datetime.datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ')
    odt = datetime.datetime.strptime(ots, '%Y-%m-%dT%H:%M:%SZ')
    return (dt-odt).seconds


def ndab(site, dab_que):
    while True:
        if not dab_que.queue:
            time.sleep(60)
            continue
        title = dab_que.queue[0]
        if debug: print('ndab', dab_que.queue)
        if site.template_in_page('In use', title=title):
            dab_que.get()  # Just forget it!
            continue
        text = site.get_text_by_title(title, ts=True)
        ts = site.get_ts()
        if not ts:
            dab_que.get()
            continue
        ct = cur_timestamp()
        delta = ts_delta(ct, ts)
        if delta < delay:
            time.sleep(delay - delta + 5)
            continue

        dab_que.get()
        if debug: print('ndab:', title)
        y, m = ct[:4], int(ct[5:7])
        all_links = list(set([t[0] for t in link_re.findall(
            remove_templates(site, remove_nottext(text))) \
                         if t[0] and not ns_re.search(t[0].lower())]))
        rst = []
        i = 0
        while i < len(all_links):
            if i+max_n <= len(all_links):
                rst.extend(site.is_disambig(all_links[i:i+max_n]))
                i += max_n
            else:
                rst.extend(site.is_disambig(all_links[i:]))
                break
        dab_links = [link for i, link in enumerate(all_links) if rst[i]]
        new_text = link_t_re.sub(lambda s: s.group(1) +
                         r'{{需要消歧义|date=%s年%d月}}' % (y, m) if s.group(2) and
                         s.group(2) in dab_links else s.group(1), text)
        if debug:
            print('ndab::', new_text.count('{{需要消歧义'), len(dab_links), len(all_links))
            continue
        site.edit(new_text, '机器人：{{[[Template:需要消歧义|需要消歧义]]}}',
                  title=title, bot=False,
                  basets=ts, startts=ts)


def get_ns(site, ids, ignore_redirect=True):
    id_str = '|'.join(ids)
    id_dict = collections.defaultdict(list)
    for i, id in enumerate(ids):
        id_dict[id].append(i)

    ret = [-1] * len(ids)
    rst = site.api_post({'action': 'query', 'prop': 'info',
                         'pageids': id_str}).get('query')
    for k, v in rst.get('pages', {}).items():
        ns = v.get('ns', -1) if 'redirect' not in v else -1
        for index in id_dict[str(k)]:
            ret[index] = ns
    return ret


def main(site, id_que):
    # Step 0: exclude disambiguation pages
    id_list = [tuple[4] for tuple in id_que]
    dab_list = is_disambig(site, id_list)
    ns_list = get_ns(site, id_list)
    id_que = [tuple for i, tuple in enumerate(id_que) if not dab_list[i] and not ns_list[i]]
    revid_que = [tuple[5] for tuple in id_que]
    old_revid_que = [tuple[6] for tuple in id_que]

    # Step 1: query wikitexts changed via RecentChange log
    new_list = site.get_text_by_revid(revid_que)
    old_list = site.get_text_by_revid(old_revid_que)

    # Step 2: find diffs and pick out disambig links added
    rst = find_disambig_links(site, id_que, new_list, old_list)
    ret = set()

    # Step 3: notice and resume next
    for i, r in enumerate(rst):
        if not r:
            continue
        ret.add(id_que[i][3])
        if debug: continue

        # judge whether to notice user or not
        if not id_que[i][0]:
            continue
        user_talk = 'User talk:%s' % id_que[i][0]
        [talk_text, is_flow] = site.get_text_by_title(user_talk,
                detect_flow=True, ts=True)
        talk_ts = site.get_ts()
        will_notify = site.editcount(id_que[i][0]) >= 100 \
                and judge_allowed(talk_text) \
                and not site.has_dup_rev(id_que[i][4], id_que[i][5])

        [notice, item, title, summary] = site.get_text_by_ids([
            '5574512', '5574516', '5575182', '5575256'])
        year, month, day = id_que[i][2][:4], \
            int(id_que[i][2][5:7]), int(id_que[i][2][8:10])
        title = title % (year, month, day)
        item = item % (id_que[i][3], '、'.join(r), id_que[i][5],
                       id_que[i][3].replace(' ', '_'))

        if not will_notify:
            continue

        # notice
        if is_flow:
            fids = site.get_flow_ids()
            if (user_talk+title) in fids:
                id = fids[user_talk+title]
                site.flow_reply('Topic:'+id, id, '补充：\n'+item)
            else:
                site.flow_new_topic(user_talk, title, notice % item)
        else:
            lines = talk_text.splitlines(True)
            sectitle = None
            for li, line in enumerate(lines):
                m = section_re.match(line)
                if m and m.group('title').strip() == title:
                    sectitle = m.group('title')
                if notice.splitlines()[-1] in line and sectitle:
                    lines[li] = sign_re.sub('--~~~~', line)
                    lines.insert(li, item+'\n\n')
                    site.edit(''.join(lines),
                              '/* %s */ %s' % (sectitle, summary),
                              title=user_talk,
                              basets=talk_ts, startts=talk_ts)
                    break
            else:
                site.edit(notice % item+' --~~~~', summary,
                          title=user_talk, append=True, section='new',
                          sectiontitle=title, nocreate=False)

    # Finally: return titles including dablinks
    if debug: print('id_que', ret)
    return ret


if __name__ == '__main__':
    pass
