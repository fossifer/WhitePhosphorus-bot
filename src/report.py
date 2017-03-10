import re
import sys
import datetime
import requests
import botsite
from botsite import remove_nottext, cur_timestamp
from dateutil.relativedelta import relativedelta

vip = 'Wikipedia:当前的破坏'
rfpt = 'Wikipedia:请求保护页面'

vandal_re = re.compile(r'===\s*{{\s*[Vv]andal\s*\|\s*(.*?)\s*}}\s*===')
result_re = re.compile(r'\*\s*[处處]理：\s*')

protect_re = re.compile(r'===\s*\[\[:?(.*?)(?:\|.*?)?\]\]\s*===')
ts_re = re.compile(r'\d{4}年\d{1,2}月\d{1,2}日 \([日一二三四五六]\)'
                   ' \d{2}:\d{2} \(UTC\)')

dur_dict = {
'seconds': '秒', 'second': '秒',
'minutes': '分', 'minute': '分',
'hours': '小时', 'hour': '小时',
'days': '天', 'day': '天',
'weeks': '周', 'week': '周',
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


def ts_delta(ts, ots):
    dt = datetime.datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ')
    odt = datetime.datetime.strptime(ots, '%Y-%m-%dT%H:%M:%SZ')
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


def handleVIP(site, change):
    text = site.get_text_by_title(vip, ts=True)
    ts = site.ts
    user = change.get('title', '')
    
    params = change.get('logparams', {})
    duration = translate_dur(params.get('duration'))
    expiry = translate_date(params.get('expiry'))
    sysop = change.get('user')
    if not any([sysop, user]) or not (duration or expiry):
        return None
    user = user[5:]
    if '/' in user:
        # TODO: ip range
        return None

    lines = text.splitlines(True)
    find = False
    result = '{{Blocked|%s|ad=%s}}。 --~~~~' % (
        '至'+expiry if expiry else duration, sysop)
    for i, line in enumerate(lines):
        target = (vandal_re.findall(line) or [''])[0]
        if find:
            if target:  # It's another title.
                break
            match = result_re.search(line)
            if match:
                lines[i] = '* 处理：%s\n' % result
                break
        elif target == user:
            find = True

    if find:
        site.edit(''.join(lines), '机器人：更新[[User:%s]]的处理结果' % user,
                  title=vip, bot=True, basets=ts, startts=ts)


def handleRFPT(site, change):
    text = site.get_text_by_title(rfpt, ts=True)
    ts = site.ts
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

    lines = text.splitlines(True)
    find, ts = False, 0
    for i, line in enumerate(lines):
        target = (protect_re.findall(line) or [''])[0]
        if find:
            if target or i == len(lines)-1:
                t = i
                while t and not line[t-1].strip('\n'):
                    t -= 1  # Find the last blank line and insert before it.
                lines.insert(t, '%s\n' % result)
                break
            ts += len(ts_re.findall(line))
            if ts > 1:
                return None
        elif target == page:
            find = True

    if find:
        site.edit(''.join(lines), '机器人：更新[[:%s]]的处理结果' % page,
                  title=rfpt, bot=True, basets=ts, startts=ts)


def main(change):
    if change['logtype'] == 'block':
        handleVIP(site, change)
    else:
        handleRFPT(site, change)


if __name__ == '__main__':
    pass
