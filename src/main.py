import os
import sys
import time
import sched
import _thread
import datetime
from . import core
from . import botsite
from .core import log, EditQueue, InteractiveTask

DEBUG = False

RESTART_TITLE = 'User:WhitePhosphorus-bot/controls/restart'


def delta(h, m, s):
    utcnow = datetime.datetime.utcnow()
    start = datetime.datetime(utcnow.year, utcnow.month, utcnow.day, h, m, s)
    if start < utcnow:
        start += datetime.timedelta(days=1)
    return (start-utcnow).seconds


def periodic(scheduler, interval, priority, function, args=(), kwargs={}):
    scheduler.enter(interval, priority, periodic,
                    (scheduler, interval, priority, function),
                    {'args': args, 'kwargs':kwargs})
    function(*args, **kwargs)


def restart():
    log('Restart...')
    python = sys.executable
    os.execl(python, python, *sys.argv)
    exit(0)


def main(pwd):
    scheduler = sched.scheduler(timefunc=time.time, delayfunc=time.sleep)

    site = botsite.Site()
    site.client_login(pwd=pwd)

    watcher = __import__('.rcwatcher').watcher()

    periodic(scheduler, 3, 1, core.main)
    periodic(scheduler, 3, 2, watcher.watch)
    _thread.start_new_thread(__import__('.report').main, (__import__('.rcwatcher').report_que, ))
    purge = InteractiveTask('purge', __import__('.purge').main)
    _thread.start_new_thread(purge.run, ())

    EditQueue().push(text='', summary='机器人重启完成', bot=True, minor=True,
                     title='User:WhitePhosphorus-bot/controls/restart',
                     nocreate=True)

    arc = __import__('.archive').default_config()

    scheduler.enter(150, 10, periodic, (3600, 10, __import__('.cs1language').fix_lang, ()))
    scheduler.enter(delta(0, 0, 0), 60, periodic, (scheduler, 86400, 60, __import__('.rcarl').main))
    scheduler.enter(delta(3, 45, 0), 50, periodic, (scheduler, 86400, 50, __import__('.badimage').main))
    scheduler.enter(delta(11, 0, 0), 20, periodic, (scheduler, 7200, 20, arc.archive))
    scheduler.enter(delta(16, 0, 0), 80, periodic, (scheduler, 86400, 80, __import__('.draft').main))

    def check_restart():
        if botsite.Site().get_text_by_title(RESTART_TITLE):
            restart()
    scheduler.enter(120, 999, periodic, (scheduler, 3, 999, check_restart))

    def check_bot():
        if not site.check_bot():
            log('Where is my bot flag?')
            site.client_login(pwd)
            if not site.check_bot():
                log('My bot flag has been revoked!')
                exit(0)
    scheduler.enter(900, 888, periodic, (scheduler, 900, 888, check_bot))

    try:
        scheduler.run()
    except KeyboardInterrupt:
        if DEBUG:
            log('the main thread terminated because of KeyboardInterrupt')
        exit(0)


if __name__ == '__main__':
    main(sys.argv[1])