# WhitePhosphorus-bot

[舊版本存檔](../../tree/archive)

## 你是誰？
我是運行在[中文維基百科](https://zh.wikipedia.org)上的機械人。

我的母語是 Python，中文講得不太好，請多包涵。

也可參見[我在維基百科上的用戶頁](https://zh.wikipedia.org/wiki/User:WhitePhosphorus-bot)。

## 最低版本要求
Python 3.4+

另見 [requirements.txt](requirements.txt)

## 當前的工作
* 定時給主人的討論頁存檔（[archive.py](src/archive.py)）
* 維護[圖片黑名單](https://zh.wikipedia.org/wiki/Mediawiki:Bad_image_list)（[badimage.py](src/badimage.py)）
* 清理 [CS1 無法識別的 |language= 參數](https://zh.wikipedia.org/wiki/Category:引文格式1维护：未识别语文类型)（[cs1language.py](src/cs1language.py)）
* 列出疑似草稿（[draft.py](src/draft.py)）
* 根據用戶需求清空頁面快取（[purge.py](src/purge.py)，开发中）
* 維護[最近變更條目請求列表](https://zh.wikipedia.org/wiki/Template:Recent_changes_article_requests/list)（[rcarl.py](src/rcarl.py)）
* 自動回報「[當前的破壞](https://zh.wikipedia.org/wiki/WP:VIP)」、「[頁面保護請求](https://zh.wikipedia.org/wiki/WP:RFPP)」中管理員的處理結果（[report.py](src/report.py)）

## 回報問題
根據[維基百科上的機器人方針](https://zh.wikipedia.org/wiki/Wikipedia:機械人方針#輕微的錯誤、投訴和改進建議)，您可以在[我主人的討論頁](https://zh.wikipedia.org/wiki/User_talk:WhitePhosphorus)回報問題，當然您也可以在這裡寫 issue。

## 授權協議
我的全部代碼使用 MIT 授權。
