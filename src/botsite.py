import re
import time
import json
import datetime
import collections
import requests
import exception

# TODO: Warning: {'result': {'*': 'This result was truncated because it would
# otherwise be larger than the limit of 12,582,912 bytes.'}}

lang = 'zh'
lang_api = 'https://%s.wikipedia.org/w/api.php' % lang

headers = {'User-Agent': "DZLWikiBot/1.0 (https://zh.wikipedia.org/w/"
           "User_talk:WhitePhosphorus) BasedOnPython/3.6"}

comment_re = re.compile(r'<!--[\s\S]*?-->')
nowiki_re = re.compile(r'<nowiki>[\s\S]*?</nowiki>|<pre>[\s\S]*?</pre>')

bot_name = 'WhitePhosphorus-bot'

maxlag = 5.0
max_n = 500  # nonbots 50, bots 500


def cur_timestamp():
    utcnow = str(datetime.datetime.utcnow())
    return utcnow.replace(' ', 'T')[:19] + 'Z'


def remove_nottext(text):
    return nowiki_re.sub('', comment_re.sub('', text))


def check_csrf(f):
    def wrapper(*args, **kwargs):
        site = args[0]
        if not site.check_user():
            site.client_login()
            if 'csrf' not in site.tokens:
                site.tokens['csrf'] = \
                    site.query_tokens('csrf').get('csrftoken')
        return f(*args, **kwargs)
    return wrapper


