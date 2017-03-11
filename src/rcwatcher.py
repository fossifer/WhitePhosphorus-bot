import re
import sys
import time
import queue
import atexit
import signal
import datetime
import threading
import report
import botsite
import dablink
from threading import Timer
#import refnotice

ts_re = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z')

rcprop = 'user|userid|timestamp|title|ids|comment|loginfo'
rctype = 'edit|new|log'
rcnamespace = '0'

max_n = 500  # nonbots 50, bots 500

bot_name = 'WhitePhosphorus-bot'

# report.py
report_que = queue.Queue()


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


def del_keys(site, last_ts):
    [title] = site.get_text_by_ids(['5575182'])
    year, month, day = last_ts[:4], int(last_ts[5:7]), int(last_ts[8:10])
    title = title % (year, month, day)
    tmp = site.flow_ids.copy()
    for k in site.flow_ids.keys():
        if title in k:
            del tmp[k]
    site.flow_ids = tmp


def watch(site):
    #latest_log = site.get_text_by_ids(['5571942'])[0].splitlines()[-1]
    last_ts = '2017-03-10T08:14:00Z'   #ts_re.findall(latest_log)[0]
    last_log = last_ts[:10]
    last_id = 43553415   #int(re.findall(r'Special:diff/(\d+)', latest_log)[0])
    site.flow_ids = {}

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

            if handled_count & 0x3FF == 0:
                dablink.ignoring_templates = \
                    dablink.update_ignore_templates(site)
            handled_count += 1
            if change['type'] == 'log':
                if change['logtype'] == 'move':
                    id_que.append(('', '', change['timestamp'],
                                   change['logparams']['target_title'],
                                   str(change['pageid']), revid, '0'))
                elif change['logtype'] in ['protect', 'block']:
                    report_que.put(change)
            else:
                if '!nobot!' not in change['comment'] and \
                        change['user'] != bot_name:
                    id_que.append((change['user'], change['userid'],
                                   change['timestamp'], change['title'],
                                   str(change['pageid']), revid, old_revid))
            #refnotice.main(site, id_que[-1])

            if change['timestamp'][:10] != last_ts[:10]:
                # delete out-dated keys
                del_keys(site, last_ts)

            if len(id_que) == max_n:
                dablink.main(site, id_que)
                continue
        if id_que:
            dablink.main(site, id_que)
        if leisure:
            time.sleep(1)
            continue


def main(pwd):
    site = botsite.Site()
    site.client_login(pwd)
    thread_list = [threading.Thread(target=watch, args=(site,)),
                   threading.Thread(target=report.main, args=(site, report_que))
                   ]

    for thread in thread_list:
        thread.start()

    for thread in thread_list:
        thread.join()


if __name__ == '__main__':
    main(sys.argv[1])
