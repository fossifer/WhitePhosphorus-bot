import re
import sys
import time
import atexit
import signal
import datetime
import collections
import botsite
import dablink
from botsite import remove_nottext, cur_timestamp
from dablink import remove_templates
#import refnotice

ts_re = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z')

# update here when a new direct page to {{需要消歧义}} is created
dab_needed = r'(?![ \t]*[\r\n]?{{\s*(?:需要消歧[义義]|連結消歧義|链接消歧义|' \
    '[Dd]isambiguation needed))'
#link_re = re.compile(r'\[\[:?(.*?)(\|.*?)?\]\]')
link_t_re = re.compile(r'\[\[:?((?:{0}.)*?)(\|(?:{0}.)*?)?\]\]{0}'
                       .format(dab_needed))
dab_re = re.compile(r'\[\[:?((?:{1}.)*?)(?:\|(?:{1}.)*?)?\]\]{0}'
                        .format(dab_needed.replace('?!', '?:'),
                                r'(?!\]\])'))
section_re = re.compile(r'(^|[^=])==(?P<title>[^=].*?[^=])==([^=]|$)')
sign_re = re.compile(r'--\[\[User:WhitePhosphorus-bot\|白磷的机器人\]\]' \
                     '（\[\[User talk:WhitePhosphorus\|给主人留言\]\]）' \
                     ' \d{4}年\d{1,2}月\d{1,2}日 \([日一二三四五六]\)' \
                     ' \d{2}:\d{2} \(UTC\)')

rcprop = 'user|userid|timestamp|title|ids|comment|loginfo'
rctype = 'edit|new|log'
rcnamespace = '0'

dablink_dir = collections.defaultdict(list)
notice_dir = collections.defaultdict(list)
dablink_delay = 600

max_n = 500  # nonbots 50, bots 500

bot_name = 'WhitePhosphorus-bot'
debug = True


def timedelta(ts1, ts2):
    dt1 = datetime.datetime.strptime(ts1, '%Y-%m-%dT%H:%M:%SZ')
    dt2 = datetime.datetime.strptime(ts2, '%Y-%m-%dT%H:%M:%SZ')
    return abs((dt2 - dt1).seconds)


# TODO: !redirect
def rc_generator(site, rcstart):
    for rc in site.api_get_long({'action': 'query', 'list': 'recentchanges',
                                 'rcstart': rcstart, 'rcdir': 'newer',
                                 'rcnamespace': rcnamespace, 'rctype': rctype,
                                 'rcshow': '!redirect', 'rcprop': rcprop,
                                 'rclimit': 'max'}, 'query'):
        if not rc['recentchanges']:
            raise StopIteration()
        for change in rc['recentchanges']:
            yield change


def dablink_edit_usertalk(site, user, idlist):
    global notice_dir
    if debug: print('dablink_edit_usertalk', user, idlist)
    user_talk = 'User talk:%s' % user
    [talk_text, is_flow] = site.get_text_by_title(user_talk,
        detect_flow=True, ts=True)
    will_notify = site.editcount(user) >= 100 \
        and dablink.judge_allowed(talk_text)
    if not will_notify:
        return None

    tmp = [True] * len(idlist)
    for i, ids in enumerate(idlist):
        if not ids[-1] or site.has_dup_rev(ids[4], ids[5]):
            tmp[i] = False
    idlist = [ids for i, ids in enumerate(idlist) if tmp[i]]
    if not idlist:
        return None

    [notice, item, title, summary] = site.get_text_by_ids([
        '5574512', '5574516', '5575182', '5575256'])
    cts = cur_timestamp()
    year, month, day = cts[:4], int(cts[5:7]), int(cts[8:10])
    title = title % (year, month, day)
    items = '\n'.join([item % (subl[3], '[['+']]、[['.join(subl[-1])+']]', subl[5], subl[3]) for subl in idlist if subl[-1]])

    if is_flow:
        if (user_talk+title) in site.flow_ids:
            id = site.flow_ids[user_talk+title]
            if debug:
                print('flow_reply: %s %s %s' % ('Topic:'+id, id, '补充：\n'+items))
            else:
                site.flow_reply('Topic:'+id, id, '补充：\n'+items)
        else:
            if debug:
                print('flow_new_topic: %s %s %s' % (user_talk, title, notice % items))
            else:
                site.flow_new_topic(user_talk, title, notice % items)
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
                lines.insert(li, items)
                site.edit(''.join(lines), '/* %s */ %s' % (sectitle, summary), title=user_talk, basets=site.ts, startts=site.ts, print_only=debug)
                break
        else:
            site.edit(notice % items+' --~~~~', summary, title=user_talk, append=True, section='new', sectiontitle=title, nocreate=False, print_only=debug)


def dablink_notice(site):
    global notice_dir
    if debug: print('dablink_notice:', notice_dir)
    for user, idlist in notice_dir.items():
        for i, ids in enumerate(idlist):
            # check again
            text = site.get_text_by_title(ids[3])
            text = remove_templates(remove_nottext(text))
            new_links = []
            for link in ids[-1]:
                if re.search(r'\[\[:?%s(\||\]\])' % link, text):
                    new_links.append(link)
            idlist[i] = ids[:-1] + (new_links,)
        dablink_edit_usertalk(site, user, idlist)
    notice_dir = collections.defaultdict(list)


