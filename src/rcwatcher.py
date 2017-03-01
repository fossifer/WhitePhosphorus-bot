import re
import sys
import time
import datetime
import botsite
import dablink

ts_re = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z')

rcprop = 'user|userid|timestamp|title|ids|comment|loginfo'
rctype = 'edit|new|log'
rcnamespace = '0'

max_n = 500  # nonbots 50, bots 500

bot_name = 'WhitePhosphorus-bot'


# TODO: !redirect
def rc_generator(site, rcstart):
    for rc in site.api_get_long({'action': 'query', 'list': 'recentchanges',
                                 'rcstart': rcstart, 'rcdir': 'newer',
                                 'rcnamespace': rcnamespace, 'rctype': rctype,
                                 'rcshow': '!redirect', 'rcprop': rcprop,
                                 'rclimit': 'max'}, 'query'):
        if not rc['recentchanges']:
            raise StopIteration()
        for change in rc['recentchanges']:
            yield change


def main(pwd):
    site = botsite.Site()
    site.client_login(pwd)
    latest_log = site.get_text_by_ids(['5571942'])[0].splitlines()[-1]
    last_ts = ts_re.findall(latest_log)[0]
    last_log = last_ts[:10]
    last_id = int(re.findall(r'Special:diff/(\d+)', latest_log)[0])

    # dablink.py
    handled_count = 0
    id_que, revid_que, old_revid_que = [], [], []
    dablink.last_log = last_log
    #
    
    while True:
        id_que, revid_que, old_revid_que = [], [], []
        leisure = True
        for change in rc_generator(site, last_ts):
            leisure = False
            revid, old_revid = change.get('revid', 0), \
                str(change.get('old_revid', '0'))
            if revid <= last_id:
                continue
            revid = str(revid)
            last_ts, last_id = change['timestamp'], change['revid']
            # dablink.py
            if handled_count & 0x3FF == 0:
                dablink.ignoring_templates = \
                    dablink.update_ignore_templates(site)
            handled_count += 1
            if change['type'] == 'log':
                if change['logtype'] != 'move':
                    continue#
                id_que.append(('', '', change['timestamp'], \
                    change['logparams']['target_title'], \
                    str(change['pageid']), revid, '0'))
            else:
                if '!nobot!' in change['comment'] or \
                        change['user'] == bot_name:
                    continue#
                id_que.append((change['user'], change['userid'], \
                    change['timestamp'], change['title'], \
                    str(change['pageid']), revid, old_revid))
            revid_que.append(revid)
            old_revid_que.append(old_revid)
            
            if change['timestamp'][:10] != last_ts[:10]:
                # delete out-dated keys
                [title] = site.get_text_by_ids(['5575182'])
                year, month, day = last_ts[:4], \
                    int(last_ts[5:7]), int(last_ts[8:10])
                title = title % (year, month, day)
                tmp = site.flow_ids.copy()
                for k in site.flow_ids.keys():
                    if title in k:
                        del tmp[k]
                site.flow_ids = tmp

            if len(id_que) == max_n:
                dablink.main(site, id_que, revid_que, old_revid_que)
                continue
        if id_que:
            dablink.main(site, id_que, revid_que, old_revid_que)
        if leisure:
            time.sleep(1)
            continue


if __name__ == '__main__':
    main(sys.argv[1])