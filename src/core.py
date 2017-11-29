import re
import time
import datetime
import threading
from . import botsite
from heapq import heappush, heappop, heapify
from .botsite import remove_nottext

DEBUG = False


class Timestamp:
    def __init__(self, **kwargs):
        if kwargs.get('ts_str'):
            self.str = kwargs['ts_str']
            self.ts = datetime.datetime.strptime(self.str, '%Y-%m-%dT%H:%M:%SZ')
        elif kwargs.get('ts_obj'):
            self.str = kwargs['ts_obj'].strftime('%Y-%m-%dT%H:%M:%SZ')
            self.ts = kwargs['ts_obj']
        else:
            raise TypeError('neither ts_str nor ts_obj is specified')

    def __str__(self):
        return self.str

    def strftime(self, fmt):
        return self.ts.strftime(fmt)

    # TODO: __repr__

    def __int__(self):
        return time.mktime(self.ts.timetuple())

    def __ne__(self, other):
        if isinstance(other, Timestamp):
            return self.ts != other.ts

    def __eq__(self, other):
        if isinstance(other, Timestamp):
            return self.ts == other.ts

    def __lt__(self, other):
        if isinstance(other, Timestamp):
            return self.ts < other.ts

    def __gt__(self, other):
        if isinstance(other, Timestamp):
            return self.ts > other.ts

    def __le__(self, other):
        if isinstance(other, Timestamp):
            return self.ts <= other.ts

    def __ge__(self, other):
        if isinstance(other, Timestamp):
            return self.ts >= other.ts

    def __add__(self, other):
        if isinstance(other, datetime.timedelta):
            return Timestamp(ts_obj=self.ts + other)

    def __sub__(self, other):
        if isinstance(other, datetime.timedelta):
            return Timestamp(ts_obj=self.ts - other)
        elif isinstance(other, Timestamp):
            return self.ts - other.ts


def now():
    return Timestamp(ts_obj=datetime.datetime.utcnow())


def log(*args, time=True, sp='\n'):
    if time:
        print('[%s] ' % datetime.datetime.utcnow(), end='')
    for item in args:
        print(item, end=sp)


