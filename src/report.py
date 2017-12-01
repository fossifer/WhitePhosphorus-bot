import re
import time
import datetime
import ipaddress
from dateutil.relativedelta import relativedelta
from . import botsite
from .core import check, log, EditQueue
from .botsite import cur_timestamp, get_summary

DEBUG = False

DELAY = 1800
LONG_SLEEP = 120
SHORT_SLEEP = 30

VIP = 'Wikipedia:当前的破坏'
RFP = 'Wikipedia:请求保护页面'
UAA = 'Wikipedia:需要管理員注意的用戶名'

blank_re = re.compile(r'^\s*$')
vandal_re = re.compile(r'===\s*{{\s*[Vv]andal\s*\|\s*(?:1=)?(.*?)\s*}}\s*===')
result_re = re.compile(r'^\*\s*[处處]理：\s*(<!--[\s\S]*?-->)?\s*$')
uaa_re = re.compile(r'{{\s*[Uu]ser-uaa\s*\|\s*(?:1=)?(.*?)\s*}}')
protect_re = re.compile(r'===\s*\[\[:?(.*?)(?:\|.*?)?\]\]\s*===')
unprotect_re = re.compile(r'==\s*[请請]求解除保[护護]\s*==')
ts_re = re.compile(r'\d{4}年\d{1,2}月\d{1,2}日 \([日一二三四五六]\)'
                   ' \d{2}:\d{2} \(UTC\)')

pt_dict = {'sysop': 'f', 'autoconfirmed': 's', 'move': 'm', 'create': 't'}


def translate_date(ts):
    if not ts:
        return ''
    return datetime.datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ').strftime('%Y年%m月%d日%H时%M分%S秒')


