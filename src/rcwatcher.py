import re
import sys
import time
import queue
import datetime
import threading
from . import report
from . import botsite
#import dablink
#import refnotice
#import rfba
from .core import Timestamp, now, log

DEBUG = False

ts_re = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z')

rcprop = 'user|userid|timestamp|title|ids|comment|loginfo'
rctype = 'edit|new|log'
rcnamespace = '*'

max_n = 200

# report.py
report_que = queue.Queue()
# dablink.py
dab_que = queue.Queue()
#


def rc_generator(rcstart):
    site = botsite.Site()
    for rc in site.api_get_long({'action': 'query', 'list': 'recentchanges',
                                 'rcstart': rcstart, 'rcdir': 'newer',
                                 'rcnamespace': rcnamespace, 'rctype': rctype,
                                 'rcprop': rcprop, 'rclimit': 'max'}, 'query'):
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
    last_ts = '2017-03-19T19:36:59Z'   #ts_re.findall(latest_log)[0]
    last_log = last_ts[:10]
    last_id = 43678772   #int(re.findall(r'Special:diff/(\d+)', latest_log)[0])
    site.flow_ids = {}

    # dablink.py
    handled_count = 0
    id_que, revid_que, old_revid_que = [], [], []
    dablink.last_log = last_log
    #

    while True:
        id_que = []
        leisure = True
        for change in rc_generator(last_ts):
            leisure = False
            revid, old_revid = change.get('revid', 0), \
                str(change.get('old_revid', '0'))
            if revid <= last_id:
                continue
            revid = str(revid)
            last_ts, last_id = change['timestamp'], change['revid']

            # No need to update frequently. Don't ask me why 0x3FF.
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
                        change['user'] != botsite.bot_name:
                    id_que.append((change['user'], change['userid'],
                                   change['timestamp'], change['title'],
                                   str(change['pageid']), revid, old_revid))
            #refnotice.main(site, id_que[-1])

            if change['timestamp'][:10] != last_ts[:10]:
                # delete out-dated keys
                del_keys(site, last_ts)

            if len(id_que) == max_n:
                rst = dablink.main(site, id_que)
                for key, value in rst.items():
                    dab_que.put((key, value))
                id_que = []
                continue
        if id_que:
            rst = dablink.main(site, id_que)
            for key, value in rst.items():
                dab_que.put((key, value))
        if leisure:
            time.sleep(1)
            continue

"""
class watcher(threading.Thread):
    def __init__(self):
        super().__init__()
        self.last_ts = now()
        self.last_id = 0
        self.stopper = threading.Event()

    def terminate(self):
        self.stopper.set()

    def run(self):
        while not self.stopper.isSet():
            leisure = True
            for c in rc_generator(self.last_ts):
                leisure = False
                if self.stopper.isSet():
                    break
                if c['rcid'] <= self.last_id:
                    continue
                self.last_id = c['rcid']
                self.last_ts = Timestamp(ts_str=c['timestamp'])

                title = c.get('title', '')
                user = c.get('user', '')

                if user == botsite.bot_name:
                    continue
                print(len(user),len(title))
                if title == rfba.rfba_title:
                    timer = threading.Timer(1, rfba.r_main, args=[c])
                    timer.daemon = True
                    timer.start()
                elif title.startswith(rfba.rfba_title):
                    timer = threading.Timer(1, rfba.s_main, args=[c])
                    timer.daemon = True
                    timer.start()
                    timer = threading.Timer(20, rfba.maintain)
                    timer.daemon = True
                    timer.start()
            if leisure:
                time.sleep(3)
"""


class watcher:
    def __init__(self, seconds=86400):
        self.last_ts = now() - datetime.timedelta(seconds=seconds)
        self.last_id = 0

    def watch(self):
        if DEBUG:
            log('fetching rc from %s...' % self.last_ts)
            n = 0
        for change in rc_generator(self.last_ts):
            rcid = change.get('rcid', 0)
            if rcid <= self.last_id:
                continue
            if DEBUG:
                n += 1
            self.last_ts, self.last_id = change.get('timestamp', ''), rcid
            if change['type'] == 'log' and change.get('logtype') in ['protect', 'block']:
                if DEBUG:
                    log('pushing {type}: {fr} -> {to} on {ts}'.format(type=change['logtype'], fr=change['user'],
                                                                      to=change['title'], ts=change['timestamp']))
                report_que.put(change)
        if DEBUG:
            log('%d rc items handled' % n)


def main(pwd):
    site = botsite.Site()
    site.client_login(pwd)
    """
    def signal_handler(signal, frame):
        print(site.flow_ids)
        exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    atexit.register(signal_handler)
    """
    thread_list = [threading.Thread(target=watch, args=(site,)),
                   threading.Thread(target=report.main, args=(site, report_que)),
                   #threading.Thread(target=dablink.ndab, args=(site, dab_que))
                   ]

    for thread in thread_list:
        thread.start()

    for thread in thread_list:
        thread.join()


if __name__ == '__main__':
    main(sys.argv[1])
