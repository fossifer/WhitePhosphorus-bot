import sys
import time
import sched
import _thread
from src import core, botsite, rcwatcher, report
from src.main import periodic


DEBUG = True


def main(pwd):
    scheduler = sched.scheduler(timefunc=time.time, delayfunc=time.sleep)

    site = botsite.Site()
    site.client_login(pwd=pwd)

    watcher = rcwatcher.watcher(seconds=43200)

    periodic(scheduler, 3, 1, core.main)
    periodic(scheduler, 3, 2, watcher.watch)
    _thread.start_new_thread(report.main, (rcwatcher.report_que,))

    try:
        scheduler.run()
    except KeyboardInterrupt:
        if DEBUG:
            core.log('the main thread terminated because of KeyboardInterrupt')
        exit(0)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else __import__('getpass').getpass())