# approx works only when tostr is True,
# set it to True when an approx result is needed
def ts_delta(ts, ots, tostr=True, approx=True):
    # "expiry": "infinite" for protection
    # "duration": "indefinite" for block
    if ts in ['infinite', 'indefinite']:
        return 'indef'
    dt = datetime.datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ')
    odt = datetime.datetime.strptime(ots, '%Y-%m-%dT%H:%M:%SZ')
    total_seconds = (dt-odt).total_seconds()
    if not tostr:
        return total_seconds

    delta = None
    if approx:
        seconds = 0
        if total_seconds < 86400:
            # accurate to a minute
            seconds = (total_seconds // 30 + (total_seconds // 30 % 2)) * 30
        elif total_seconds < 5184000:
            # accurate to an hour
            seconds = (total_seconds // 1800 + (total_seconds // 1800 % 2)) * 1800
        else:
            # accurate to a day
            seconds = (total_seconds // 43200 + (total_seconds // 43200 % 2)) * 43200
        delta = relativedelta(odt + datetime.timedelta(seconds=seconds), odt)
    else:
        delta = relativedelta(dt, odt)

    ret = ''
    if delta.years:
        ret += '%d年' % delta.years
    if delta.months:
        ret += '%d个月' % delta.months
    if delta.days:
        ret += '%d天' % delta.days
    if delta.hours:
        ret += '%d小时' % delta.hours
    if delta.minutes:
        ret += '%d分' % delta.minutes
    if delta.seconds:
        ret += '%d秒' % delta.seconds
    return ret


def insert_result(text, title_re, tar, result, stop_re=None):
    lines = text.splitlines(True)
    lines.append('\n')  # For the case that the last line is our target.
    found, ts = False, 0
    for i, line in enumerate(lines):
        if stop_re and stop_re.search(line):
            break
        target = (title_re.findall(line) or [''])[0]
        if found:
            if target or i == len(lines)-1:
                t = i
                while t and not lines[t-1].strip('\n'):
                    t -= 1  # Find the last blank line and insert before it.
                lines.insert(t, result)
                break
            ts += len(ts_re.findall(line))
            if ts > 1:
                return '', False
        # FIXME: The title needs normalization, e.g. [[WP:xxx]]
        elif target.replace('_', ' ') == tar:
            found = True

    return ''.join(lines), found


def ip_in_range(ip, range):
    try:
        target = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return target in range


def isip(user):
    try:
        ipaddress.ip_network(user)
    except ValueError:
        return False
    return True


def handleVIP(change):
    site = botsite.Site()
    text = site.get_text_by_title(VIP, ts=True)
    basets = site.get_ts()
    user = change.get('title', '')
    params = change.get('logparams', {})
    duration = params.get('duration')
    #duration = translate_dur(params.get('duration'))
    #expiry = translate_date(params.get('expiry'))
    timestamp = change.get('timestamp')
    expiry = params.get('expiry')
    sysop = change.get('user')

    if change.get('logaction') == 'unblock':
        return None

    if not expiry:
        if duration in ['infinite', 'indefinite']:
            expiry = duration
        else:
            log('Warning: bad block log entry -- cannot parse expiry: ' + str(change))
            return None
    if not any([sysop, user, timestamp]):
        log('Warning: bad block log entry -- cannot parse src, dest or timestamp: ' + str(change))
        return None

    # check if admins have changed their minds
    # If the expiry has been changed, the block will be handled later
    block_log = site.api_get({'action': 'query', 'list': 'logevents', 'letype': 'block',
                              'letitle': user, 'lelimit': 1}, 'query').get('logevents')
    if not block_log or type(block_log) != list:
        return None
    block_log = block_log[0]
    new_params = block_log.get('params', {})
    # if expiry is None, use duration (for indefinite blocks)
    if (new_params.get('expiry') or new_params.get('duration')) != expiry:
        return None

    user, ip_range = user[5:], None
    ip = isip(user)
    if '/' in user:
        # ip range
        try:
            ip_range = ipaddress.ip_network(user)
        except ValueError:
            # This should not happen, but who knows...
            log('handleVIP: %s does not appear to be'
                'an IPv4 or IPv6 network' % user)
            return None

    lines = text.splitlines(True)
    found, replaced = False, False
    result = '{{Blocked|%s|ad=%s}}' % (ts_delta(expiry, timestamp), sysop)
    if ip_range:
        result += '<small>（对[[special:contribs/{0}|{0}]]的广域封禁）</small>'.format(user)
    result += '。 --~~~~'

    if DEBUG:
        log('Attempting to post a new VIP result: ' + result)

    for i, line in enumerate(lines):
        target = (vandal_re.findall(line) or [''])[0]
        if found:
            if target:  # It's another title.
                break
            match = result_re.search(line)
            if match:
                lines[i] = '* 处理：%s\n' % result
                replaced = True
                break
        elif target:
            if target == user or (ip_range and ip_in_range(target, ip_range)):
                found = True

    if replaced:
        if DEBUG:
            log('A new VIP result will be posted:', result, '\n', sp=' ')
        else:
            EditQueue().push(text=''.join(lines), summary=get_summary('report', '更新[[User:%s]]的处理结果' % user),
                             title=VIP, bot=True, basetimestamp=basets)

    # if not ip:
        # handleUAA(site, user, '** %s\n' % result)


def handleUAA(user, result):
    site = botsite.Site()
    text = site.get_text_by_title(UAA, ts=True)
    basets = site.get_ts()
    newtext, found = insert_result(text, uaa_re, user, result)
    if found:
        if DEBUG:
            log('A new UAA result will be posted', result, sp=' ')
        else:
            EditQueue().push(text=newtext, summary=get_summary('report', '更新[[User:%s]]的处理结果' % user),
                             title=UAA, bot=True, basetimestamp=basets)


def handleRFP(change):
    site = botsite.Site()
    text = site.get_text_by_title(RFP, ts=True)
    basets = site.get_ts()
    page = change.get('title')
    sysop = change.get('user')
    details = change.get('logparams', {}).get('details', [])
    ots = change.get('timestamp')
    result = ''

    # check if admins have changed their minds
    protect_log = site.api_get({'action': 'query', 'list': 'logevents', 'letype': 'protect',
                                'letitle': page, 'lelimit': 1}, 'query').get('logevents')
    if not protect_log or type(protect_log) != list:
        return None
    protect_log = protect_log[0]
    # Here we use logid instead of expiry, because a protection may includes multiple expiring timestamps.
    if protect_log.get('logid') != change.get('logid'):
        return None

    if change.get('logaction') == 'unprotect':
        # don't process unprotecting
        return None
        # result = ': {{RFPP|au}}，操作管理员为{{User link|%s}}' % sysop
    elif change.get('logaction') == 'move_prot':
        # move protection, e.g. logid 7649780 and 7649788
        return None
    else:
        if not any([page, sysop, details, ots]):
            return None

    if details and type(details) == list:
        # Only consider the first item (when there are edit & move protection we ignore the latter)
        pt = details[0]
        result = '* {{{{RFPP|{level}|{time}|by={by}}}}}'.format(level=pt_dict[pt['level']] if \
                        pt['type'] == 'edit' else pt_dict[pt['type']],
                        time=ts_delta(pt['expiry'], ots), by=sysop)
    else:
        log('handleRFP error: "details" is empty or not a list. The log id is %d' % change.get('logid', -1))

    if not result:
        return None
    result += '。 --~~~~'

    if DEBUG:
        log('Attempting to post a new RFP result: %s' % result)

    newtext, found = insert_result(text, protect_re, page, '%s\n' % result, stop_re=unprotect_re)
    if found:
        if DEBUG:
            log('A new RFP result will be posted', result, sp=' ')
        else:
            EditQueue().push(text=newtext, summary=get_summary('report', '更新[[:%s]]的处理结果' % page),
                             title=RFP, bot=True, basetimestamp=basets)


@check('report')
def work(report_que):
    if not report_que.queue:
        return LONG_SLEEP
    change = report_que.queue[0]
    ct = cur_timestamp()
    delta = ts_delta(ct, change.get('timestamp', ct), tostr=False)
    if delta < DELAY:
        ret = DELAY - delta + SHORT_SLEEP
        if DEBUG:
            log('delta < DELAY, waiting for %d seconds...' % ret)
        return ret

    change = report_que.get()
    if DEBUG:
        log('handling {type}: {fr} -> {to} on {ts}'.format(type=change['logtype'], fr=change['user'],
                                                           to=change['title'], ts=change['timestamp']))
    if change['logtype'] == 'block':
        handleVIP(change)
    else:
        handleRFP(change)
    return SHORT_SLEEP


def main(report_que):
    while True:
        sleep_time = work(report_que) or SHORT_SLEEP
        try:
            if DEBUG:
                log('Nothing to do, sleep %d seconds...' % sleep_time)
            time.sleep(sleep_time)
        except KeyboardInterrupt:
            if DEBUG:
                log('program terminated when running report.py because of KeyboardInterrupt')
            exit(0)


if __name__ == '__main__':
    pass
