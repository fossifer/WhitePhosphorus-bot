import sys
import regex
from . import botsite
from .core import check, EditQueue
from .botsite import cur_timestamp, get_summary


# This module is called once an hour.
MAX_WORK_PER_HOUR = 50
LAST_SORT_KEY = None

tar_template = '[Cc]ite |[Cc]itation'
tar_para = 'language'
para_re = regex.compile(r'(?P<prefix>{{\s*(%s)(?:(?!{{|}}).)*?(?P<nest>{{(?:(?!{{).)*?(?&nest)?(?:(?!}}).)*?}})*'
                        '(?:(?!{{|}}).)*?\|\s*(%s)\s*=\s*)(?P<para>.*?)'
                        '(?P<suffix>\s*(\|\s*(?:(?!{{|}}).)*(?&nest)*(?:(?!{{|}}).)*?)?}})' %
                        (tar_template, tar_para), regex.DOTALL)

sub_dict = {
    r'阿拉伯[语語文]|Arabic': 'ar',
    r'保加利亚[语文]|保加利亞[語文]|Bulgarian': 'bg',
    r'波斯尼亚[语文]|波士尼亚[語文]|Bosnian': 'bs',
    r'加泰罗尼亚[语文]|加泰羅尼亞[語文]|Catalan': 'ca',
    r'捷克[语語文]|Czech': 'cs',
    r'丹麦[语文]|丹麥[語文]|Danish': 'da',
    r'德[语語文]|Germany?|Deutsch|de-DE': 'de',
    r'希腊[语文]|希臘[語文]|Greek': 'el',
    r'英[语語文]|English|en-(UK|IN)|\[\[English language(\|English)?\]\]': 'en',
    r'西班牙[语語文]|Spanish|español|\[\[西班牙語(\|Spanish)?\]\]': 'es',
    r'爱沙尼亚[语文]|愛沙尼亞[語文]|Estonian': 'et',
    r'波斯[语語文]|Persian': 'fa',
    r'芬兰[语文]|芬蘭[語文]|Finnish': 'fi',
    r'法[语語文]|French|Français|fr-FR|\[\[French language(\|French)?\]\]|\{\{fr icon\}\}': 'fr',
    r'希伯来[语文]|希伯來[語文]|Hebrew': 'he',
    r'克罗地亚[语文]|克罗埃西亚[語文]|Croatian': 'hr',
    r'匈牙利[语語文]|Hungarian': 'hu',
    r'印度尼西亚[语文]|印度尼西亞[語文]|印尼[语語文]|Indonesian': 'id',
    r'冰岛[语文]|冰島[語文]|Icelandic': 'is',
    r'[意義](大利)?[语語文]|Italian|it-IT|\[\[義大利語(\|Italian)?\]\]': 'it',
    r'日本?[语語文]|Japanese|ja-JP': 'ja',
    r'格鲁吉亚[语文]|喬治亞[語文]|Georgian': 'ka',
    r'(韩|朝鲜?|韓國?)[语語文]|Korean|ko-KR': 'ko',
    r'拉丁[语語文]|Latin': 'la',
    r'立陶宛[语語文]|Lithuanian': 'lt',
    r'拉脱维亚[语文]|拉脫維亞[語文]|Latvian': 'lv',
    r'蒙古[语語文]|Mongolian': 'mn',
    r'马来[语文]|馬來[語文]|Malay': 'ms',
    r'[缅緬]甸[语語文]|Burmese': 'my',
    r'荷[兰蘭]?[语語文]|Dutch|Nederlands|nl-NL': 'nl',
    r'挪威[语語文]|Norwegian': 'no',
    r'波兰[语文]|波蘭[語文]|Polish': 'pl',
    r'葡萄牙[语語文]|Portuguese': 'pt',
    r'罗马尼亚语|羅馬尼亞語|Romanian': 'ro',
    r'俄[语語文]|Russian': 'ru',
    r'斯洛伐克[语語文]|Slovak': 'sk',
    r'斯洛文尼亚[语文]|斯洛维尼亚[語文]|Slovenian|Slovene': 'sl',
    r'阿尔巴尼亚[语文]|阿爾巴尼亞[語文]|Albanian': 'sq',
    r'塞尔维亚[语文]|塞爾維亞[語文]|Serbian': 'sr',
    r'瑞典[语語文]|Swedish': 'sv',
    r'傣[语文]|泰[語文]|Thai': 'th',
    r'土耳其[语語文]|Turkish': 'tr',
    r'维吾[尔儿][语語文]|Uyghur': 'ug',
    r'乌克兰[语文]|烏克蘭[語文]|Ukrainian': 'uk',
    r'乌兹别克[语文]|烏茲別克[語文]|Uzbek': 'uz',
    r'越南[语語文]|Vietnamese': 'vi',
    r'[汉漢][语語]|Chinese': 'zh',
    r'中文\s*[（(]?(简体?|簡體?)[）)]?|(简体|簡體)(中文|汉语|漢語)|zh-cmn-Hans': 'zh-hans',
    r'中文\s*[（(]?[正繁][体體]?[）)]?|[正繁][体體](中文|汉语|漢語)|zh-cmn-Hant': 'zh-hant',
    r'zh_CN|zh-Hans-CN': 'zh-CN',
    r'zh_TW|zh-Hant-TW': 'zh-TW',
    r'(\[\[)?粵[语語](\]\])?': 'zh-yue',
}


def set_text(match):
    dest = match.group('para')
    for (key, value) in sub_dict.items():
        dest = regex.sub(r'^(%s)$' % key, value, dest, flags=regex.IGNORECASE)
    return match.group('prefix') + dest + match.group('suffix')


@check('CS1lang')
def fix_lang():
    global LAST_SORT_KEY
    site = botsite.Site()
    count, leisure = 0, True
    for id, sortkey in site.cat_generator('5163898', get_sortkey=True, startsortkey=LAST_SORT_KEY):
        leisure = False
        EditQueue().push(text=lambda old_text: para_re.sub(set_text, old_text),
                         summary=get_summary('CS1lang', '清理[[CAT:引文格式1维护：未识别语文类型]]'),
                         pageid=id, minor=True, bot=True, starttimestamp=cur_timestamp())
        count += 1
        if count >= MAX_WORK_PER_HOUR:
            LAST_SORT_KEY = sortkey
            break
    else:
        LAST_SORT_KEY = None
    if leisure:
        LAST_SORT_KEY = None


if __name__ == '__main__':
    site = botsite.Site()
    site.client_login(sys.argv[1])
    fix_lang()
