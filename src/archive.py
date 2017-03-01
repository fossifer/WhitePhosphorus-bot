import re
import sys
import datetime
import botsite
from botsite import remove_nottext, cur_timestamp

working_title = 'Wikipedia:机器人/申请'
success_title = 'Wikipedia:机器人/申请/存档/2017年/獲批的申請'
failure_title = 'Wikipedia:机器人/申请/存档/2017年/未獲批的申請'

request_title = r'=\s*請求測試許可\s*='
testing_title = r'=\s*正在測試的機械人\s*='
tested_title = r'=\s*已完成測試的機械人\s*='

request_re = re.compile(r'%s(.*?)%s' % (request_title, testing_title), re.DOTALL)
testing_re = re.compile(r'%s(.*?)%s' % (testing_title, tested_title), re.DOTALL)
tested_re = re.compile(r'%s(.*?)$' % (tested_title), re.DOTALL)
section_re = [request_re, testing_re, tested_re]
subpage_re = re.compile(r'{{[\s\n\r]*(.*?)[\s\n\r]*}}', re.DOTALL)

delete_re = re.compile(r'<s>[\s\S]*?</s>|<del>[\s\S]*?</del>')

group_notchange = ['OperatorAssistanceNeeded', 'BAGAssistanceNeeded']
group_testing = ['BotTrial', 'BotExtendedTrial']
group_tested = ['BotTrialComplete']
group_success = ['BotSpeedy', 'BotApproved']
group_failure = ['BotDenied', 'BotWithdrawn', 'BotExpired', 'BotRevoked',
                 'BotStatus']

complete_delay_days = 7

def normalize(title):
    return working_title + title if title.startswith('/') else title

def handle(site, title, origin):
    text = site.get_text_by_title(title, ts=True)
    old = datetime.datetime.strptime(site.ts, '%Y-%m-%dT%H:%M:%SZ')
    text = delete_re.sub('', remove_nottext(text))
    
    if site.template_in_page(group_notchange, text=text):
        return origin

    ret = 0
    if site.template_in_page(group_testing, text=text):
        ret = 1
    if site.template_in_page(group_tested, text=text):
        ret = 2
    now = datetime.datetime.utcnow()
    delay = (now-old).days
    if delay >= complete_delay_days:
        if site.template_in_page(group_success, text=text):
            ret = 3
        if site.template_in_page(group_failure, text=text):
            ret = 4
    else:
        if site.template_in_page(group_success, text=text):
            ret = 2

    return ret

def main(pwd):
    site = botsite.Site()
    site.client_login(pwd)
    all_text = site.get_text_by_title(working_title)
    basets, startts = site.ts, cur_timestamp()
    old_list = list(map(lambda t: subpage_re.findall(t),
                        [r.search(all_text).groups(0)[0] for r in section_re]))
    moved, archived_s, archived_f = 0, 0, 0
    new_list = [[], [], [], [], []] # request, testing, tested, success, failure
    for old_index, sub_list in enumerate(old_list[::-1]):
        old_index = 2 - old_index
        for i, title in enumerate(sub_list):
            sub_list[i] = normalize(title)
            new_index = handle(site, sub_list[i], 0)
            new_list[new_index].append('{{%s}}' % sub_list[i])
            moved += (0 <= new_index < 3 and new_index != old_index)
            archived_s += (new_index == 3)
            archived_f += (new_index == 4)
    if not moved and not archived:
        return None
    summary = '机器人：移动%d个申请，存档%d个申请' % (moved, archived_s + archived_f)
    summary_a = '机器人：存档%d个申请'
    new_list = ['\n'+'\n'.join(sub_list)+'\n' for sub_list in new_list]
    new_text = re.search(r'([\s\S]*?)'+request_title, all_text).groups(0)[0] + \
               request_title.replace(r'\s*', '') + new_list[0] + \
               testing_title.replace(r'\s*', '') + new_list[1] + \
               tested_title.replace(r'\s*', '') + new_list[2]
    site.edit(new_text, summary, title=working_title, bot=True,
              basets=basets, startts= startts)
    if archived_s:
        site.edit(new_list[3], summary_a % archived_s, title=success_title,
                  append=True, nocreate=False, bot=True)
    if archived_f:
        site.edit(new_list[4], summary_a % archived_s, title=failure_title,
                  append=True, nocreate=False, bot=True)

if __name__ == '__main__':
    main(sys.argv[1])
