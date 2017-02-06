import time
import re
import sys
import requests
import json
import difflib
import botsite
import exception

nobots_re = re.compile(r'{{[\s\r\n]*[Nn]obots[\s\r\n]*}}|{{[\s\r\n]*[Bb]ots[\s\r\n]*\|[\s\r\n]*allow[\s\r\n]*=[\s\r\n]*none[\s\r\n]*}}|{{[Bb]ots[\s\r\n]*\|[\s\r\n]*deny[\s\r\n]*=[\s\r\n]*all[\s\r\n]*}}|{{[\s\r\n]*[Bb]ots[\s\r\n]*\|[\s\r\n]*optout[\s\r\n]*=[\s\r\n]*all[\s\r\n]*}}')
allow_re = re.compile(r'{{[\s\r\n]*[Bb]ots[\s\r\n]*\|[\s\r\n]*allow[\s\r\n]*=[\s\r\n]*([\s\S]*?)}}')
deny_re = re.compile(r'{{[\s\r\n]*[Bb]ots[\s\r\n]*\|[\s\r\n]*deny[\s\r\n]*=[\s\r\n]*([\s\S]*?)}}')

#link_re = re.compile(r'\[\[:?(.*?)(\||\]\])')
dab_needed = r'(?!\s*[\r\n]?{{[\s\r\n]*需要消歧[义義])'
link_re = re.compile(r'\[\[:?(.*?)(\|.*?)?\]\]')
link_t_re = re.compile(r'\[\[:?((?:{0}.)*?)(\|(?:{0}.)*?)?\]\]{0}'.format(dab_needed))
link_invalid = '<>[]|{}'
ns_re = re.compile(r'^category\s*:|^file\s*:|^image\s*:') # do not forget to use lower()
section_re = re.compile(r'(^|[^=])==(?P<title>[^=].*?[^=])==([^=]|$)')
comment_re = re.compile(r'<!--[\s\S]*?-->')
nowiki_re = re.compile(r'<nowiki>[\s\S]*?</nowiki>')
sign_re = re.compile(r'--\[\[User:WhitePhosphorus-bot\|白磷的机器人\]\]（\[\[User talk:WhitePhosphorus\|给主人留言\]\]） [0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日 \([日一二三四五六]\) [0-9]{2}:[0-9]{2} \(UTC\)')

rollback_re = re.compile(r'回退\[\[Special:Contributions/(.*?)\|\1\]\]\s*\(\[\[User talk:\1\|讨论\]\]\)做出的\s*\d+\s*次编辑|\[\[WP:UNDO\|撤销\]\]|回退到由\[\[Special:Contributions/(.*?)\|\2]]\s*\(\[\[User talk:\2\|讨论\]\]\)做出的修订版本|回退.*?做出的出于\[\[WP:AGF\|善意\]\]的编辑|取消\[\[Special:Contributions/(.*?)|\3\]\]（\[\[User talk:\3|对话\]\]）的编辑')

last_log = '2017-02-06'

max_n = 500 # nonbots 50, bots 500

bot_name, bot_name_l = 'WhitePhosphorus-bot', 'whitePhosphorus-bot'

def judge_allowed(page_text):
    '''
        if following patterns are found in a user talk page, the bot is denied:
        {{nobots}},
        {{bots|allow=none}},
        {{bots|allow=<botlist>}} and bot_name not in <botlist>,
        {{bots|deny=all}},
        {{bots|deny=<botlist>}} and bot_name in <botlist>
    '''
    # without <botlist>
    if nobots_re.findall(page_text):
        return False
    
    # with <botlist>
    allow_list, deny_list = allow_re.findall(page_text), deny_re.findall(page_text)
    if not (allow_list or deny_list):
        return True
    a, d = ''.join(allow_list), ''.join(deny_list)
    # contradictory patterns considered allowing
    return (bot_name in a or bot_name_l in a) or (d and not (bot_name in d or bot_name_l in d or 'all' in d))

def contains_any(src, pat):
    for c in pat:
        if c in src:
            return c
    return None

def remove_nottext(text):
    return nowiki_re.sub('', comment_re.sub('', text))

