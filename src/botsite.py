import re
import time
import json
import datetime
import threading
import collections
import requests
from . import exception

# TODO: Warning: {'result': {'*': 'This result was truncated because it would
# otherwise be larger than the limit of 12,582,912 bytes.'}}

debug = False

lang = 'zh'

if not debug:
    lang_api = 'https://%s.wikipedia.org/w/api.php' % lang
    headers = {'User-Agent': "P4WikiBot/1.0 (https://zh.wikipedia.org/w/"
               "User_talk:WhitePhosphorus) BasedOnPython/3.6"}
    bot_name = 'WhitePhosphorus-bot'
else:
    lang_api = 'https://%s.wikipedia.beta.wmflabs.org/w/api.php' % lang
    headers = {'User-Agent': 'P4-test via Python 3.6'}
    bot_name = 'WhitePhosphorus-bot'

comment_re = re.compile(r'<!--[\s\S]*?-->')
nowiki_re = re.compile(r'<nowiki>[\s\S]*?</nowiki>|<pre>[\s\S]*?</pre>|'
                       r'<src[\s\S]*?</src>')

maxlag = 5.0


def get_summary(task, body):
    return '[[User:{name}/tasks/{task}|机器人]]（[[User:{name}/controls/{task}.json|紧急开关]]）：'.format(name=bot_name,
                                                                                                task=task) + body


def log(*args, time=True, sp='\n'):
    if time:
        print('[%s] ' % datetime.datetime.utcnow(), end='')
    for item in args:
        print(item, end=sp)


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
            tmp = site.get_tokens('csrf')
            if not tmp:
                site.set_tokens('csrf', site.query_tokens('csrf').get('csrftoken'))
        return f(*args, **kwargs)
    return wrapper