def singleton(cls, *args, **kwargs):
    instances = {}
    def _singleton(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    return _singleton


def check_core(task_name):
    if task_name is None:
        return True
    title = 'User:%s/controls/%s.js' % (botsite.bot_name, task_name)
    return not botsite.Site().get_text_by_title(title)


def check(task_name):
    def _wrapper(func, *args, **kwargs):
        def _check(*args, **kwargs):
            if check_core(task_name):
                return func(*args, **kwargs)
        return _check
    return _wrapper


class Revision:
    def __init__(self, **kwargs):
        self.task = kwargs.pop('task', None)
        self.ts = kwargs.pop('ts', now())
        self.loop = kwargs.pop('loop', None)
        self.options = kwargs
        self.title = kwargs.get('title', '')
        self.text = kwargs.get('text', '')
        self.summary = kwargs.get('summary', '')
        self.basetimestamp = kwargs.get('basetimestamp')

    def __str__(self):
        return vars(self).__str__()

    def __repr__(self):
        return 'Revision(%s)' % ', '.join(['%s=%s' % (k, v) for k, v in vars(self).items()])

    def __lt__(self, other):
        if isinstance(other, Revision):
            return self.ts < other.ts

    def __gt__(self, other):
        if isinstance(other, Revision):
            return self.ts > other.ts

    def __le__(self, other):
        if isinstance(other, Revision):
            return self.ts <= other.ts

    def __ge__(self, other):
        if isinstance(other, Revision):
            return self.ts >= other.ts


@singleton
class EditQueue:
    def __init__(self):
        self.lock = threading.Lock()
        self.heap = []

    def __len__(self):
        return len(self.heap)

    def push(self, **kwargs):
        with self.lock:
            #kwargs.pop('ts', None)
            rev = Revision(**kwargs)
            heappush(self.heap, rev)

    def peek(self):
        with self.lock:
            if len(self.heap):
                return self.heap[0]

    def pop(self):
        with self.lock:
            if len(self.heap):
                ret = heappop(self.heap)
                if ret.loop:
                    para = vars(ret)
                    para['ts'] = now() + ret.loop
                    heappush(self.heap, Revision(**para))
                return ret

    def remove(self, title):
        with self.lock:
            self.heap = [r for r in self.heap if r.title != title]
            heapify(self.heap)


class InteractiveTask(threading.Thread):
    def __init__(self, task_name, task_func):
        super().__init__()
        self.stopper = threading.Event()
        name = botsite.bot_name
        self.task = task_name
        self.func = task_func
        self.input_page = 'User:{name}/controls/{task}/input'.format(
            name=name, task=task_name)
        self.status_page = 'User:{name}/controls/{task}/status'.format(
            name=name, task=task_name)
        self.msg_page = 'User:{name}/controls/{task}/message'.format(
            name=name, task=task_name)
        self.dump_page = 'User:{name}/dump'.format(name=name)

    def terminate(self):
        self.stopper.set()

    def work(self):
        site = botsite.Site()
        EditQueue().push(text='running', title=self.status_page,
                         summary='机器人：正在执行任务' + self.task,
                         bot=True, minor=True)

        input = site.get_text_by_title(self.input_page)
        result = self.func(input)

        success, result_msg, result_dump = True, '', ''
        if type(result) == bool:
            success = result
        elif type(result) == dict:
            success = result.get('success', True)
            result_msg = result.get('message', '')
            result_dump = result.get('dump', '')

        EditQueue().remove(self.status_page)
        if success:
            EditQueue().push(text='succeeded', title=self.status_page,
                             summary='机器人：成功完成任务' + self.task,
                             bot=True, minor=True)
        else:
            EditQueue().push(text='failed', title=self.status_page,
                             summary='机器人：未能完成任务' + self.task,
                             bot=True, minor=True)
        if result_dump:
            result_msg = result_msg.format(dump='special:permalink/'
                                                '{{subst:REVISIONID:%s}}' % self.dump_page)
            EditQueue().push(text=result_dump, title=self.dump_page,
                             summary='机器人：执行任务%s时产生了临时信息' % self.task,
                             bot=True, minor=True)
        EditQueue().push(text=result_msg or '', title=self.msg_page,
                         summary='机器人：执行任务%s时产生了消息' % self.task,
                         bot=True, minor=True)

    def run(self):
        site = botsite.Site()
        while not self.stopper.isSet():
            text = site.get_text_by_title(self.status_page)
            text = remove_nottext(text).strip().lower()
            if DEBUG:
                log('IATask name: {name}; status: {status}'.format(name=self.task, status=text))
            if text in ['start', '开始', '開始', '启动', '啟動', 'running']:
                self.work()
            time.sleep(30)


def main():
    site = botsite.Site()
    que = EditQueue()
    if len(que) and que.peek().ts < now():
        rev = que.pop()
        if check_core(rev.task):
            site.ex_edit(**rev.options)


if __name__ == '__main__':
    site = botsite.Site()
    site.client_login(pwd=__import__('getpass').getpass())
    que = EditQueue()
    que.push(title='User:WhitePhosphorus/沙盒', text=lambda s,t:re.sub(r'[a-zA-Z]', 'P<sub>4</sub>', t),
             summary='WhitePhosphorus', ts=now()+datetime.timedelta(seconds=20))
    que.push(title='User:WhitePhosphorus/沙盒', text=lambda s,t:re.sub(r'[a-zA-Z]', 'b', t),
             summary='test', ts=now()+datetime.timedelta(seconds=5))
    que.push(title='User:WhitePhosphorus/沙盒',
             text=lambda s,t:re.sub(r'[a-zA-Z0-9]', 'poi', t), summary='poi',
             ts=now()+datetime.timedelta(seconds=10),
             loop=datetime.timedelta(seconds=30))
    while True:
        if len(que) and que.peek().ts < now():
            rev = que.pop()
            site.ex_edit(**rev.options)
        else:
            time.sleep(3)
