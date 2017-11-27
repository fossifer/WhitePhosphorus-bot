# WhitePhosphorus-bot

[旧版本存档](../../tree/archive)

## 你是谁？
我是运行在[中文维基百科](https://zh.wikipedia.org)上的机器人。

我的母语是 Python，中文讲得不太好，请多包涵。

也可参见[我在维基百科上的用户页](https://zh.wikipedia.org/wiki/User:WhitePhosphorus-bot)。

## 最低版本要求
Python 3.4+

另见 [requirements.txt](requirements.txt)

## 当前的工作
* 定时给主人的讨论页存档（[archive.py](src/archive.py)）
* 维护[图片黑名单](https://zh.wikipedia.org/wiki/Mediawiki:Bad_image_list)（[badimage.py](src/badimage.py)）
* 清理 [CS1 无法识别的 |language= 参数](https://zh.wikipedia.org/wiki/Category:引文格式1维护：未识别语文类型)（[cs1language.py](src/cs1language.py)）
* 列出疑似废弃草稿（[draft.py](src/draft.py)）
* 根据用户需求清空页面缓存（[purge.py](src/purge.py)，开发中）
* 维护[最近更改条目请求列表](https://zh.wikipedia.org/wiki/Template:Recent_changes_article_requests/list)（[rcarl.py](src/rcarl.py)）
* 自动回报"[当前的破坏](https://zh.wikipedia.org/wiki/WP:VIP)"、"[页面保护请求](https://zh.wikipedia.org/wiki/WP:RFPP)"中管理员的处理结果（[report.py](src/report.py)）

## 回报问题
根据[维基百科上的机器人方针](https://zh.wikipedia.org/wiki/Wikipedia:機械人方針#輕微的錯誤、投訴和改進建議)，您可以在[我主人的用户页](https://zh.wikipedia.org/wiki/User_talk:WhitePhosphorus)回报问题。当然您也可以在这里写 issue。

## 授权协议
我的全部代码使用 MIT 授权。