def singleton(cls, *args, **kwargs):
    instances = {}
    def _singleton(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    return _singleton


@singleton
class Site:
    def __init__(self):
        self.s = requests.Session()
        self.tokens, self.flow_ids, self.status, self.ts = {}, {}, '', ''
        self._tokens_l, self._flow_ids_l, self._status_l, self._ts_l = \
            (threading.Lock(),) * 4
        self.pwd = ''

    def get_tokens(self, key, default=None):
        with self._tokens_l:
            return self.tokens.get('key', default)

    def set_tokens(self, key, value):
        with self._tokens_l:
            self.tokens['key'] = value

    def get_flow_ids(self):
        with self._flow_ids_l:
            return self.flow_ids

    def set_flow_ids(self, key, value):
        with self._flow_ids_l:
            self.flow_ids[key] = value

    def get_status(self):
        with self._status_l:
            return self.status

    def set_status(self, value):
        with self._status_l:
            self.status = value

    def get_ts(self):
        with self._ts_l:
            return self.ts

    def set_ts(self, value):
        with self._ts_l:
            self.ts = value

    def api_get(self, req, target, interval=1):
        req['format'] = 'json'
        self.set_status('')
        try:
            result = self.s.get(lang_api, params=req, headers=headers).json()
        except:  # json.decoder.JSONDecodeError:
            log('api_get: Try again after %d sec...' % interval)
            time.sleep(interval)
            return self.api_get(req, target, interval * 2)
        # print(json.dumps(result, indent=4, sort_keys=True))
        if 'error' in result:
            code = result['error'].get('code', 'error')
            if code == 'maxlag':
                lag_str = result['error'].get('info', 'Maxlag Error')
                log(lag_str)
                lag_m = re.search(r'(\d+(\.\d+)?) seconds lagged.', lag_str)
                lag_sec = maxlag if lag_m is None else float(lag_m.group(1))
                log('api_get: Try again after %f sec...' % lag_sec)
                time.sleep(lag_sec)
                return self.api_get(req, target)
            log('api_get error!', req, target)
            raise exception.Error(result['error'])
        if 'warnings' in result:
            log('api_get: Warning: %s' % result['warnings'], req, target)
        return result.get(target)

    def api_get_long(self, req, target, last_c='', interval=1):
        req['format'] = 'json'
        self.set_status('')
        last_cont = {'continue': last_c}
        while True:
            c_req = req.copy()
            c_req.update(last_cont)
            try:
                result = self.s.get(lang_api,
                                    params=c_req, headers=headers).json()
            except requests.exceptions.ConnectionError as error:
                log(error)
                log('api_get_long: Try again after %d sec...' % interval)
                time.sleep(interval)
                for t in self.api_get_long(req, target, last_cont['continue'],
                                           interval * 2):
                    yield t
                break
            if 'error' in result:
                code = result['error'].get('code', 'error')
                if code == 'maxlag':
                    lag_str = result['error'].get('info', 'Maxlag Error')
                    log(lag_str)
                    lag_m = re.search(r'(\d+(\.\d+)?) seconds lagged.', lag_str)
                    lag_sec = maxlag if lag_m is None else float(lag_m.group(1))
                    log('api_get_long: Try again after %f sec...' % lag_sec)
                    time.sleep(lag_sec)
                    for t in self.api_get_long(req, target, last_c=last_c):
                        yield t
                    break
                log(result)
                raise exception.Error(result['error'])
            if 'warnings' in result:
                log('api_get_long: Warning:', result['warnings'])
            if target in result:
                yield result[target]
            if 'continue' not in result:
                break
            last_cont = result['continue']

    def api_post(self, data, interval=1, retry=False):
        data['format'], data['utf8'], data['maxlag'] = 'json', '1', maxlag
        self.set_status('')
        rst = None
        try:
            rst = self.s.post(lang_api, data=data, headers=headers).json()
        except:
            log('api_post: Try again after %d sec...' % interval)
            time.sleep(interval)
            return self.api_post(data, interval * 2)
        if 'error' in rst:
            code = rst['error'].get('code', 'error')
            if code == 'maxlag':
                lag_str = rst['error'].get('info', 'Maxlag Error')
                log(lag_str)
                lag_m = re.search(r'(\d+(\.\d+)?) seconds lagged.', lag_str)
                lag_sec = maxlag if lag_m is None else float(lag_m.group(1))
                log('api_post: Try again after %f sec...' % lag_sec)
                time.sleep(lag_sec)
                return self.api_post(data)
            elif code == 'badtoken':
                self.set_tokens('csrf', self.query_tokens('csrf'))
                if not retry:
                    self.api_post(data, interval=interval, retry=True)
                else:
                    log('Invalid token.')
            self.set_status(code)
        elif 'warnings' in rst:
            log('api_post: Warning:', rst['warnings'])
        return rst

    def api_post_long(self, data, target='', last_c='', interval=1, retry=False):
        data['format'], data['utf8'], data['maxlag'] = 'json', '1', maxlag
        self.set_status('')
        target = target or data['action']
        last_cont = {'continue': last_c}
        while True:
            c_req = data.copy()
            c_req.update(last_cont)
            try:
                result = self.s.post(lang_api, data=c_req, headers=headers).json()
            except requests.exceptions.ConnectionError as error:
                log(error)
                log('api_post_long: Try again after %d sec...' % interval)
                time.sleep(interval)
                for t in self.api_post_long(data, target, last_cont['continue'], interval=interval*2):
                    yield t
                break
            if 'error' in result:
                code = result['error'].get('code', 'error')
                if code == 'maxlag':
                    lag_str = result['error'].get('info', 'Maxlag Error')
                    log(lag_str)
                    lag_m = re.search(r'(\d+(\.\d+)?) seconds lagged.', lag_str)
                    lag_sec = maxlag if lag_m is None else float(lag_m.group(1))
                    log('api_post_long: Try again after %f sec...' % lag_sec)
                    time.sleep(lag_sec)
                    for t in self.api_post_long(data, target=target, last_c=last_c):
                        yield t
                    break
                self.set_status(code)
            if 'warnings' in result:
                log('api_get_long: Warning:', result['warnings'])
            if target in result:
                yield result[target]
            if 'continue' not in result:
                break
            last_cont = result['continue']


    def query_tokens(self, type):
        req = {'type': type}
        req['meta'], req['action'] = 'tokens', 'query'
        return self.api_get(req, 'query').get('tokens')

    def check_user(self, interval=1):
        r = None
        try:
            r = self.s.get(lang_api + '?'
                           'action=query&format=json&assert=user').json()
        except requests.exceptions.ConnectionError as e:
            log('check_user: ConnectionError, try again after %d sec...' % interval)
            time.sleep(interval)
            return self.check_user(interval * 2)
        return 'error' not in r

    def check_bot(self, interval=1):
        r = None
        try:
            r = self.s.get(lang_api + '?'
                           'action=query&format=json&assert=bot').json()
        except requests.exceptions.ConnectionError as e:
            log('check_bot: ConnectionError, try again after %d sec...' % interval)
            time.sleep(interval)
            return self.check_bot(interval * 2)
        return 'error' not in r

    def client_login(self, pwd=None):
        data = {'logintoken': self.query_tokens('login')['logintoken']}
        self.set_tokens('login', data['logintoken'])
        data['username'] = bot_name
        data['password'] = pwd if pwd is not None else self.pwd
        data['action'] = 'clientlogin'
        data['loginreturnurl'] = 'https://zh.wikipedia.org/'

        result = self.api_post(data)['clientlogin']

        if 'error' in result:
            raise exception.Error(result['error'])
        if 'warnings' in result:
            log('Warning: %s' % result['warnings'])
        if result.get('status') == 'PASS':
            self.set_tokens('csrf',self.query_tokens('csrf').get('csrftoken'))
            return None
        else:
            raise exception.Error(result.get('message', 'Login Failed'))

    # TODO: double redirects
    def exact_title(self, title):
        r = self.api_get({'action': 'query', 'titles': title, 'redirects': '1',
                         'converttitles': '1'}, 'query')
        if not r:
            return title
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
            log('is_disambig: ConnectionError, try again...')
            return self.is_disambig(titles)
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
            r = self.api_post({'action': 'query', 'prop': 'revisions',
                                   'rvprop': 'content|ids',
                                   'revids': '|'.join(revid_list)}).get('query')
        except requests.exceptions.ConnectionError as error:
            log('get_text_by_revid: ConnectionError, try again...')
            return self.get_text_by_revid(revid_list)

        if not r or 'pages' not in r:
            log(revid_list)
            return ret
        for k, v in r['pages'].items():
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
            log('get_text_by_ids: ConnectionError, try again...')
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
                    self.set_ts(v['revisions'][0]['timestamp'])
                if detect_flow:
                    return [v['revisions'][0]['*'],
                            v['contentmodel'] == 'flow-board']
                return v['revisions'][0]['*']
            except:
                self.set_ts('')
                if detect_flow:
                    return ['', False]
                return ''

    def get_text_by_id(self, pageid):
        req = {'action': 'query', 'pageids': pageid,
               'prop': 'revisions', 'rvprop': 'content|timestamp'}
        r = self.api_get(req, 'query')['pages']
        temp = r.get(pageid, '')
        # TODO: missing
        self.set_ts(temp['revisions'][0]['timestamp'] if temp else '')
        return temp['revisions'][0]['*'] if temp else ''

    def parse(self, text):
        r = self.api_post({'action': 'parse', 'text': text,
                           'prop': 'text', 'contentmodel': 'wikitext',
                           'disablelimitreport': 1})
        if not hasattr(r, 'get'):
            return ''
        return r.get('parse', {}).get('text', {}).get('*', '')

    def get_html_by_title(self, title):
        r = self.api_post({'action': 'parse', 'page': title,
                           'prop': 'text', 'contentmodel': 'wikitext',
                           'disablelimitreport': 1})
        if not hasattr(r, 'get'):
            return ''
        return r.get('parse', {}).get('text', {}).get('*', '')

    def list_templates(self, text):
        r = self.api_post({'action': 'parse', 'text': text,
                           'prop': 'templates', 'contentmodel': 'wikitext'})
        if not hasattr(r, 'get'):
            return set()
        return set([t.get('*', '喵'*9)[9:] for t in r.get('templates', [{}])])

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
        if not r:
            return False
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

    def cat_generator(self, cat_id, get_sortkey=False, startsortkey=None):
        for cat in self.api_get_long({'action': 'query',
                                      'list': 'categorymembers',
                                      'cmpageid': cat_id,
                                      'cmnamespace': '0',
                                      'cmprop': 'ids|title|sortkey',
                                      'cmstarthexsortkey': startsortkey,
                                      'cmlimit': 'max'}, 'query'):
            if not cat['categorymembers']:
                raise StopIteration()
            for page in cat['categorymembers']:
                if get_sortkey:
                    yield (str(page['pageid']), page['sortkey'])
                else:
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

    def purge(self, forcelinkupdate=False, forcerecursivelinkupdate=False,
              redirects=True, converttitles=True, **kwargs):
        req = {'action': 'purge', 'forcelinkupdate': forcelinkupdate,
               'forcerecursivelinkupdate': forcerecursivelinkupdate,
               'redirects': redirects, 'converttitles': converttitles}
        titles = kwargs.get('titles')
        reqs = [req]
        if titles and type(titles) == list:
            reqs = [req] * ((len(titles)-1) // 500 + 1)
            for i, r in enumerate(reqs):
                r['titles'] = '|'.join(titles[i*500:i*500+500])
        else:
            reqs[0].update(kwargs)
        for r in reqs:
            for chunk in self.api_post_long(r):
                for item in chunk:
                    yield item

    @check_csrf
    def edit(self, text, summary, title=None, pageid=None, append=False,
             minor=False, bot=False, nocreate=True, check_title=False,
             section=None, sectiontitle=None, basets=None, startts=None,
             print_only=False, captchaid=None, captchaword=None, interval=6):
        assert((title is None) != (pageid is None))
        assert((captchaid is None) == (captchaword is None))
        if print_only:
            # print('Editing page: '+('#'+pageid if title is None else title))
            log(text)
            return None
        if check_title:
            title = self.exact_title(title)
        data = {'action': 'edit', 'text': text,
                'summary': summary, 'token': self.get_tokens('csrf')}
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
        st = self.get_status()
        if st.startswith('noedit') or st.startswith('cantcreate'):
            log('Error: Maybe the bot is blocked and it will terminate.')
            exit(0)
        time.sleep(interval)

        if 'edit' in rst and 'result' in rst['edit'] and \
                rst['edit']['result'] == 'Success':
            if 'nochange' in rst['edit']:
                self.set_status('nochange')
            else:
                self.set_status('')
        else:
            log('Error: Page not saved, see the following result.')
            log(json.dumps(rst, indent=4, sort_keys=True))
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
                self.set_status('abusefilter #%d' % \
                    rst['edit']['abusefilter']['id'])
                if 'info' in rst['edit']:
                    log(rst['edit']['info'])
                else:
                    log('Hit abusefilter #%d!' % rst['abusefilter']['id'])
            elif 'error' not in rst:
                self.set_status(json.dumps(rst))

    @check_csrf
    def ex_edit(self, **kwargs):
        title, pageid = kwargs.get('title'), kwargs.get('pageid')
        content = kwargs.get('text')
        if (title is None) == (pageid is None):
            # invalid parameters
            return None
        if callable(content):
            # A function which can generate new content.
            if title:
                text = self.get_text_by_title(title, ts=True)
            else:
                text = self.get_text_by_id(pageid)
            kwargs['basetimestamp'] = kwargs.get('basetimestamp') or self.ts
            result = content(text)
            if isinstance(result, dict):
                content = result.get('text', '')
                kwargs['summary'] = kwargs.get('summary') or result.get('summary', '')
            elif isinstance(result, str):
                content = result
            else:
                return None
        kwargs['starttimestamp'] = kwargs.get('starttimestamp') or kwargs.get('basetimestamp') or cur_timestamp()
        kwargs['text'] = content
        kwargs['action'] = 'edit'
        kwargs['token'] = self.get_tokens('csrf')

        rst = self.api_post(kwargs)

        if rst.get('edit', {}).get('result') == 'Success':
            if 'nochange' in rst['edit']:
                self.set_status('nochange')
            else:
                self.set_status('')
        else:
            log('Error: Page not saved, see the following result.')
            log(json.dumps(rst, indent=4, sort_keys=True))
            if rst.get('edit', {}).get('captcha'):
                word = input('Input the captcha listed above: ')
                kwargs['captchaid'] = rst['edit']['captcha'].get('id')
                kwargs['captchaword'] = word
                self.ex_edit(**kwargs)
            elif rst.get('edit', {}).get('abusefilter', {}).get('id'):
                afid = rst['edit']['abusefilter']['id']
                self.set_status('abusefilter #%d' % afid)
                log('Hit abusefilter #%d!' % afid)
                if 'info' in rst['edit']:
                    log(rst['edit']['info'])
            elif 'error' not in rst:
                self.set_status(json.dumps(rst))

    @check_csrf
    def flow_new_topic(self, page, topic, content, check_title=False):
        if check_title:
            page = self.exact_title(page)

        rst = self.api_post({'action': 'flow', 'submodule': 'new-topic',
                             'page': page, 'nttopic': topic,
                             'ntcontent': content,
                             'token': self.get_tokens('csrf')})

        if 'flow' in rst and 'new-topic' in rst['flow'] and 'status' \
                in rst['flow']['new-topic'] and \
                rst['flow']['new-topic']['status'] == 'ok':
            self.set_flow_ids(page + topic,
                rst['flow']['new-topic']['committed']['topiclist']['topic-id'])
            self.set_status('')
            time.sleep(6)
        else:
            log('Error: New topic not created, see the following result.')
            log(json.dumps(rst, indent=4, sort_keys=True))
            if 'error' not in rst:
                self.set_status(json.dumps(rst))

    @check_csrf
    def flow_unlock_topic(self, page, reason):
        rst = self.api_post({'action': 'flow', 'page': page,
                             'submodule': 'lock-topic',
                             'cotmoderationState': 'unlock',
                             'cotreason': reason,
                             'token': self.get_tokens('csrf')})
        log(json.dumps(rst, indent=4, sort_keys=True))

    @check_csrf
    def flow_reply(self, page, id, content, retry=False):
        rst = self.api_post({'action': 'flow', 'page': page,
                             'submodule': 'reply', 'repreplyTo': id,
                             'repcontent': content,
                             'token': self.get_tokens('csrf')})

        if 'flow' in rst and 'reply' in rst['flow'] \
                and 'status' in rst['flow']['reply'] \
                and rst['flow']['reply']['status'] == 'ok':
            self.set_status('')
            time.sleep(6)
        else:
            if 'error' in rst and 'permissions' in rst['error']:
                if retry:
                    self.set_status('topic locked')
                else:
                    self.flow_unlock_topic(page, '机器人：发送新的通知')
                    self.flow_reply(page, id, content, retry=True)
            else:
                log('Error: reply not saved, see the following result.')
                log(json.dumps(rst, indent=4, sort_keys=True))
                if 'error' not in rst:
                    self.set_status(json.dumps(rst))

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


def main(pwd):
    pass


if __name__ == '__main__':
    main(__import__('password').getpass())
