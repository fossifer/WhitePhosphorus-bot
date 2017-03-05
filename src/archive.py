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

archive_prefix = (
    "{{存檔頁}}\n'''This is an archive page. "
    "For new bot request, please to go [[Wikipedia:機械人/申請]] "
    "and follow the instructions there.'''\n")

request_re = re.compile(r'%s(.*?)%s' % (request_title + newline, newline + testing_title),
                        re.DOTALL)
testing_re = re.compile(r'%s(.*?)%s' % (testing_title + newline, newline + tested_title),
                        re.DOTALL)
tested_re = re.compile(r'%s(.*?)$' % (tested_title + newline), re.DOTALL)
section_re = [request_re, testing_re, tested_re]
transclude_re = re.compile(r'{{[\s\n\r]*(.*?)[\s\n\r]*}}', re.DOTALL)

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

def normalize(title):
    return working_title + title if title.startswith('/') else title


def check_status(site, title, origin):
    text = site.get_text_by_title(title, ts=True)
    old = datetime.datetime.strptime(site.ts, '%Y-%m-%dT%H:%M:%SZ')
    text = delete_re.sub('', remove_nottext(text))

    if site.template_in_page(group_notchange, text=text):
        return origin

    ret = STATUS_REQUEST
    if site.template_in_page(group_testing, text=text):
        ret = STATUS_TESTING
    now = datetime.datetime.utcnow()
    delay = (now-old).days
    if delay >= complete_delay_days:
        # Rev, Artoria: Are these mutually exclusive? If so, do a hard return.
        if site.template_in_page(group_tested, text=text):
            ret = STATUS_TESTED
        if site.template_in_page(group_success, text=text):
            ret = STATUS_SUCCESS
        if site.template_in_page(group_failure, text=text):
            ret = STATUS_FAILURE
    else:
        if site.template_in_page(group_tested, text=text):
            ret = origin
        if site.template_in_page(group_success, text=text):
            ret = STATUS_TESTED

    return ret

def main(pwd):
    site = botsite.Site()
    site.client_login(pwd)
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
    for old_index, sub_list in enumerate(reversed(old_list)):
        # Correspond to reversed(section_states)
        old_index = 2 - old_index
        for i, title in enumerate(sub_list):
            sub_list[i] = normalize(title)
            new_index = check_status(site, sub_list[i], 0)
            new_list[new_index].append('{{%s}}' % sub_list[i])
            moved += (0 <= new_index < 3 and new_index != old_index)
            archived_s += (new_index == 3)
            archived_f += (new_index == 4)
    if not any([moved, archived_s, archived_f]):
        return None
    summary = '机器人：移动%d个申请，存档%d个申请' % (moved, archived_s + archived_f)
    summary_a = '机器人：存档%d个申请'
    new_list = ['\n'+'\n'.join(sub_list)+'\n' for sub_list in new_list]
    new_text = re.search(r'([\s\S]*?)' + request_title, all_text).groups(0)[0] +
               request_title.replace(r'\s*', '') + new_list[0] +
               testing_title.replace(r'\s*', '') + new_list[1] +
               tested_title.replace(r'\s*', '') + new_list[2]
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
