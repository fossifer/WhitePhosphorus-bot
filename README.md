# WhitePhosphorus-bot

[简体中文](README.zh-hans.md) - [繁體中文](README.zh-hant.md)

[Older versions archive](../tree/archive)

## Who am I?
I'm a bot running on [Chinese wikipedia](https://zh.wikipedia.org).

My native language is Python and I'm sorry that I cannot speak English fluently.

You can also refer to [my user page on Wikipedia](https://zh.wikipedia.org/wiki/User:WhitePhosphorus-bot).

## Requirements
Python 3.4+

See also [requirements.txt](requirements.txt).

## Current tasks
* Archive my owner's talk page ([archive.py](src/archive.py))
* Maintain [the bad image list](https://zh.wikipedia.org/wiki/Mediawiki:Bad_image_list) ([badimage.py](src/badimage.py))
* Clean up [unrecognized language codes in CS1 citations](https://zh.wikipedia.org/wiki/Category:引文格式1维护：未识别语文类型) ([cs1language.py](src/cs1language.py))
* List abandoned drafts ([draft.py](src/draft.py))
* Purge pages in user inputs ([purge.py](src/purge.py), under developing)
* Maintain [the recent changes article request list](https://zh.wikipedia.org/wiki/Template:Recent_changes_article_requests/list) ([rcarl.py](src/rcarl.py))
* Report the results of requests in [WP:VIP](https://zh.wikipedia.org/wiki/WP:VIP) and [WP:RFPP](https://zh.wikipedia.org/wiki/WP:RFPP) ([report.py](src/report.py))

## Reporting issues
According to [the bot policy on Chinese Wikipedia](https://zh.wikipedia.org/wiki/Wikipedia:機械人方針#輕微的錯誤、投訴和改進建議), you may report issues on [my owner's talk page](https://zh.wikipedia.org/wiki/User_talk:WhitePhosphorus). Of course, you can open issues here.

## License
All my codes are under MIT License.