def log(site, text, ts, red=False):
    global last_log
    text = '\n* [~~~~~] ' + text
    if red:
        text = '<span style="color:red">%s</span>' % text
    log_text = ('' if last_log == ts[:10] else '\n== %s ==' % ts[:10]) + text
    site.edit(log_text, '机器人：消歧义内链日志记录。', title='User:WhitePhosphorus-bot/log/dablink', bot=True, append=True)
    last_log = ts[:10]

def find_disambig_links(site, id_que, new_list, old_list):
    l = len(new_list)
    assert(l <= max_n)
    ret = [[] for i in range(l)]
    link_buffer, link_owner, count, link_index = [''] * 75, [''] * 75, 0, {}
    for i in range(l):
        # Step 1: find diff between new and old
        diff = difflib.unified_diff(old_list[i].splitlines(), new_list[i].splitlines(), lineterm='')
        removed_lines, added_lines = [], []
        for line in list(diff)[2:]: # first 2 lines are '---' and '+++'
            if line[0] == '-':
                removed_lines.append(line)
            elif line[0] == '+':
                added_lines.append(line)

        # Step 2: find links added
        link_dict = {}
        for tuple in link_re.findall(remove_nottext('\n'.join(added_lines))):
            c = contains_any(tuple[0], link_invalid)
            if c is not None:
                # log: invalid
                log(site, '检查User:%s于[[%s]]做出的版本号%s（[[Special:diff/%s|差异]]），时间戳%s的编辑时遇到异常：标题“<nowiki>%s</nowiki>”含有非法字符“%s”，请复查。' % (id_que[i][0], id_que[i][3], id_que[i][5], id_que[i][5], id_que[i][2], tuple[0], c), id_que[i][2])
                continue
            link_dict[tuple[0]] = link_dict.get(tuple[0], 0) + 1
        for tuple in link_re.findall(remove_nottext('\n'.join(removed_lines))):
            link_dict[tuple[0]] = link_dict.get(tuple[0], 0) - 1

        # Step 3: pick out disambig links
        dab_list = []
        for key, value in link_dict.items():
            # ignore categories
            if value > 0 and ns_re.search(key.lower()) is None:
                link_buffer[count], link_owner[count] = key, i
                if link_index.get(key, -1) == -1:
                    link_index.update({key: [count]})
                else:
                    link_index[key].append(count)
                count += 1
                # full
                if count == 75:
                    rst = site.is_disambig(link_buffer, link_index)
                    for dab_index in range(len(rst)):
                        if rst[dab_index]:
                            ret[link_owner[dab_index]].append('[[%s]]' % link_buffer[dab_index])
                    link_buffer, link_owner, count, link_index = [''] * 75, [''] * 75, 0, {}
    if count > 0:
        rst = site.is_disambig(link_buffer, link_index)
        for dab_index in range(len(rst)):
            if rst[dab_index]:
                ret[link_owner[dab_index]].append('[[%s]]' % link_buffer[dab_index])

    return ret

def is_rollback(comment):
    return rollback_re.match(comment) is not None

