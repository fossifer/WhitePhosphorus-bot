import sys
import regex
from . import botsite
from .core import check, EditQueue
from .botsite import cur_timestamp, get_summary


# This module is called once an hour.
MAX_WORK_PER_HOUR = 50
LAST_SORT_KEY = None

tar_template = '[Cc]ite '
tar_para = 'language'
para_re = regex.compile(r'(?P<prefix>{{\s*%s(?:(?!{{|}}).)*?(?P<nest>{{(?:(?!{{).)*?(?&nest)?(?:(?!}}).)*?}})*'
                        '(?:(?!{{|}}).)*?\|\s*%s\s*=\s*)(?P<para>.*?)'
                        '(?P<suffix>\s*(\|\s*(?:(?!{{|}}).)*(?&nest)*(?:(?!{{|}}).)*?)?}})' %
                        (tar_template, tar_para), regex.DOTALL)

sub_dict = {
    r'中文\s*[（(](简体?|簡體?)[）)]|(简体|簡體)(中文|汉语|漢語)': 'zh-hans',
    r'中文\s*[（(][正繁][体體]?[）)]|[正繁][体體](中文|汉语|漢語)': 'zh-hant',
    r'(\[\[)?粵[语語](\]\])?': 'zh-yue',
    r'[汉漢][语語]|[Cc]hinese|[Cc][Nn]': 'zh',
    r'英[语語文]|[Ee]nglish': 'en',
    r'日本?[语語文]|[Jj]apanese|ja-JP': 'ja',
    r'法[语語文]|[Ff]rench|[Ff]rançais': 'fr',
    r'荷[兰蘭]?[语語文]|[Dd]utch|[Nn]ederlands': 'nl',
    r'德[语語文]|[Gg]ermany?|[Dd]eutsch': 'de',
    r'俄[语語文]|[Rr]ussian': 'ru',
    r'(韩|朝鲜?|韓國?)[语語文]|[Kk]orean': 'ko',
    r'[意義](大利)?[语語文]|[Ii]talian': 'it',
    r'希伯来[语文]|希伯來[語文]|[Hh]ebrew': 'he',
    r'塞尔维亚[语文]|塞爾維亞[語文]|[Ss]erbian': 'sr',
    r'立陶宛[语語文]|[Ll]ithuanian': 'lt',
    r'乌克兰[语文]|烏克蘭[語文]|[Uu]krainian': 'uk',
    r'土耳其[语語文]|[Tt]urkish': 'tr',
    r'西班牙[语語文]|[Ss]panish|español': 'es',
    r'拉丁[语語文]|[Ll]atin': 'la',
    r'捷克[语語文]|[Cc]zech': 'cs',
    r'保加利亚[语文]|保加利亞[語文]|[Bb]ulgarian': 'bg',
    r'越南[语語文]|[Vv]ietnamese': 'vi',
    r'波斯[语語文]|[Pp]ersian': 'fa',
    r'芬兰[语文]|芬蘭[語文]|[Ff]innish': 'fi',
    r'波兰[语文]|波蘭[語文]|[Pp]olish': 'pl',
    r'葡萄牙[语語文]|[Pp]ortuguese': 'pt',
    r'罗马尼亚语|羅馬尼亞語|[Rr]omanian': 'ro',
    r'瑞典[语語文]|[Ss]wedish': 'sv',
    r'维吾[尔儿][语語文]|[Uu]yghur': 'ug',
    r'傣[语文]|泰[語文]|[Tt]hai': 'th',
    r'希腊[语文]|希臘[語文]|[Gg]reek': 'el',
    r'丹麦[语文]|丹麥[語文]|[Dd]anish': 'da',
    r'爱沙尼亚[语文]|愛沙尼亞[語文]|[Ee]stonian': 'et',
    r'挪威[语語文]|[Nn]orwegian': 'no',
    r'拉脱维亚[语文]|拉脫維亞[語文]|[Ll]atvian': 'lv',
    r'斯洛文尼亚[语文]|斯洛维尼亚[語文]|[Ss]lovenian|[Ss]lovene': 'sl',
    r'匈牙利[语語文]|[Hh]ungarian': 'hu',
    r'阿尔巴尼亚[语文]|阿爾巴尼亞[語文]|[Aa]lbanian': 'sq',
    r'克罗地亚[语文]|克罗埃西亚[語文]|[Cc]roatian': 'hr',
    r'斯洛伐克[语語文]|[Ss]lovak': 'sk',
    r'冰岛[语文]|冰島[語文]|[Ii]celandic': 'is',
    r'波斯尼亚[语文]|波士尼亚[語文]|[Bb]osnian': 'bs',
    r'格鲁吉亚[语文]|喬治亞[語文]|[Gg]eorgian': 'ka',
    r'蒙古[语語文]|[Mm]ongolian': 'mn',
}


def set_text(match):
    dest = match.group('para')
    for (key, value) in sub_dict.items():
        dest = regex.sub(r'^(%s)$' % key, value, dest)
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
                         pageid=id, minor=True, bot=True, startts=cur_timestamp())
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
