# TODO: <source lang='foo'> </source>

import re
import sys
import time
import datetime
import collections
import difflib
import botsite
from botsite import remove_nottext, cur_timestamp

nobots_re = re.compile(r'{{\s*[Nn]obots\s*}}|'
                       '{{\s*[Bb]ots\s*\|\s*allow\s*=\s*none\s*}}|'
                       '{{[Bb]ots\s*\|\s*deny\s*=\s*all\s*}}|'
                       '{{\s*[Bb]ots\s*\|\s*optout\s*=\s*all\s*}}')
allow_re = re.compile(r'{{\s*[Bb]ots\s*\|\s*allow\s*=\s*([\s\S]*?)}}')
deny_re = re.compile(r'{{\s*[Bb]ots\s*\|\s*deny\s*=\s*([\s\S]*?)}}')

# update here when a new direct page to {{需要消歧义}} is created
dab_needed = r'(?![ \t]*[\r\n]?{{\s*(需要消歧[义義]|連結消歧義|链接消歧义|' \
             '[Dd]isambiguation needed))'
link_re = re.compile(r'\[\[:?(.*?)(\|.*?)?\]\]')
link_t_re = re.compile(r'\[\[:?((?:{0}.)*?)(\|(?:{0}.)*?)?\]\]{0}'
                       .format(dab_needed))
link_invalid = '<>[]|{}'
# do not forget to use lower()
ns_re = re.compile(r'^category\s*:|^分[类類]\s*:|'
                   '^file\s*:|^image\s*:|^文件\s*:|^[档檔]案\s*:|'
                   '^wikipedia:\s*:|^wp\s*:|^project\s*:|^[維维]基百科\s*:')
section_re = re.compile(r'(^|[^=])==(?P<title>[^=].*?[^=])==([^=]|$)')
sign_re = re.compile(r'--\[\[User:WhitePhosphorus-bot\|白磷的机器人\]\]'
                     '（\[\[User talk:WhitePhosphorus\|给主人留言\]\]）'
                     ' [0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日 \([日一二三四五六]\)'
                     '[0-9]{2}:[0-9]{2} \(UTC\)')
pycomment_re = re.compile(r'[ \t]*#.*?[\r\n]')

last_log, ignoring_templates = '', ''

max_n = 500  # nonbots 50, bots 500

bot_name, bot_name_l = 'WhitePhosphorus-bot', 'whitePhosphorus-bot'


def judge_allowed(page_text):
    """
    if following patterns are found in a user's talk page, the bot is denied:
    {{nobots}},
    {{bots|allow=none}},
    {{bots|allow=<botlist>}} and bot_name not in <botlist>,
    {{bots|deny=all}},
    {{bots|deny=<botlist>}} and bot_name in <botlist>
    {{bots|optout=all}}
    """
    # without <botlist>
    if nobots_re.findall(page_text):
        return False

    # with <botlist>
    allow_list, deny_list = allow_re.findall(page_text), \
                            deny_re.findall(page_text)
    if not (allow_list or deny_list):
        return True
    a, d = ''.join(allow_list), ''.join(deny_list)
    # contradictory patterns are considered allowing
    return (bot_name in a or bot_name_l in a) or \
        (d and not (bot_name in d or bot_name_l in d or 'all' in d))


def contains_any(src, pat):
    for c in pat:
        if c in src:
            return c
    return None


def log(site, text, ts, red=False):
    global last_log
    text = '\n* [~~~~~] ' + text
    if red:
        text = '<span style="color:red">%s</span>' % text
    if last_log == ts[:10]:
        site.edit(text, '机器人：消歧义内链日志记录。',
                  title='User:WhitePhosphorus-bot/log/dablink',
                  bot=True, append=True)
        last_log = ts[:10]
        return None
    # delete out-dated log and add a new section
    cur_text = site.get_text_by_ids(['5571942'])[0]
    strip_start = cur_text.find('== ')
    today = datetime.datetime.strptime(ts[:10], '%Y-%m-%d')
    last = today - datetime.timedelta(days=6)
    strip_end = cur_text.find('== %s ==' % (last.strftime('%Y-%m-%d')))
    log_text = '\n== %s ==' % ts[:10] + text
    if strip_start == -1 or strip_end == -1:
        site.edit(log_text, '机器人：消歧义内链日志记录。',
                  title='User:WhitePhosphorus-bot/log/dablink',
                  bot=True, append=True)
        return None
    site.edit(cur_text[:strip_start] + cur_text[strip_end:] + log_text,
              '机器人：消歧义内链日志记录。',
              title='User:WhitePhosphorus-bot/log/dablink', bot=True)
    last_log = ts[:10]


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
            c = contains_any(tuple[0], link_invalid)
            if c is not None:
                # log: invalid
                log(site, '检查User:%s于[[%s]]做出的版本号%s'
                    '（[[Special:diff/%s|差异]]），时间戳%s的编辑时遇到异常：'
                    '标题“<nowiki>%s</nowiki>”含有非法字符“%s”，请复查。'
                    % (id_que[i][0], id_que[i][3], id_que[i][5],
                       id_que[i][5], id_que[i][2], tuple[0], c), id_que[i][2])
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