def main(pwd):
    global last_log
    site = botsite.Site()
    site.client_login(pwd)
    id_que, revid_que, old_revid_que, notice_que = [], [], [], []
    id_count = 0
    log = site.get_text_by_ids(['5571942'])[0].splitlines()[-1]
    last_ts = re.findall(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', log)[0]
    last_log = last_ts[:10]
    last_id = re.findall(r'Special:diff/(\d+)', log)[0]
    print(last_ts, last_log, last_id)
    while True:
        # Step 1: get the wikitexts edited via RecentChange log
        for change in site.rc_generator(last_ts):
            if is_rollback(change['comment']) or change['user'] == bot_name:
                continue
            user, userid, timestamp, title, pageid, revid, old_revid = change['user'], change['userid'], change['timestamp'], change['title'], str(change['pageid']), change['revid'], str(change['old_revid'])
            if revid <= last_id:
                continue
            revid = str(revid)
            id_que.append((user, userid, timestamp, title, pageid, revid, old_revid))
            revid_que.append(revid)
            old_revid_que.append(old_revid)
            #print("'%s', %s" % (timestamp, revid))
            if len(id_que) == max_n:
                break
        if not id_que:
            #print('Information: Nothing to do, sleep for 1 sec.')
            time.sleep(1)
            continue
        new_list = site.get_text_by_revid(revid_que)
        old_list = site.get_text_by_revid(old_revid_que)

        # Step 2: find the diffs and pick out disambig links added
        rst = find_disambig_links(site, id_que, new_list, old_list)

        # Step 3: Log and go to next loop
        for i, r in enumerate(rst):
            if not r:
                continue
            # add {{需要消歧义}} to the article
            while True:
                # try to edit again and again
                text = site.get_text_by_title(id_que[i][3], ts=True)
                # s.group(1) and ...: considering uncompleted links '[[]]'
                new_text = link_t_re.sub(lambda s: s.group(0) + '{{需要消歧义|date=%s年%d月}}' % (id_que[i][2][:4], int(id_que[i][2][5:7])) if s.group(1) and s.group(1) in ''.join(r) else s.group(0), text)
                site.edit(new_text, '机器人：{{[[Template:需要消歧义|需要消歧义]]}}', title=id_que[i][3],
                      bot=False, basets=site.ts, startts=site.ts)
                if site.status != 'editconflict':
                    break

            # no change means the dablink is already fixed, do not notice
            if site.status == 'nochange' or site.status == 'pagedeleted':
                continue
            elif site.status:
                log(site, "保存[[%s]]失败：%s！需要消歧义的内链有：%s－'''[https://dispenser.homenet.org/~dispenser/cgi-bin/dab_solver.py/zh:%s 修复它！]'''" % (id_que[i][3], site.status, ''.join(r), id_que[i][3]), site.ts, red=True)
    
            # notice user
            user_talk = 'User talk:%s' % id_que[i][0]
            [talk_text, is_flow] = site.get_text_by_title(user_talk, detect_flow=True)
            will_notify = site.editcount(id_que[i][0]) >= 100 and judge_allowed(talk_text)

            [notice, item, title, summary] = site.get_text_by_ids(['5574512', '5574516', '5575182', '5575256'])
            year, month, day = id_que[i][2][:4], int(id_que[i][2][5:7]), int(id_que[i][2][8:10])
            title = title % (year, month, day)
            item = item % (id_que[i][3], '、'.join(r), id_que[i][5], id_que[i][3].replace(' ', '_'))
            
            if not will_notify:
                log(site, '检查User:%s（不通知）于%s的编辑时发现%s' % (id_que[i][0], id_que[i][2], item[2:]), id_que[i][2])
                continue

            # notice
            if is_flow:
                if (user_talk+title) in site.flow_ids:
                    id = site.flow_ids[user_talk+title]
                    site.flow_reply('Topic:'+id, id, '补充：\n'+item)
                else:
                    site.flow_new_topic(user_talk, title, notice % item)
            else:
                lines = talk_text.splitlines(True)
                s, sec = 0, 0
                for l, line in enumerate(lines):
                    m = section_re.match(line)
                    if m is not None:
                        s += 1
                        if m.group('title').strip() == title:
                            sectitle, sec = m.group('title'), s
                    if notice.splitlines()[-1] in line and sec != 0:
                        line = sign_re.sub('--~~~~', line)
                        lines.insert(l, item+'\n\n')
                        site.edit(''.join(lines), '/* %s */ ' % sectitle + summary, title=user_talk)
                        break
                else:
                    site.edit(notice % item+' --~~~~', summary, title=user_talk, append=True, section='new', sectiontitle=title, nocreate=False)

            # log
            log(site, '检查User:%s（%s通知）于%s的编辑时发现%s' % (id_que[i][0], '未' if site.status else '已', id_que[i][2], item[2:]), id_que[i][2], site.status)

        id_count = 0
        id_que, revid_que, old_revid_que = [], [], []
        # now *change* equals to the last edit iterated, record it
        if change['timestamp'][:10] != last_ts[:10]:
            # delete out-dated keys
            [title] = site.get_text_by_ids(['5575182'])
            year, month, day = last_ts[:4], int(last_ts[5:7]), int(last_ts[8:10])
            title = title % (year, month, day)
            tmp = site.flow_ids.copy()
            for k in site.flow_ids.keys():
                if title in k:
                    del tmp[k]
            site.flow_ids = tmp
        last_ts, last_id = change['timestamp'], change['revid']

if __name__ == '__main__':
    main(sys.argv[1])
