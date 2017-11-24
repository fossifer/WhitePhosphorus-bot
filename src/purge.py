import exception
from . import botsite
from .core import EditQueue, now, log


DEBUG = True


def strip_comments(line):
    try:
        sharp_index = line.index('#')
        return line[:sharp_index].strip()
    except ValueError:
        return line.strip()


def main(input_lines):
    # TODO: order changed
    site = botsite.Site()
    rst = dict()
    dump = []

    pagelist = input_lines.splitlines()
    try:
        index_a = pagelist.index('########## 清空以下页面的缓存 ##########')
        index_b = pagelist.index('########## 清空嵌入以下模板的页面的缓存 ##########')
        index_c = pagelist.index('########## 清空以下分类全部成员的缓存 ##########')
    except ValueError:
        # Wrong input format
        log('Invalid input')
        rst['success'] = False
        rst['result_msg'] = '输入格式错误，请检查'
        return rst

    if DEBUG:
        log('Input loaded, working...')

    def load_pages(index_a, index_b):
        pages = set()
        for i in range(index_a + 1, index_b):
            title = strip_comments(pagelist[i])
            if title:
                pages.add(title)
        return pages

    pages = load_pages(index_a, index_b)
    for rst in site.purge(forcelinkupdate=True, titles=list(pages)):
        log(rst)
        if 'invalid' in rst:
            dump.append('* 错误：未清空“{title}”的缓存：{reason}'.format(title=rst.get('title', ''),
                                                                  reason=rst.get('invalidreason', '')))
        elif 'missing' in rst:
            dump.append('* 错误：未清空[[:{title}]]的缓存：页面不存在'.format(title=rst.get('title', '')))
        elif 'purged' not in rst:
            dump.append('* 错误：未清空[[:{title}]]的缓存：{rst}'.format(title=rst.get('title', ''), rst=str(rst)))
        elif 'linkupdate' not in rst:
            dump.append('* 错误：[[:{title}]]缓存已清空但未更新链接表：{rst}'.format(
                title=rst.get('title', ''), rst=str(rst)))

    pages = load_pages(index_b, index_c)
    for title in pages:
        log('purging pages embedded in [[:%s]]' % title)
        purged = False
        try:
            for rst in site.purge(forcelinkupdate=True, generator='embeddedin', geititle=title):
                purged = True
                log(rst)
                if 'purged' not in rst:
                    dump.append('* 错误：[[:{title}]]嵌入了[[:{parent}]]，但未清空前者的缓存：{rst}'.format(
                        title=rst.get('title', ''), rst=str(rst), parent=title))
                elif 'linkupdate' not in rst:
                    dump.append('* 错误：[[:{title}]]嵌入了[[:{parent}]]，前者缓存已清空但未更新链接表：{rst}'.format(
                        title=rst.get('title', ''), rst=str(rst), parent=title))
            if not purged:
                dump.append('* 警告：未找到任何嵌入[[:{title}]]的页面，可能是模板未使用或输入有误'.format(title=title))
        except exception.Error as e:
            if e.message.get('code') == 'invalidtitle':
                log('invalid category name [[:%s]]' % title)
                dump.append('* 警告：已跳过名称不合法的页面“{title}”，请检查输入是否有误'.format(
                    title=title))
            log(e.message)

    pages = load_pages(index_c, len(pagelist)-1)
    for title in pages:
        log('purging pages in [[:%s]]' % title)
        purged = False
        try:
            for rst in site.purge(forcelinkupdate=True, forcerecursivelinkupdate=True,
                                  generator='embeddedin', geititle=title):
                purged = True
                log(rst)
                if 'purged' not in rst:
                    dump.append('* 错误：[[:{parent}]]分类中包含[[:{title}]]，但未清空后者的缓存：{rst}'.format(
                        title=rst.get('title', ''), rst=str(rst), parent=title))
                elif 'linkupdate' not in rst:
                    dump.append('* 错误：[[:{parent}]]分类中包含[[:{title}]]，后者缓存已清空但未更新链接表：{rst}'.format(
                                    title=rst.get('title', ''), rst=str(rst), parent=title))
            if not purged:
                dump.append('* 警告：未找到任何[[:{title}]]的分类成员，可能是分类为空或输入有误'.format(title=title))
        except exception.Error as e:
            if e.message.get('code') == 'invalidcategory':
                log('invalid category name [[:%s]]' % title)
                dump.append('* 警告：已跳过名称不合法的分类“{title}”，请确认标题以<code>Category:</code>开头'.format(
                    title=title))
            log(e.message)

    rst['dump'] = '\n'.join(dump)
    if dump:
        rst['message'] = '运行过程中出现了一些错误和警告，详情请见[[{dump}]]'
    rst['success'] = True
    return rst
