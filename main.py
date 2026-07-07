import argparse
import os
import re
import urllib.parse
import requests
from loguru import logger
from apis.xhs_pc_apis import XHS_Apis
from apis.xhs_pc_login_apis import XHSLoginApi
from apis.xhs_creator_login_apis import XHSCreatorLoginApi
from xhs_utils.common_util import init
from xhs_utils.data_util import handle_note_info, download_note, save_to_xlsx, ocr_note_images
from xhs_utils.ocr_util import build_ocr_client_from_env
from xhs_utils.xhs_util import get_common_headers


def extract_first_url(raw_text: str):
    if not raw_text:
        return ""
    match = re.search(r'https?://[^\s]+', raw_text)
    if not match:
        return ""
    url = match.group(0).strip()
    return url.rstrip('，。；：！？、"\'”’）)')


def normalize_note_url(raw_input: str):
    """
    支持三类输入：
    1) 直接笔记URL
    2) xhslink短链
    3) 小红书分享文案（含短链）
    """
    url = extract_first_url(raw_input.strip())
    if not url:
        return ""
    if "xhslink.com" not in url:
        return url
    try:
        res = requests.get(
            url,
            allow_redirects=True,
            timeout=20,
            headers=get_common_headers(),
        )
        final_url = res.url
        logger.info(f"短链解析成功: {url} -> {final_url}")
        return final_url
    except Exception as e:
        logger.warning(f"短链解析失败，尝试使用原始短链: {url}, err: {e}")
        return url