class Site:
    def __init__(self):
        self.s = requests.Session()
        self.tokens, self.flow_ids, self.status, self.ts = {}, {}, '', ''
        self.pwd = ''

    def api_get(self, req, target, interval=1):
        req['format'] = 'json'
        self.status = ''
        try:
            result = self.s.get(lang_api, params=req, headers=headers).json()
        except:  # json.decoder.JSONDecodeError:
            print('api_get: Try again after %d sec...' % interval)
            print(req, target)
            time.sleep(interval)
            return self.api_get(req, target, interval * 2)
        # print(json.dumps(result, indent=4, sort_keys=True))
        if 'error' in result:
            print(req, target)
            raise exception.Error(result['error'])
        if 'warnings' in result:
            print('api_get: Warning: %s' % result['warnings'])
            print(req, target)
        return result.get(target)

    def api_get_long(self, req, target, last_c='', interval=1):
        req['format'] = 'json'
        self.status = ''
        last_cont = {'continue': last_c}
        while True:
            c_req = req.copy()
            c_req.update(last_cont)
            try:
                result = self.s.get(lang_api,
                                    params=c_req, headers=headers).json()
            except:
                print(req, target, last_c)
                raise exception.Error(result['error'])
                print('api_get_long: Try again after %d sec...' % interval)
                print(req, target, last_c)
                time.sleep(interval)
                for t in self.api_get_long(req, target, last_cont['continue'],
                                           interval * 2):
                    yield t
                break
            if 'error' in result:
                print(req, target, last_c)
                raise exception.Error(result['error'])
            if 'warnings' in result:
                print('api_get_long: Warning: %s' % result['warnings'])
                print(req, target, last_c)
            if target in result:
                yield result[target]
            if 'continue' not in result:
                break
            last_cont = result['continue']

    def api_post(self, data, interval=1):
        data['format'], data['utf8'], data['maxlag'] = 'json', '1', maxlag
        self.status, rst = '', None
        try:
            rst = self.s.post(lang_api, data=data, headers=headers).json()
        except:
            print('api_post: Try again after %d sec...' % interval)
            print(data)
            time.sleep(interval)
            return self.api_post(data, interval * 2)
        if 'error' in rst:
            code = rst['error'].get('code', 'error')
            if code == 'maxlag':
                lag_str = rst['error'].get('info', 'Maxlag Error')
                print(lag_str)
                lag_m = re.search(r'(\d+(.\d+)?) seconds lagged.', lag_str)
                lag_sec = maxlag if lag_m is None else float(lag_m.group(1))
                print('Try again after %f sec...' % lag_sec)
                time.sleep(lag_sec)
                return self.api_post(data, lag_sec)
            self.status = code
        return rst

    def query_tokens(self, type):
        req = {'type': type}
        req['meta'], req['action'] = 'tokens', 'query'
        return self.api_get(req, 'query').get('tokens')

    def check_user(self, interval=1):
        try:
            r = self.s.get('https://zh.wikipedia.org/w/api.php?'
                           'action=query&format=json&assert=user').json()
        except:
            print('check_user: Try again after %d sec...' % interval)
            print(r)
            time.sleep(interval)
            return self.check_user(interval * 2)
        return 'error' not in r

    def check_bot(self):
        try:
            r = self.s.get('https://zh.wikipedia.org/w/api.php?'
                           'action=query&format=json&assert=bot').json()
        except:
            print('check_bot: Try again after %d sec...' % interval)
            print(r)
            time.sleep(interval)
            return self.check_bot(interval * 2)
        return 'error' not in r

    def client_login(self, pwd=None):
        data = {'logintoken': self.query_tokens('login')['logintoken']}
        self.tokens['login'] = data['logintoken']
        data['username'] = bot_name
        data['password'] = pwd if pwd is not None else self.pwd
        data['action'] = 'clientlogin'
        data['loginreturnurl'] = 'https://zh.wikipedia.org/'
        self.pwd = pwd

        result = self.api_post(data)['clientlogin']

        if 'error' in result:
            raise exception.Error(result['error'])
        if 'warnings' in result:
            print('Warning: %s' % result['warnings'])
        if result.get('status') == 'PASS':
            self.tokens['csrf'] = self.query_tokens('csrf').get('csrftoken')
            return None
        else:
            raise exception.Error(result.get('message', 'Login Failed'))

    # TODO: double redirects
    def exact_title(self, title):
        r = self.api_get({'action': 'query', 'titles': title, 'redirects': '1',
                         'converttitles': '1'}, 'query')
        if 'normalized' in r:
            title = r['normalized'][0]['to']
        if 'converted' in r:
            title = r['converted'][0]['to']
        if 'redirects' in r:
            title = r['redirects'][0]['to']
        return title

    def correct_dict(self, pattern, t_dict):
        if pattern is None:
            return t_dict
        for tuple in pattern:
            try:
                t_dict[tuple['to']] = t_dict.pop(tuple['from'])
            except:
                continue
        return t_dict

    def is_disambig(self, titles):
        ret = [False] * len(titles)
        t_str = '|'.join(titles)
        t_dict = collections.defaultdict(list)
        for i, title in enumerate(titles):
            t_dict[title].append(i)
        try:
            r = self.api_post({'action': 'query', 'prop': 'pageprops',
                               'redirects': '1', 'converttitles': '1',
                               'ppprop': 'disambiguation',
                               'titles': t_str}).get('query')
        except requests.exceptions.ConnectionError as error:
            print(error)
            print('is_disambig: try again...')
            return self.is_disambig(titles, t_dict)
        self.correct_dict(r.get('normalized'), t_dict)
        self.correct_dict(r.get('converted'), t_dict)
        self.correct_dict(r.get('redirects'), t_dict)
        for k, v in r.get('pages', {}).items():
            tmp = 'disambiguation' in v.get('pageprops', [])
            for index in t_dict[v.get('title', '')]:
                ret[index] = tmp
        return ret

    def get_text_by_revid(self, revid_list):
        d = dict(zip(revid_list, [i for i in range(len(revid_list))]))
        ret = [''] * len(revid_list)
        try:
            r = self.api_get_long({'action': 'query', 'prop': 'revisions',
                                   'rvprop': 'content|ids',
                                   'revids': '|'.join(revid_list)}, 'query')
        except requests.exceptions.ConnectionError as error:
            print(error)
            print('get_text_by_revid: try again...')
            return self.get_text_by_revid(revid_list)

        for chunk in r:
            # print(json.dumps(chunk, indent=4, sort_keys=True))
            if 'pages' not in chunk:
                continue
            for k, v in chunk['pages'].items():
                if 'revisions' not in v:
                    continue
                for rev in v['revisions']:
                    if 'revid' not in rev or '*' not in rev:
                        continue
                    ret[d[str(rev['revid'])]] = rev['*']

        return ret

    # TODO: duplicate
    def get_text_by_ids(self, id_list):
        ret = [''] * len(id_list)
        d = dict(zip(id_list, [i for i in range(len(id_list))]))
        try:
            r = self.api_get_long({'action': 'query', 'prop': 'revisions',
                                   'rvprop': 'content',
                                   'pageids': '|'.join(id_list)}, 'query')
        except requests.exceptions.ConnectionError as error:
            print(error)
            print('get_text_by_ids: try again...')
            return self.get_text_by_ids(id_list)

        for chunk in r:
            if 'pages' not in chunk:
                continue
            for k, v in chunk['pages'].items():
                try:
                    ret[d[k]] = v['revisions'][0]['*']
                except:
                    continue

        return ret

    def get_text_by_title(self, title, check_title=False,
                          detect_flow=False, ts=False):
        if check_title:
            title = self.exact_title(title)
        req = {'action': 'query', 'titles': title,
               'rvprop': 'content|timestamp'}
        req['prop'] = 'revisions|info' if detect_flow else 'revisions'
        r = self.api_get(req, 'query')['pages']
        for k, v in r.items():
            try:
                if ts:
                    self.ts = v['revisions'][0]['timestamp']
                if detect_flow:
                    if v['contentmodel'] == 'flow-board':
                        r = self.api_get({'action': 'flow', 'submodule': 'view-header', 'page': title, 'vhformat': 'wikitext'}, 'flow')
                        return [r.get('view-header', {}).get('result', {}).get('header', {}).get('revision', {}).get('content', {}).get('content', ''), True]
                    else:
                        return [v['revisions'][0]['*'], False]
                            
                return v['revisions'][0]['*']
            except:
                self.ts = ''
                if detect_flow:
                    return ['', False]
                return ''

    def get_text_by_id(self, pageid):
        req = {'action': 'query', 'pageids': pageid,
               'prop': 'revisions', 'rvprop': 'content|timestamp'}
        r = self.api_get(req, 'query')['pages']
        temp = r.get(pageid, '')
        self.ts = temp['revisions'][0]['timestamp']
        return temp['revisions'][0]['*'] if temp else ''

    def template_in_page(self, names, title=None, text=None):
        assert((title is None) != (text is None))
        if isinstance(names, str):
            names = [names]
        if text is None:
            req = {'action': 'parse', 'page': title, 'prop': 'templates'}
        else:
            req = {'action': 'parse', 'text': text, 'prop': 'templates',
                   'contentmodel': 'wikitext'}
        r = self.api_post(req).get('parse')
        templates = r.get('templates', [{}])
        for t in templates:
            if t.get('*')[9:] in names:
                return True
        return False

    def editcount(self, username):
        r = self.api_get({'action': 'query', 'list': 'users',
                          'ususers': username,
                          'usprop': 'editcount|groups'}, 'query')
        groups = r.get('users', [{}])[0].get('groups')
        if groups is None or 'bot' in groups or 'flood' in groups:
            return 0
        return r.get('users', [{}])[0].get('editcount', 0)

    def cat_generator(self, cat_id):
        for cat in self.api_get_long({'action': 'query',
                                      'list': 'categorymembers',
                                      'cmpageid': cat_id,
                                      'cmnamespace': '0',
                                      'cmprop': 'ids|title',
                                      'cmlimit': 'max'}, 'query'):
            if not cat['categorymembers']:
                raise StopIteration()
            for page in cat['categorymembers']:
                yield str(page['pageid'])

    def what_embeds_it(self, pageid=None, title=None, ns='0', id=True):
        assert((pageid is None) != (title is None))
        req = {'action': 'query', 'list': 'embeddedin', 'einamespace': ns}
        if title is None:
            req['eipageid'] = str(pageid)
        else:
            req['eititle'] = title

        for rst in self.api_get_long(req, 'query'):
            if not rst['embeddedin']:
                raise StopIteration()
            for page in rst['embeddedin']:
                yield str(page['pageid']) if id else str(page['title'])

    @check_csrf
    def edit(self, text, summary, title=None, pageid=None, append=False,
             minor=False, bot=False, nocreate=True, check_title=False,
             section=None, sectiontitle=None, basets=None, startts=None,
             print_only=False, captchaid=None, captchaword=None, interval=6):
        assert((title is None) != (pageid is None))
        assert((captchaid is None) == (captchaword is None))
        if print_only:
            # print('Editing page: '+('#'+pageid if title is None else title))
            print(text)
            return None
        if check_title:
            title = self.exact_title(title)
        data = {'action': 'edit', 'text': text,
                'summary': summary, 'token': self.tokens['csrf']}
        if title is None:
            data['pageid'] = str(pageid)
        else:
            data['title'] = title
        if nocreate:
            data['nocreate'] = '1'
        if append:
            data['appendtext'] = data.pop('text')
        if section is not None:
            data['section'] = section
        if sectiontitle is not None:
            data['section'], data['sectiontitle'] = 'new', sectiontitle
        if minor:
            data['minor'] = '1'
        if bot:
            data['bot'] = '1'
        if basets:
            data['basetimestamp'] = basets
        if startts:
            data['starttimestamp'] = startts
        if captchaid is not None:
            data['captchaid'], data['captchaword'] = captchaid, captchaword

        rst = self.api_post(data)
        if self.status.startswith('noedit') or \
                self.status.startswith('cantcreate'):
            print('Error: Maybe the bot is blocked and it will terminate.')
            exit(0)
        time.sleep(interval)

        if 'edit' in rst and 'result' in rst['edit'] and \
                rst['edit']['result'] == 'Success':
            if 'nochange' in rst['edit']:
                self.status = 'nochange'
            else:
                self.status = ''
        else:
            print('Error: Page not saved, see the following result.')
            print(json.dumps(rst, indent=4, sort_keys=True))
            if 'edit' in rst and 'captcha' in rst['edit']:
                word = input('Input the captcha listed above: ')
                self.edit(text, summary, title=title, pageid=pageid,
                          append=append, minor=minor, bot=bot,
                          nocreate=nocreate, check_title=check_title,
                          section=section, sectiontitle=sectiontitle,
                          print_only=print_only,
                          captchaid=rst['edit']['captcha'].get('id'),
                          captchaword=word)
            elif rst.get('edit', {}).get('abusefilter', {}).get('id'):
                self.status = 'abusefilter #%d' % \
                    rst['edit']['abusefilter']['id']
                if 'info' in rst['edit']:
                    print(rst['edit']['info'])
                else:
                    print('Hit abusefilter #%d!' % rst['abusefilter']['id'])
            elif 'error' not in rst:
                self.status = json.dumps(rst)

    @check_csrf
    def flow_new_topic(self, page, topic, content, check_title=False):
        if check_title:
            page = self.exact_title(page)

        rst = self.api_post({'action': 'flow', 'submodule': 'new-topic',
                             'page': page, 'nttopic': topic,
                             'ntcontent': content,
                             'token': self.tokens['csrf']})

        if 'flow' in rst and 'new-topic' in rst['flow'] and 'status' \
                in rst['flow']['new-topic'] and \
                rst['flow']['new-topic']['status'] == 'ok':
            self.flow_ids[page + topic] = \
                rst['flow']['new-topic']['committed']['topiclist']['topic-id']
            self.status = ''
            time.sleep(6)
        else:
            print('Error: New topic not created, see the following result.')
            print(json.dumps(rst, indent=4, sort_keys=True))
            if 'error' not in rst:
                self.status = json.dumps(rst)

    @check_csrf
    def flow_unlock_topic(self, page, reason):
        rst = self.api_post({'action': 'flow', 'page': page,
                             'submodule': 'lock-topic',
                             'cotmoderationState': 'unlock',
                             'cotreason': reason,
                             'token': self.tokens['csrf']})
        print(json.dumps(rst, indent=4, sort_keys=True))

    @check_csrf
    def flow_reply(self, page, id, content, retry=False):
        rst = self.api_post({'action': 'flow', 'page': page,
                             'submodule': 'reply', 'repreplyTo': id,
                             'repcontent': content,
                             'token': self.tokens['csrf']})

        if 'flow' in rst and 'reply' in rst['flow'] \
                and 'status' in rst['flow']['reply'] \
                and rst['flow']['reply']['status'] == 'ok':
            self.status = ''
            time.sleep(6)
        else:
            if 'error' in rst and 'permissions' in rst['error']:
                if retry:
                    self.status = 'topic locked'
                else:
                    self.flow_unlock_topic(page, '机器人：发送新的通知')
                    self.flow_reply(page, id, content, retry=True)
            else:
                print('Error: reply not saved, see the following result.')
                print(json.dumps(rst, indent=4, sort_keys=True))
                if 'error' not in rst:
                    self.status = json.dumps(rst)

    def has_dup_rev(self, pageid, revid, limit=50):
        limit += 1
        rst = self.api_get({'action': 'query', 'prop': 'revisions',
                            'pageids': pageid, 'rvprop': 'ids|size',
                            'rvlimit': str(limit),
                            'rvstartid': revid}, 'query')
        if rst is None:
            return False
        revisions = rst.get('pages', {}).get(pageid, {}).get('revisions', [])
        if not revisions:
            return False
        suspect_list = []
        base_size = revisions[0].get('size', -1)
        for rev in revisions[1:]:
            if rev.get('size', -2) == base_size:
                suspect_list.append(str(rev.get('revid', '')))
        for sus_id in suspect_list:
            rst = self.api_get({'action': 'query', 'prop':
                                'revisions', 'revids': revid,
                                'rvdiffto': sus_id}, 'query')
            if not rst.get('pages', {}).get(pageid, {}) \
                    .get('revisions', [{}])[0].get('diff', {}).get('*', '喵'):
                return True
        return False


def main():
    pass


if __name__ == '__main__':
    main()
