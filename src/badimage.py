# TODO: NO files in 'except on' list
# TODO: NO other prefixes such as Image, 图片, 档案, etc.
# TODO: NOT considering redirect pages of {{受限制文件}} when removing

import re
import sys
import botsite
from botsite import cur_timestamp

bad_re = re.compile(r'{{\s*(受限制文件' \
                    r'|[Rr]estricted use|[Bb]ad ?image)\s*}}')
file_re = re.compile(r'\[\[:?[Ff]ile:(?P<name>.*?)\]\]')
empty_re = re.compile(r'\s*')
site = botsite.Site()
bad_list = []


def init():
    global bad_list
    text = site.get_text_by_title('MediaWiki:Bad_image_list')
    bad_list = ['File:' + match.group('name').replace('_', ' ')
                for match in file_re.finditer(text)]


def check_image(title):
    r = site.api_get({'action': 'query', 'prop': 'imageinfo',
                      'titles': title, 'iiprop': 'badfile|sha1'}, 'query')
    img_dict = list(r.get('pages', {}).values())[0]
    return 'sha1' in img_dict.get('imageinfo', [{}])[0]


def add():
    for image in bad_list:
        if check_image(image):
            image_text = site.get_text_by_title(image)
            if bad_re.search(image_text):
                continue
            new_text = '\n{{受限制文件}}' if image_text else '{{受限制文件}}'
            site.edit(new_text,
                      '机器人：为[[MediaWiki:Bad image list]]中的文件添加' \
                      '{{[[Template:受限制文件|受限制文件]]}}', bot=True,
                      title=image, nocreate=False, append=True,
                      basets=site.ts, startts=site.ts)


def remove():
    for title in site.what_embeds_it(
            title='Template:受限制文件', ns='6', id=False):
        if title not in bad_list:
            t = ''
            new_text = bad_re.sub('', site.get_text_by_title(title))
            if not empty_re.sub('', new_text):
                new_text = '{{d|g1}}'
                t = '并提请快速删除（G1）'
                print(title)
            site.edit(new_text,
                      '机器人：[[%s]]不在[[MediaWiki:Bad image list]]中，移除' \
                      '{{[[Template:受限制文件|受限制文件]]}}%s' % (title, t),
                      bot=True, minor=True, title=title,
                      basets=site.ts, startts=site.ts, print_only=True)


if __name__ == '__main__':
    site.client_login(sys.argv[1])
    init()
    remove()
    add()
