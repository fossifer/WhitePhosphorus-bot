import re
import sys
import datetime
import botsite
from botsite import remove_nottext, cur_timestamp

working_title = 'Wikipedia:机器人/申请'
success_title = 'Wikipedia:机器人/申请/存档/2017年/获批的申请'
failure_title = 'Wikipedia:机器人/申请/存档/2017年/未获批的申请'

newline = r'\r?\n'
request_title = r'=\s*請求測試許可\s*='
testing_title = r'=\s*正在測試的機械人\s*='
tested_title = r'=\s*已完成測試的機械人\s*='
tail_title = r'=\s*申請覆核\s*='

archive_prefix = (
    "{{存檔頁}}\n'''This is an archive page. "
    "For new bot request, please to go [[Wikipedia:機械人/申請]] "
    "and follow the instructions there.'''\n")

request_re = re.compile(r'%s(.*?)%s' % (request_title + newline, newline + testing_title),
                        re.DOTALL)
testing_re = re.compile(r'%s(.*?)%s' % (testing_title + newline, newline + tested_title),
                        re.DOTALL)
tested_re = re.compile(r'%s(.*?)%s' % (tested_title + newline, tail_title), re.DOTALL)
section_re = [request_re, testing_re, tested_re]
transclude_re = re.compile(r'{{\s*(.*?)\s*}}', re.DOTALL)

delete_re = re.compile(r'<s>[\s\S]*?</s>|<del>[\s\S]*?</del>')

group_notchange = ['OperatorAssistanceNeeded', 'BAGAssistanceNeeded']
group_testing = ['BotTrial', 'BotExtendedTrial']
group_tested = ['BotTrialComplete']
group_success = ['BotSpeedy', 'BotApproved']
group_failure = ['BotDenied', 'BotWithdrawn', 'BotExpired', 'BotRevoked',
                 'BotStatus']

complete_delay_days = 7

STATUS_REQUEST = 0
STATUS_TESTING = 1
STATUS_TESTED = 2
STATUS_SUCCESS = 3
STATUS_FAILURE = 4

section_states = [STATUS_TESTED, STATUS_TESTING, STATUS_REQUEST]

bag_list, needbag_list, needopt_list = [], [], []

user_re = re.compile(r'{{\s*[Uu]ser\s*\|\s*(.*?)\s*}}')


def normalize(title):
    return working_title + title if title.startswith('/') else title


def init(site):
    global bag_list
    # bureaucrats
    bag_list = [user.get('name') for user in site.api_get({'list': 'allusers',
        'action': 'query', 'augroup': 'bureaucrat'},
        'query').get('allusers', [{}])]
    # BAGs
    text = site.get_text_by_title('Wikipedia:機械人審核小組')
    bag_list += [user for user in user_re.findall(text)]


def check_status(site, title, origin):
    global needbag_list, needopt_list
    text = site.get_text_by_title(title, ts=True)
    old = datetime.datetime.strptime(site.ts, '%Y-%m-%dT%H:%M:%SZ')
    text = delete_re.sub('', remove_nottext(text))

    if site.template_in_page('BAGAssistanceNeeded', text=text):
        needbag_list.append(title)
        return origin
    if site.template_in_page('OperatorAssistanceNeeded', text=text):
        needopt_list.append(title)
        return origin

    ret = STATUS_REQUEST
    if site.template_in_page(group_testing, text=text):
        ret = STATUS_TESTING
    now = datetime.datetime.utcnow()
    delay = (now-old).days
    if delay >= complete_delay_days:
        # Rev, Artoria: Are these mutually exclusive? If so, do a hard return.
        ## lziad: Completed.
        if site.template_in_page(group_tested, text=text):
            ret = STATUS_TESTED
        if site.template_in_page(group_success, text=text):
            ret = STATUS_SUCCESS
        if site.template_in_page(group_failure, text=text):
            return STATUS_FAILURE
    else:
        if site.template_in_page(group_tested, text=text):
            ret = origin
        if site.template_in_page(group_success, text=text):
            return STATUS_TESTED

    return ret


week_list = ['一', '二', '三', '四', '五', '六', '日']
def ts_to_text(ts):
    if not ts:
        return ''
    dt = datetime.datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ')
    return '{y}年{m}月{d}日 ({w}) {hh:02d}:{mm:02d} (UTC)'.format(
            y=dt.year, m=dt.month, d=dt.day, w=week_list[dt.weekday()],
            hh=dt.hour, mm=dt.minute)


