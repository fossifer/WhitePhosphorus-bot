# TODO: NO files in 'except on' list
# TODO: NO other prefixes such as Image, 图片, 档案, etc.
# TODO: NOT considering redirect pages of {{受限制文件}} when removing

import re
from . import botsite
from .core import EditQueue, check
from .botsite import get_summary

bad_re = re.compile(r'{{\s*(受限制文件'
                    r'|[Rr]estricted use|[Bb]ad ?image)\s*}}')
file_re = re.compile(r'\[\[:?[Ff]ile:(?P<name>.*?)\]\]')
empty_re = re.compile(r'^\s*$')
bad_list = []


def init():
    global bad_list
    site = botsite.Site()
    text = site.get_text_by_title('MediaWiki:Bad_image_list')
    bad_list = ['File:' + match.group('name').replace('_', ' ')
                for match in file_re.finditer(text)]


def check_image(title):
    site = botsite.Site()
    r = site.api_get({'action': 'query', 'prop': 'imageinfo',
                      'titles': title, 'iiprop': 'badfile|sha1'}, 'query')
    img_dict = list(r.get('pages', {}).values())[0]
    return 'sha1' in img_dict.get('imageinfo', [{}])[0]


def add():
    site = botsite.Site()
    for image in bad_list:
        if check_image(image):
            image_text = site.get_text_by_title(image)
            if bad_re.search(image_text):
                continue
            new_text = '\n{{受限制文件}}' if image_text else '{{受限制文件}}'
            EditQueue().push(title=image, appendtext=new_text,
                             summary=get_summary('badimage', '为[[MediaWiki:Bad image list]]中的'
                                                             '文件添加{{[[T:受限制文件|受限制文件]]}}'),
                             bot=True, minor=True, task='badimage')


def remove():
    site = botsite.Site()
    for title in site.what_embeds_it(
            title='Template:受限制文件', ns='6', id=False):
        if title not in bad_list:
            t = ''
            new_text = bad_re.sub('', site.get_text_by_title(title))
            if empty_re.match(new_text):
                new_text = '{{d|g1|bot=%s}}' % botsite.bot_name
                t = '并提请快速删除（[[WP:CSD#G1|CSD G1]]）'
            EditQueue().push(title=title, text=new_text,
                             summary=get_summary('badimage', '[[%s]]不在'
                                                             '[[MediaWiki:Bad image list]]中，移除'
                                                             '{{[[T:受限制文件|受限制文件]]}}%s' % (title, t)),
                             bot=True, minor=True, task='badimage')


@check('badimage')
def main():
    init()
    remove()
    add()


if __name__ == '__main__':
    main()