class Data_Spider():
    def __init__(self):
        self.xhs_apis = XHS_Apis()

    def spider_note(self, note_url: str, cookies_str: str, proxies=None):
        """
        爬取一个笔记的信息
        :param note_url:
        :param cookies_str:
        :return:
        """
        note_info = None
        note_url = normalize_note_url(note_url)
        if not note_url:
            logger.error('输入内容中未识别到可用URL')
            return False, '输入内容中未识别到可用URL', None
        try:
            success, msg, note_info = self.xhs_apis.get_note_info(note_url, cookies_str, proxies)
            if success:
                note_info = note_info['data']['items'][0]
                note_info['url'] = note_url
                note_info = handle_note_info(note_info)
        except Exception as e:
            success = False
            msg = e
        logger.info(f'爬取笔记信息 {note_url}: {success}, msg: {msg}')
        return success, msg, note_info

    def spider_some_note(self, notes: list, cookies_str: str, base_path: dict, save_choice: str, excel_name: str = '', proxies=None):
        """
        爬取一些笔记的信息
        :param notes:
        :param cookies_str:
        :param base_path:
        :return:
        """
        if (save_choice == 'all' or save_choice == 'excel') and excel_name == '':
            raise ValueError('excel_name 不能为空')
        note_list = []
        for note_url in notes:
            success, msg, note_info = self.spider_note(note_url, cookies_str, proxies)
            if note_info is not None and success:
                note_list.append(note_info)
        for note_info in note_list:
            if save_choice == 'all' or 'media' in save_choice:
                download_note(note_info, base_path['media'], save_choice, True)
        if save_choice == 'all' or save_choice == 'excel':
            file_path = os.path.abspath(os.path.join(base_path['excel'], f'{excel_name}.xlsx'))
            save_to_xlsx(note_list, file_path)


    def spider_user_all_note(self, user_url: str, cookies_str: str, base_path: dict, save_choice: str, excel_name: str = '', proxies=None):
        """
        爬取一个用户的所有笔记
        :param user_url:
        :param cookies_str:
        :param base_path:
        :return:
        """
        note_list = []
        try:
            success, msg, all_note_info = self.xhs_apis.get_user_all_notes(user_url, cookies_str, proxies)
            if success:
                logger.info(f'用户 {user_url} 作品数量: {len(all_note_info)}')
                for simple_note_info in all_note_info:
                    note_url = f"https://www.xiaohongshu.com/explore/{simple_note_info['note_id']}?xsec_token={simple_note_info['xsec_token']}"
                    note_list.append(note_url)
            if save_choice == 'all' or save_choice == 'excel':
                excel_name = user_url.split('/')[-1].split('?')[0]
            self.spider_some_note(note_list, cookies_str, base_path, save_choice, excel_name, proxies)
        except Exception as e:
            success = False
            msg = e
        logger.info(f'爬取用户所有视频 {user_url}: {success}, msg: {msg}')
        return note_list, success, msg

    def spider_user_all_collect_note(self, user_url: str, cookies_str: str, base_path: dict, save_choice: str, excel_name: str = '', proxies=None, collect_num: int = 0):
        """
        爬取某用户「收藏-笔记」下的全部笔记（与 Web 收藏夹笔记列表一致，非按自定义专辑拆分）。
        需目标收藏对当前 Cookie 可见（例如本人或对方公开收藏）。
        :param collect_num: 最多爬取多少条；0 表示不限制。
        """
        note_list = []
        try:
            max_count = collect_num if collect_num and collect_num > 0 else None
            success, msg, all_note_info = self.xhs_apis.get_user_all_collect_note_info(
                user_url, cookies_str, proxies, max_count=max_count
            )
            if success:
                logger.info(f'用户收藏笔记 {user_url} 条数: {len(all_note_info)}（限制: {collect_num or "无"}）')
                for row in all_note_info:
                    note_id = row.get('note_id') or row.get('id') or ''
                    xsec_token = row.get('xsec_token') or ''
                    if not note_id:
                        continue
                    note_url = f'https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}'
                    note_list.append(note_url)
            if save_choice == 'all' or save_choice == 'excel':
                url_parse = urllib.parse.urlparse(user_url)
                excel_name = url_parse.path.rstrip('/').split('/')[-1].split('?')[0]
            self.spider_some_note(note_list, cookies_str, base_path, save_choice, excel_name, proxies)
        except Exception as e:
            success = False
            msg = e
        logger.info(f'爬取用户收藏笔记 {user_url}: {success}, msg: {msg}')
        return note_list, success, msg

    def spider_some_search_note(self, query: str, require_num: int, cookies_str: str, base_path: dict, save_choice: str, sort_type_choice=0, note_type=0, note_time=0, note_range=0, pos_distance=0, geo: dict = None,  excel_name: str = '', proxies=None):
        """
            指定数量搜索笔记，设置排序方式和笔记类型和笔记数量
            :param query 搜索的关键词
            :param require_num 搜索的数量
            :param cookies_str 你的cookies
            :param base_path 保存路径
            :param sort_type_choice 排序方式 0 综合排序, 1 最新, 2 最多点赞, 3 最多评论, 4 最多收藏
            :param note_type 笔记类型 0 不限, 1 视频笔记, 2 普通笔记
            :param note_time 笔记时间 0 不限, 1 一天内, 2 一周内天, 3 半年内
            :param note_range 笔记范围 0 不限, 1 已看过, 2 未看过, 3 已关注
            :param pos_distance 位置距离 0 不限, 1 同城, 2 附近 指定这个必须要指定 geo
            返回搜索的结果
        """
        note_list = []
        try:
            success, msg, notes = self.xhs_apis.search_some_note(query, require_num, cookies_str, sort_type_choice, note_type, note_time, note_range, pos_distance, geo, proxies)
            if success:
                notes = list(filter(lambda x: x['model_type'] == "note", notes))
                logger.info(f'搜索关键词 {query} 笔记数量: {len(notes)}')
                for note in notes:
                    note_url = f"https://www.xiaohongshu.com/explore/{note['id']}?xsec_token={note['xsec_token']}"
                    note_list.append(note_url)
            if save_choice == 'all' or save_choice == 'excel':
                excel_name = query
            self.spider_some_note(note_list, cookies_str, base_path, save_choice, excel_name, proxies)
        except Exception as e:
            success = False
            msg = e
        logger.info(f'搜索关键词 {query} 笔记: {success}, msg: {msg}')
        return note_list, success, msg

    def spider_single_note_auto_download(self, note_url: str, cookies_str: str, base_path: dict, proxies=None):
        """
        根据单条笔记 URL 自动识别图集/视频并下载对应媒体。
        """
        success, msg, note_info = self.spider_note(note_url, cookies_str, proxies)
        if not success or not note_info:
            logger.error(f'单条笔记下载失败: {note_url}, msg: {msg}')
            return None, success, msg
        save_path = download_note(note_info, base_path['media'], 'media', True)
        logger.info(f"下载完成，笔记类型: {note_info['note_type']}, 保存路径: {save_path}")
        return note_info, True, '成功'