def dablink_handle(site):
    global dablink_dir, notice_dir
    if debug: print('dablink_handle:', dablink_dir)
    tmp = dablink_dir.copy()
    for title, idlist in dablink_dir.items():
        cts = cur_timestamp()
        delta = [timedelta(ids[2], cts) < dablink_delay for ids in idlist]
        #if debug: print('dablink_handle:', delta, [timedelta(ids[2], cts) for ids in idlist])
        if any(delta):
            continue
        all_links = []
        text = site.get_text_by_title(title)
        for i, ids in enumerate(idlist):
            #ids[-1] = ids[-1].split('|')
            idlist[i] = ids[:-1] + (ids[-1].split('|'),)
            all_links.extend(idlist[i][-1])
        if debug: print('dablink_handle:', all_links)
        new_text = link_t_re.sub(lambda s: s.group(0) +
            '{{需要消歧义|date=%s年%d月}}' % (cts[:4],
            int(cts[5:7])) if s.group(1) and
            s.group(1) in all_links else s.group(0), text)
        handled = set(dab_re.findall(new_text)) - set(dab_re.findall(text))
        if debug:
            if title == 'Wikipedia:沙盒': print(all_links, new_text)
            print(idlist)
            print(dab_re.findall(new_text), dab_re.findall(text))
        if handled:
            if debug: print('dablink_handle:', handled)
            while True:
                site.edit(new_text, '机器人：{{[[Template:需要消歧义|需要消歧义]]}}',
                          title=title, bot=False,
                          basets=site.ts, startts=site.ts, print_only=debug)
                if site.status != 'editconflict':
                    break
            if site.status:
                # log something
                continue
        for i, ids in enumerate(idlist):
            if debug: print('dablink_handle 164:', ids[-1], set(ids[-1]), handled)
            idlist[i] = ids[:-1] + (list(set(ids[-1]) & handled),)
            if debug: print('dablink_handle 166:', ids)
            if ids[-1] and ids[0]:
                notice_dir[ids[0]].append(ids)
                print('add')
        del(tmp[title])
        if debug and title == 'Komica': exit(0)
    #if debug: print('dablink_handle:', notice_dir)
    if notice_dir:
        dablink_notice(site)
    dablink_dir = tmp


def del_keys(site, last_ts):
    [title] = site.get_text_by_ids(['5575182'])
    year, month, day = last_ts[:4], int(last_ts[5:7]), int(last_ts[8:10])
    title = title % (year, month, day)
    tmp = site.flow_ids.copy()
    for k in site.flow_ids.keys():
        if title in k:
            del tmp[k]
    site.flow_ids = tmp


def main(pwd):
    global dablink_dir
    site = botsite.Site()
    site.client_login(pwd)
    #latest_log = site.get_text_by_ids(['5571942'])[0].splitlines()[-1]
    last_ts = '2017-03-08T10:23:00Z'   #ts_re.findall(latest_log)[0]
    last_log = last_ts[:10]
    last_id = 43527068   #int(re.findall(r'Special:diff/(\d+)', latest_log)[0])
    
    def signal_handler(signal, frame):
        print(site.flow_ids)
        exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    atexit.register(signal_handler)
    
    # dablink.py
    handled_count = 0
    id_que, revid_que, old_revid_que = [], [], []
    dablink.last_log = last_log
    #

    while True:
        id_que = []
        leisure = True
        for change in rc_generator(site, last_ts):
            leisure = False
            revid, old_revid = change.get('revid', 0), \
                str(change.get('old_revid', '0'))
            if revid <= last_id:
                continue
            revid = str(revid)
            last_ts, last_id = change['timestamp'], change['revid']
            # dablink.py
            if handled_count & 0x3FF == 0:
                dablink.ignoring_templates = \
                    dablink.update_ignore_templates(site)
            handled_count += 1
            if change['type'] == 'log':
                if change['logtype'] == 'move':
                    id_que.append(('', '', change['timestamp'],
                                   change['logparams']['target_title'],
                                   str(change['pageid']), revid, '0'))
            else:
                if '!nobot!' not in change.get('comment', '!nobot!') and \
                        change['user'] != bot_name:
                    id_que.append((change['user'], change['userid'],
                                   change['timestamp'], change['title'],
                                   str(change['pageid']), revid, old_revid))
            #refnotice.main(site, id_que[-1])

            if change['timestamp'][:10] != last_ts[:10]:
                # delete out-dated keys
                del_keys(site, last_ts)

            if len(id_que) == (max_n-200):
                break
        if id_que:
            rst, id_que = dablink.main(site, id_que)
            for i, r in enumerate(rst):
                if not r:
                    continue
                dablink_dir[id_que[i][3]].append(id_que[i] + ('|'.join(r),))
        if True:
            dablink_handle(site)
        if leisure:
            time.sleep(1)
            continue


if __name__ == '__main__':
    main(sys.argv[1])
