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


class watcher:
    def __init__(self, seconds=86400):
        self.last_ts = now() - datetime.timedelta(seconds=seconds)
        self.last_id = 0

    def watch(self):
        if DEBUG:
            # log('fetching rc from %s...' % self.last_ts)
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
        if DEBUG and n:
            log('%d rc items handled' % n)


def main(pwd):
    pass


if __name__ == '__main__':
    main(sys.argv[1])
