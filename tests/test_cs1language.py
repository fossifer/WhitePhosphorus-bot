import unittest
from src import cs1language, botsite

title = 'User:WhitePhosphorus/磷原子4号/2009年薩揚-舒申斯克水力發電廠事故'


test_cases = {
    "{{cite web|language=russian}}": "{{cite web|language=ru}}",
    "{{ cites | {{ cite journal | language = 简体中文 }} }}": "{{ cites | {{ cite journal | language = zh-hans }} }}",
    "{{ cite journal\n| language = 汉语, Greek }} }}": "{{ cite journal\n| language = 汉语, Greek }} }}",
    "{{ infobox settlement | language = English | name = 东亚 {{ cite web | language = 中文（简体） }} }}":
        "{{ infobox settlement | language = English | name = 东亚 {{ cite web | language = zh-hans }} }}",
    "{{cite press release|title=t|language=English|c=d}}": "{{cite press release|title=t|language=en|c=d}}",
    "{{cite press release|title=t|language=English|c=d}": "{{cite press release|title=t|language=English|c=d}",
    "{{cite press release|title=t|language=English|c=d}test{{cite news|title=n|language=简体中文|a=b}}":
        "{{cite press release|title=t|language=English|c=d}test{{cite news|title=n|language=zh-hans|a=b}}",
}


class TestCS1LanguageReplace(unittest.TestCase):
    def test(self):
        for k, v in test_cases.items():
            self.assertEqual(cs1language.para_re.sub(cs1language.set_text, k), v)


def main(pwd):
    site = botsite.Site()
    site.client_login(pwd)
    text = site.get_text_by_title(title)
    new_text = cs1language.para_re.sub(cs1language.set_text, text)
    if new_text == text:
        print('No change')
    else:
        site.ex_edit(text=new_text, summary='机器人：清理[[Category:引文格式1维护：未识别语文类型]]',
                     title=title, minor=True, bot=True)


if __name__ == '__main__':
    unittest.main()