def main(site, id_que, revid_que=None, old_revid_que=None):
    # Step 0: exclude disambiguation pages
    id_list = [tuple[4] for tuple in id_que]
    dab_list = is_disambig(site, id_list)
    id_que = [tuple for i, tuple in enumerate(id_que) if not dab_list[i]]
    revid_que = [tuple[5] for tuple in id_que]
    old_revid_que = [tuple[6] for tuple in id_que]

    # Step 1: query wikitexts changed via RecentChange log
    new_list = site.get_text_by_revid(revid_que)
    old_list = site.get_text_by_revid(old_revid_que)

    # Step 2: find diffs and pick out disambig links added
    rst = find_disambig_links(site, id_que, new_list, old_list)

    # Step 3: Log, notice and resume next
    for i, r in enumerate(rst):
        if not r:
            continue
        # {{需要消歧义}}
        while True:
            # try to edit again and again
            text = site.get_text_by_title(id_que[i][3], ts=True)
            # s.group(1) and ...: ignoring uncompleted links '[[]]'
            new_text = link_t_re.sub(lambda s: s.group(0) +
                '{{需要消歧义|date=%s年%d月}}' % (id_que[i][2][:4],
                int(id_que[i][2][5:7])) if s.group(1) and
                '[[%s]]' % s.group(1) in r else s.group(0), text)
            site.edit(new_text, '机器人：{{[[Template:需要消歧义|需要消歧义]]}}',
                      title=id_que[i][3], bot=False,
                      basets=site.ts, startts=site.ts)
            if site.status != 'editconflict':
                break

        # no change means the dablink is already fixed, do not notice
        if site.status == 'nochange' or site.status == 'pagedeleted':
            continue
        elif site.status:
            log(site, "保存[[%s]]失败：%s！需要消歧义的内链有：%s "
                "－'''[https://dispenser.homenet.org/~dispenser/cgi-bin/"
                "dab_solver.py/zh:%s 修复它！]'''" % (id_que[i][3],
                site.status, '、'.join(r), id_que[i][3]), site.ts, red=True)

        # judge whether to notice user or not
        if not id_que[i][0]:
            continue
        user_talk = 'User talk:%s' % id_que[i][0]
        [talk_text, is_flow] = site.get_text_by_title(user_talk,
                                                      detect_flow=True,
                                                      ts=True)
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
            log(site, '检查User:%s（不通知）于%s的编辑时发现%s' % (
                id_que[i][0], id_que[i][2], item[2:]), id_que[i][2])
            continue

        # notice
        if is_flow:
            if (user_talk+title) in site.flow_ids:
                id = site.flow_ids[user_talk+title]
                site.flow_reply('Topic:'+id, id, '补充：\n'+item)
            else:
                site.flow_new_topic(user_talk, title, notice % item)
        else:
            # TODO: the variable s seems not needed
            lines = talk_text.splitlines(True)
            s, sec = 0, 0
            for li, line in enumerate(lines):
                m = section_re.match(line)
                if m is not None:
                    s += 1
                    if m.group('title').strip() == title:
                        sectitle, sec = m.group('title'), s
                if notice.splitlines()[-1] in line and sec:
                    lines[li] = sign_re.sub('--~~~~', line)
                    lines.insert(li, item+'\n\n')
                    site.edit(''.join(lines),
                              '/* %s */ %s' % (sectitle, summary),
                              title=user_talk,
                              basets=site.ts, startts=site.ts)
                    break
            else:
                site.edit(notice % item+' --~~~~', summary,
                          title=user_talk, append=True, section='new',
                          sectiontitle=title, nocreate=False)

        # log
        log(site, '检查User:%s（%s通知）于%s的编辑时发现%s' % (id_que[i][0],
            '未' if site.status else '已', id_que[i][2], item[2:]),
            id_que[i][2], red=site.status)


if __name__ == '__main__':
    pass