def parse_args():
    parser = argparse.ArgumentParser(description='Spider_XHS 入口程序')
    parser.add_argument('--mode', type=str, default='', choices=[
        'single', 'list', 'user', 'search', 'collect', 'ocr',
        'login-pc-qrcode', 'login-pc-phone', 'login-creator-qrcode', 'login-creator-phone',
    ], help='运行模式: single/list/user/search/collect/ocr 或 login-pc-qrcode/login-pc-phone/login-creator-qrcode/login-creator-phone')
    parser.add_argument('--note-url', type=str, default='', help='单条小红书笔记 URL（single 模式可用）')
    parser.add_argument('--notes', type=str, default='', help='多个笔记 URL，逗号分隔（list 模式可用）')
    parser.add_argument('--user-url', type=str, default='', help='用户主页 URL（user/collect 模式；collect 可填带 ?tab=fav&subTab=note 的收藏页链接）')
    parser.add_argument('--query', type=str, default='', help='搜索关键词（search 模式可用）')
    parser.add_argument('--query-num', type=int, default=10, help='搜索数量（search 模式可用，默认10）')
    parser.add_argument('--collect-num', type=int, default=0, help='collect 模式最多爬取的收藏笔记条数，0 表示不限制')
    parser.add_argument('--save-choice', type=str, default='all', choices=['all', 'media', 'media-video', 'media-image', 'excel'], help='保存类型')
    parser.add_argument('--excel-name', type=str, default='test', help='excel 文件名（save_choice 为 all/excel 时需设置）')
    parser.add_argument('--note-dir', type=str, default='', help='已下载笔记目录（ocr 模式可用）')
    parser.add_argument('--ocr-overwrite', action='store_true', help='ocr 模式下覆盖已存在的 OCR 结果')
    parser.add_argument('--ocr-mode', type=str, default='async', choices=['sync', 'async'], help='OCR 模式')
    parser.add_argument('--ocr-poll-interval', type=int, default=5, help='OCR 轮询间隔秒（async 模式）')
    parser.add_argument('--ocr-timeout', type=int, default=300, help='OCR 超时秒数（async 模式）')
    parser.add_argument('--ocr-submit-retries', type=int, default=None, help='OCR 提交队列满时的重试次数（默认读取环境变量或 5）')
    parser.add_argument('--login-terminal', action='store_true', help='登录二维码在终端 ASCII 显示（默认弹窗图片）')
    return parser.parse_args()


def run_list_mode(data_spider, cookies_str, base_path, args):
    notes_input = args.notes.strip()
    if notes_input:
        notes = [item.strip() for item in notes_input.split(',') if item.strip()]
    else:
        notes = []
        print('请输入笔记 URL（输入空行结束）:')
        while True:
            note_url = input().strip()
            if not note_url:
                break
            notes.append(note_url)
    if not notes:
        logger.warning('未提供任何笔记 URL')
        return
    data_spider.spider_some_note(notes, cookies_str, base_path, args.save_choice, args.excel_name)


def run_user_mode(data_spider, cookies_str, base_path, args):
    user_url = args.user_url.strip() or input('请输入用户主页 URL: ').strip()
    if not user_url:
        logger.warning('未提供用户主页 URL')
        return
    data_spider.spider_user_all_note(user_url, cookies_str, base_path, args.save_choice)


def run_collect_mode(data_spider, cookies_str, base_path, args):
    user_url = args.user_url.strip() or input(
        '请输入用户收藏页或主页 URL（示例含收藏标签页）: '
    ).strip()
    if not user_url:
        logger.warning('未提供用户 URL')
        return
    collect_num = max(0, args.collect_num)
    if collect_num == 0 and not (args.mode or '').strip():
        raw = input('最多爬取多少条收藏笔记（直接回车表示不限制）: ').strip()
        if raw.isdigit():
            collect_num = int(raw)
        elif raw:
            logger.warning('输入非正整数，将按不限制处理')
    data_spider.spider_user_all_collect_note(
        user_url,
        cookies_str,
        base_path,
        args.save_choice,
        collect_num=collect_num,
    )


def run_search_mode(data_spider, cookies_str, base_path, args):
    query = args.query.strip() or input('请输入搜索关键词: ').strip()
    if not query:
        logger.warning('未提供搜索关键词')
        return
    sort_type_choice = 0
    note_type = 0
    note_time = 0
    note_range = 0
    pos_distance = 0
    data_spider.spider_some_search_note(query, args.query_num, cookies_str, base_path, args.save_choice, sort_type_choice, note_type, note_time, note_range, pos_distance, geo=None)


def run_single_mode(data_spider, cookies_str, base_path, args):
    note_url = args.note_url.strip() or input('请输入笔记 URL: ').strip()
    if not note_url:
        logger.warning('未提供笔记 URL')
        return
    data_spider.spider_single_note_auto_download(note_url, cookies_str, base_path)


def resolve_note_dir(note_dir: str, media_base_path: str):
    note_dir = note_dir.strip()
    if not note_dir:
        return ''
    candidates = []
    if os.path.isabs(note_dir):
        candidates.append(note_dir)
    else:
        candidates.append(os.path.abspath(note_dir))
        candidates.append(os.path.abspath(os.path.join(media_base_path, note_dir)))
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return candidates[0]


