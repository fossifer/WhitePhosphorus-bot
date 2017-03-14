import re
import sys
import time
import queue
import datetime
import ipaddress
import botsite
from botsite import cur_timestamp
from dateutil.relativedelta import relativedelta

delay = 1800

vip = 'Wikipedia:当前的破坏'
rfp = 'Wikipedia:请求保护页面'
uaa = 'Wikipedia:需要管理員注意的用戶名'

blank_re = re.compile(r'^\s*$')
vandal_re = re.compile(r'===\s*{{\s*[Vv]andal\s*\|\s*(?:1=)?(.*?)\s*}}\s*===')
result_re = re.compile(r'\*\s*[处處]理：\s*')
uaa_re = re.compile(r'{{\s*[Uu]ser-uaa\s*\|\s*(?:1=)?(.*?)\s*}}')

protect_re = re.compile(r'===\s*\[\[:?(.*?)(?:\|.*?)?\]\]\s*===')
ts_re = re.compile(r'\d{4}年\d{1,2}月\d{1,2}日 \([日一二三四五六]\)'
                   ' \d{2}:\d{2} \(UTC\)')

dur_dict = {
'seconds': '秒', 'second': '秒',
'minutes': '分', 'minute': '分',
'hours': '小时', 'hour': '小时',
'days': '天', 'day': '天',
'weeks': '周', 'week': '周',
'months': '月', 'month': '月',
'years': '年', 'year': '年',
'indefinite': 'indef'
}

pt_dict = {'sysop': 'f', 'autoconfirmed': 's', 'move': 'm', 'create': 't'}


def translate_dur(dur):
    for k, v in dur_dict.items():
        dur = dur.replace(k, v)
    return dur.replace(' ', '')


def translate_date(ts):
    if not ts:
        return ts
    return datetime.datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ').strftime(
        '%Y年%m月%d日%H时%M分%S秒')


def ts_delta(ts, ots, tostr=True):
    dt = datetime.datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ')
    odt = datetime.datetime.strptime(ots, '%Y-%m-%dT%H:%M:%SZ')
    delta = relativedelta(dt, odt)
    if not tostr:
        return (dt-odt).seconds
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


def insert_result(text, title_re, tar, result):
    lines = text.splitlines(True)
    lines.append('\n')  # For the case that the last line is our target.
    find, ts = False, 0
    for i, line in enumerate(lines):
        target = (title_re.findall(line) or [''])[0]
        if find:
            if target or i == len(lines)-1:
                t = i
                while t and not lines[t-1].strip('\n'):
                    t -= 1  # Find the last blank line and insert before it.
                lines.insert(t, result)
                break
            ts += len(ts_re.findall(line))
            if ts > 1:
                return '', False
        elif target == tar:
            find = True

    return ''.join(lines), find


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


# Although the name is 'handleVIP', UAA is also handled here
def handleVIP(site, change):
    text = site.get_text_by_title(vip, ts=True)
    ts = site.get_ts()
    user = change.get('title', '')
    params = change.get('logparams', {})
    duration = translate_dur(params.get('duration'))
    expiry = translate_date(params.get('expiry'))
    sysop = change.get('user')
    if not any([sysop, user]) or not (duration or expiry):
        return None
    user, ip_range = user[5:], None
    ip = isip(user)
    if '/' in user:
        # ip range
        try:
            ip_range = ipaddress.ip_network(user)
        except ValueError:
            # This should not happen, but who knows...
            print('handleVIP: %s does not appear to be'
                  'an IPv4 or IPv6 network' % user)
            return None

    lines = text.splitlines(True)
    find = False
    result = '{{Blocked|%s|ad=%s}}' % ('至'+expiry if expiry else duration, sysop)
    if ip_range:
        result += '<small>（对%s的广域封禁）</small>' % user
    result += '。 --~~~~'
    for i, line in enumerate(lines):
        target = (vandal_re.findall(line) or [''])[0]
        if find:
            if target:  # It's another title.
                break
            match = result_re.search(line)
            if match:
                lines[i] = '* 处理：%s\n' % result
                break
        elif target:
            if target == user or (ip_range and ip_in_range(target, ip_range)):
                find = True

    if find:
        site.edit(''.join(lines), '机器人：更新[[User:%s]]的处理结果' % user,
                  title=vip, bot=True, basets=ts, startts=ts)

    if not ip:
        handleUAA(site, user, '** %s\n' % result)


def handleUAA(site, user, result):
    text = site.get_text_by_title(uaa, ts=True)
    ts = site.get_ts()
    newtext, find = insert_result(text, uaa_re, user, result)
    if find:
        site.edit(newtext, '机器人：更新[[User:%s]]的处理结果' % user,
                  title=uaa, bot=True, basets=ts, startts=ts)


def handleRFP(site, change):
    text = site.get_text_by_title(rfp, ts=True)
    ts = site.get_ts()
    page = change.get('title')
    sysop = change.get('user')
    details = change.get('logparams', {}).get('details', [])
    ots = change.get('timestamp')
    result = []
    if change.get('logaction') != 'unprotect':
        if not any([page, sysop, details, ots]):
            return None
    else:
        result = ['{{RFPP|au}}，操作管理员为{{User link|%s}}' % sysop]
    for pt in details:
        result.append('{{RFPP|%s|%s|by=%s}}' % (pt_dict[pt['level']] if \
                        pt['type'] == 'edit' else pt_dict[pt['type']], \
                        ts_delta(pt['expiry'], ots), sysop))
    result = '；'.join(result) + '。 --~~~~'

    newtext, find = insert_result(text, protect_re, page, '%s\n' % result)
    if find:
        site.edit(newtext, '机器人：更新[[:%s]]的处理结果' % page,
                  title=rfp, bot=True, basets=ts, startts=ts)


def main(site, report_que):
    while True:
        if not report_que.queue:
            time.sleep(120)
            continue
        change = report_que.queue[0]
        ct = cur_timestamp()
        delta = ts_delta(ct, change.get('timestamp', ct), tostr=False)
        if delta < delay:
            time.sleep(delay - delta + 10)  # +10s(θ..θ) to buffer.
            continue

        change = report_que.get()
        if change['logtype'] == 'block':
            handleVIP(site, change)
        else:
            handleRFP(site, change)


if __name__ == '__main__':
    pass