def search_history(site, title):
    # if there are > 5000 revisions, this will not work
    pages = site.api_get({'action': 'query', 'titles': title, 'prop': 'revisions', 'rvprop': 'timestamp|user', 'rvlimit': 'max'}, 'query').get('pages', {}).values()
    revisions = []
    for page in pages:
        revisions = page.get('revisions', [])
    if not revisions:
        return '','','',''
    last_editor, last_ts = (revisions[0].get('user', ''),
        revisions[0].get('timestamp', ''))
    last_bag, last_bag_ts = '',''
    for rev in revisions:
        user = rev.get('user', '')
        if user in bag_list:
            last_bag, last_bag_ts = user, rev.get('timestamp', '')
            break
    create_ts = revisions[-1].get('timestamp', '')
    return (ts_to_text(create_ts), last_editor, ts_to_text(last_ts),
            last_bag, ts_to_text(last_bag_ts))


def update_status(site, new_list):
    table_header = ('{| border="1" class="sortable wikitable plainlinks"\n'
                    '!机器人名称 !! 状态 !! 创建于 !! 最后编辑者 !! 最后编辑于 !!'
                    '最后BAG编辑者 !! BAG最后编辑于\n|-\n')
    table_tail = '\n|}'
    table_split = '\n|-\n'
    status_list = ['请求测试许可', '测试中', '测试完成']
    color_list = [None, 'lightgreen', 'lightblue']
    req_pattern = ('| [[{0}|{show_name}]] <small>[[Special:Contributions/{1}|贡献]]</small>\n|{2}|{3}\n| {4}\n|| {5} ||| {6}\n| {7}|| {8}')
    req_list = []
    total = 0
    for i, list in enumerate(new_list[:3]):
        for title in list:
            match = re.search(r'Wikipedia:机器人/申请/([^/]*)(/\d+)?', title)
            if match is None:
                continue
            total += 1
            botname = match.group(1)
            status = status_list[i] + ('：需要BAG关注！' if title in needbag_list else '')
            color = 'style="background-color:%s"' % color_list[i] if color_list[i] else ''
            color = 'style="background-color:#f88"' if '！' in status else color
            color += ' data-sort-value="%d%d"' % (i, 0 if title in needbag_list else 5)
            create, last_editor, last_ts, last_bag, last_bag_ts = \
                search_history(site, title)
            req_list.append(req_pattern.format(title, botname, color, status, create, last_editor, last_ts, last_bag, last_bag_ts, show_name=botname+match.group(2) if match.group(2) else botname))
    site.edit(table_header + table_split.join(req_list) + table_tail, '机器人：现有%d个申请，其中%d个需要BAG关注' % (total, len(needbag_list)), title='User:WhitePhosphorus-bot/RFBA Status', nocreate=False, bot=True)


def main(pwd):
    site = botsite.Site()
    site.client_login(pwd)
    
    init(site)
    
    all_text = site.get_text_by_title(working_title)
    basets, startts = site.ts, cur_timestamp()

    # We sort old_list into new_list, and
    # archive types 3 and 4 (success/fail).
    old_list = [transclude_re.findall(
        r.search(all_text).groups(0)[0])
        for r in section_re]
    moved, archived_s, archived_f = 0, 0, 0  # count work for bread
    # request, testing, tested, success, failure
    new_list = [[], [], [], [], []]

    # Rev, Artoria: maybe old/new_index => old/new_status?
    for old_status, sub_list in reversed(list(enumerate(old_list))):
        for i, title in enumerate(sub_list):
            sub_list[i] = normalize(title)
            new_status = check_status(site, sub_list[i], old_status)
            new_list[new_status].append(sub_list[i])
            moved += (0 <= new_status < 3 and new_status != old_status)
            archived_s += (new_status == 3)
            archived_f += (new_status == 4)

    update_status(site, new_list)

    if not any([moved, archived_s, archived_f]):
        return None
    summary = '机器人：移动%d个申请，存档%d个申请' % (moved, archived_s + archived_f)
    summary_a = '机器人：存档%d个申请'
    new_list = ['\n{{'+'}}\n{{'.join(sub_list)+'}}\n' for sub_list in new_list]
    new_text = re.search(r'([\s\S]*?)' + request_title, all_text).groups(0)[0] +\
               request_title.replace(r'\s*', '') + new_list[0] +\
               testing_title.replace(r'\s*', '') + new_list[1] +\
               tested_title.replace(r'\s*', '') + new_list[2] +\
               re.search(r'(\n%s[\s\S]*)$' % tail_title, all_text).groups(0)[0]
    site.edit(new_text, summary, title=working_title, minor=True, bot=True,
              basets=basets, startts=startts)
    if archived_s:
        old_text = site.get_text_by_title(success_title)
        if not old_text:
            new_list[3] = archive_prefix + new_list[3]
        site.edit(new_list[3], summary_a % archived_s, title=success_title,
                  append=old_text, nocreate=False, minor=True, bot=True)
    if archived_f:
        old_text = site.get_text_by_title(failure_title)
        if not old_text:
            new_list[4] = archive_prefix + new_list[4]
        site.edit(new_list[4], summary_a % archived_s, title=failure_title,
                  append=old_text, nocreate=False, minor=True, bot=True)


if __name__ == '__main__':
    main(sys.argv[1])