def run_ocr_mode(base_path, args):
    note_dir = args.note_dir.strip() or input('请输入已下载的笔记目录路径: ').strip()
    note_dir = resolve_note_dir(note_dir, base_path['media'])
    if not note_dir:
        logger.warning('未提供笔记目录')
        return
    ocr_client = build_ocr_client_from_env(
        args.ocr_mode,
        args.ocr_poll_interval,
        args.ocr_timeout,
        args.ocr_submit_retries,
        args.ocr_submit_retry_delay,
    )
    if not ocr_client:
        logger.error('OCR 客户端初始化失败，请检查 OCR_TOKEN。')
        return
    try:
        success_count, skip_count = ocr_note_images(note_dir, ocr_client, args.ocr_overwrite)
    except Exception as e:
        logger.error(f'OCR 处理失败: {e}')
        return
    logger.info(f'OCR 处理完成: 成功 {success_count} 个，跳过 {skip_count} 个，目录: {note_dir}')


def run_login_mode(mode, args):
    show_in_terminal = args.login_terminal
    if mode == 'login-pc-qrcode':
        cookies_str = XHSLoginApi().qrcode_login(show_in_terminal=show_in_terminal)
    elif mode == 'login-pc-phone':
        cookies_str = XHSLoginApi().phone_login()
    elif mode == 'login-creator-qrcode':
        cookies_str = XHSCreatorLoginApi().qrcode_login(show_in_terminal=show_in_terminal)
    elif mode == 'login-creator-phone':
        cookies_str = XHSCreatorLoginApi().phone_login()
    else:
        logger.error(f'未知登录模式: {mode}')
        return
    if not cookies_str:
        logger.error('登录失败，未获取到 Cookie')
        return
    logger.info('请将上方 Cookie 复制到 .env 的 COOKIES= 后重新运行采集任务。')


def choose_mode_interactive():
    mapping = {
        '1': 'single',
        '2': 'list',
        '3': 'user',
        '4': 'search',
        '5': 'collect',
        '6': 'ocr',
        '8': 'login-pc-qrcode',
        '9': 'login-pc-phone',
        '10': 'login-creator-qrcode',
        '11': 'login-creator-phone',
        '7': 'exit',
    }
    while True:
        print('\n请选择运行模式:')
        print('1. 单条笔记自动下载（自动识别图集/视频）')
        print('2. 批量笔记 URL 下载')
        print('3. 下载某个用户的全部笔记')
        print('4. 按关键词搜索并下载')
        print('5. 下载用户收藏夹中的全部笔记（Web「收藏-笔记」列表）')
        print('6. 对已下载笔记手动 OCR')
        print('8. PC 端扫码登录（获取 COOKIES）')
        print('9. PC 端手机验证码登录（获取 COOKIES）')
        print('10. 创作者平台扫码登录（获取 COOKIES）')
        print('11. 创作者平台手机验证码登录（获取 COOKIES）')
        print('7. 退出')
        select = input('输入选项 [1-11, 7=退出]: ').strip()
        if select in mapping:
            return mapping[select]
        print('输入无效，请重新输入。')

if __name__ == '__main__':
    """
        此文件为爬虫的入口文件，可以直接运行
        apis/xhs_pc_apis.py 为爬虫的api文件，包含小红书的全部数据接口，可以继续封装
        apis/xhs_creator_apis.py 为小红书创作者中心的api文件
        感谢star和follow
    """

    args = parse_args()

    cookies_str, base_path = init()
    """
        save_choice: all: 保存所有的信息, media: 保存视频和图片（media-video只下载视频, media-image只下载图片，media都下载）, excel: 保存到excel
        save_choice 为 excel 或者 all 时，excel_name 不能为空
    """

    mode = (args.mode or "").strip() or choose_mode_interactive()
    login_modes = {
        'login-pc-qrcode', 'login-pc-phone', 'login-creator-qrcode', 'login-creator-phone',
    }
    if mode in login_modes:
        run_login_mode(mode, args)
        raise SystemExit(0)

    if mode not in {"exit", "ocr"} and not (cookies_str or '').strip():
        logger.error(
            '未检测到环境变量 COOKIES。请在 test002 目录下的 .env 文件中配置 COOKIES=（从浏览器复制完整 Cookie）。'
        )
        raise SystemExit(1)

    data_spider = Data_Spider()

    if mode == 'single':
        run_single_mode(data_spider, cookies_str, base_path, args)
    elif mode == 'list':
        run_list_mode(data_spider, cookies_str, base_path, args)
    elif mode == 'user':
        run_user_mode(data_spider, cookies_str, base_path, args)
    elif mode == 'search':
        run_search_mode(data_spider, cookies_str, base_path, args)
    elif mode == 'collect':
        run_collect_mode(data_spider, cookies_str, base_path, args)
    elif mode == 'ocr':
        run_ocr_mode(base_path, args)
    elif mode == 'exit':
        logger.info('已退出程序。')
    else:
        logger.info('无效选项，程序结束。')
