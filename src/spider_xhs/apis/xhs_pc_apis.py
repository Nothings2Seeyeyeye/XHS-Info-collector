# encoding: utf-8
import json
import re
import time
import urllib
from spider_xhs.utils import network as requests
from spider_xhs.utils.xhs_util import (
    splice_str,
    generate_request_params,
    generate_search_id,
    generate_search_request_id,
    generate_x_rap_param,
    get_common_headers,
)
from spider_xhs.utils.rate_limit_util import sleep_before_pagination, sleep_before_request
from loguru import logger

"""
    获小红书的api
    :param cookies_str: 你的cookies
"""
class XHS_Apis():
    def __init__(self):
        self.base_url = "https://edith.xiaohongshu.com"
        self.max_network_retries = 3
        self.network_retry_delay = 1.5

    def _extract_first_url(self, text: str):
        if not text:
            return ""
        # 优先提取 xhslink，其次提取小红书网页链接
        patterns = [
            r"https?://(?:www\.)?xhslink\.com/[^\s]+",
            r"https?://(?:www\.)?xiaohongshu\.com/[^\s]+",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0).rstrip('，。,.!?！？"”\'')
        return text.strip()

    def _resolve_share_url(self, text: str, proxies: dict = None):
        candidate_url = self._extract_first_url(text)
        if "xhslink.com" not in candidate_url:
            return candidate_url
        try:
            response = requests.get(
                candidate_url,
                allow_redirects=True,
                timeout=15,
                proxies=proxies,
                headers=get_common_headers(),
            )
            return response.url
        except Exception:
            return candidate_url

    def _is_risk_response(self, status_code: int, response_text: str, res_json=None):
        risk_keywords = [
            "captcha", "verify", "risk", "forbidden",
            "访问过于频繁", "需要验证", "账号异常", "登录失效", "请先登录"
        ]
        if status_code in [401, 403, 429]:
            return True, f"触发风控或鉴权失败，状态码: {status_code}"
        text = (response_text or "").lower()
        if any(keyword in text for keyword in risk_keywords):
            return True, "返回内容疑似触发风控/验证码"
        if isinstance(res_json, dict):
            msg = str(res_json.get("msg", "")).lower()
            code = str(res_json.get("code", ""))
            if any(keyword in msg for keyword in risk_keywords):
                return True, f"接口提示风控: {res_json.get('msg', '')}"
            if code in {"-401", "401", "403"}:
                return True, f"接口返回鉴权失败 code={code}"
        return False, ""

    def _request_json(self, method: str, url: str, headers=None, cookies=None, data=None, proxies=None):
        sleep_before_request('api')
        last_error = None
        for attempt in range(1, self.max_network_retries + 1):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    cookies=cookies,
                    data=data,
                    proxies=proxies,
                    timeout=20,
                )
            except requests.RequestException as e:
                last_error = f"网络异常: {e}"
                if attempt < self.max_network_retries:
                    logger.warning(f"[网络重试 {attempt}/{self.max_network_retries}] {last_error}")
                    time.sleep(self.network_retry_delay)
                    continue
                raise RuntimeError(last_error)

            if response.status_code >= 500:
                last_error = f"服务端异常状态码: {response.status_code}"
                if attempt < self.max_network_retries:
                    logger.warning(f"[网络重试 {attempt}/{self.max_network_retries}] {last_error}")
                    time.sleep(self.network_retry_delay)
                    continue
                raise RuntimeError(last_error)

            res_json = None
            try:
                res_json = response.json()
            except ValueError:
                pass

            is_risk, risk_msg = self._is_risk_response(response.status_code, response.text, res_json)
            if is_risk:
                # 风控类错误不重试，防止硬刷
                raise RuntimeError(f"[风控停止重试] {risk_msg}")

            response.raise_for_status()
            if res_json is None:
                raise RuntimeError("接口未返回JSON数据")
            return res_json

        raise RuntimeError(last_error or "请求失败")

    def _pause_between_pages(self, label='page'):
        sleep_before_pagination(label)

    @staticmethod
    def _parse_url_query(url: str):
        """解析 URL 查询参数，避免手写 split 导致边界值报错。"""
        url_parse = urllib.parse.urlparse(url)
        return url_parse, dict(urllib.parse.parse_qsl(url_parse.query, keep_blank_values=True))

    def get_homefeed_all_channel(self, cookies_str: str, proxies: dict = None):
        """
            获取主页的所有频道
            返回主页的所有频道
        """
        res_json = None
        try:
            api = "/api/sns/web/v1/homefeed/category"
            headers, cookies, data = generate_request_params(cookies_str, api, '', 'GET')
            res_json = self._request_json('GET', self.base_url + api, headers=headers, cookies=cookies, proxies=proxies)
            success, msg = res_json.get("success", False), res_json.get("msg", "")
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_homefeed_recommend(self, category, cursor_score, refresh_type, note_index, cookies_str: str, proxies: dict = None):
        """
            获取主页推荐的笔记
            :param category: 你想要获取的频道
            :param cursor_score: 你想要获取的笔记的cursor
            :param refresh_type: 你想要获取的笔记的刷新类型
            :param note_index: 你想要获取的笔记的index
            :param cookies_str: 你的cookies
            返回主页推荐的笔记
        """
        res_json = None
        try:
            api = f"/api/sns/web/v1/homefeed"
            data = {
                "cursor_score": cursor_score,
                "num": 20,
                "refresh_type": refresh_type,
                "note_index": note_index,
                "unread_begin_note_id": "",
                "unread_end_note_id": "",
                "unread_note_count": 0,
                "category": category,
                "search_key": "",
                "need_num": 10,
                "image_formats": [
                    "jpg",
                    "webp",
                    "avif"
                ],
                "need_filter_image": False
            }
            headers, cookies, trans_data = generate_request_params(cookies_str, api, data, 'POST')
            res_json = self._request_json('POST', self.base_url + api, headers=headers, cookies=cookies, data=trans_data, proxies=proxies)
            success, msg = res_json.get("success", False), res_json.get("msg", "")
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_homefeed_recommend_by_num(self, category, require_num, cookies_str: str, proxies: dict = None):
        """
            根据数量获取主页推荐的笔记
            :param category: 你想要获取的频道
            :param require_num: 你想要获取的笔记的数量
            :param cookies_str: 你的cookies
            根据数量返回主页推荐的笔记
        """
        cursor_score, refresh_type, note_index = "", 1, 0
        note_list = []
        try:
            while True:
                success, msg, res_json = self.get_homefeed_recommend(category, cursor_score, refresh_type, note_index, cookies_str, proxies)
                if not success:
                    raise Exception(msg)
                if "items" not in res_json["data"]:
                    break
                notes = res_json["data"]["items"]
                note_list.extend(notes)
                cursor_score = res_json["data"]["cursor_score"]
                refresh_type = 3
                note_index += 20
                if len(note_list) > require_num:
                    break
                self._pause_between_pages('homefeed')
        except Exception as e:
            success = False
            msg = str(e)
        if len(note_list) > require_num:
            note_list = note_list[:require_num]
        return success, msg, note_list

    def get_user_info(self, user_id: str, cookies_str: str, proxies: dict = None):
        """
            获取用户的信息
            :param user_id: 你想要获取的用户的id
            :param cookies_str: 你的cookies
            返回用户的信息
        """
        res_json = None
        try:
            api = f"/api/sns/web/v1/user/otherinfo"
            params = {
                "target_user_id": user_id
            }
            splice_api = splice_str(api, params)
            headers, cookies, data = generate_request_params(cookies_str, splice_api, '', 'GET')
            res_json = self._request_json('GET', self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies)
            success, msg = res_json.get("success", False), res_json.get("msg", "")
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_user_self_info(self, cookies_str: str, proxies: dict = None):
        """
            获取用户自己的信息1
            :param cookies_str: 你的cookies
            返回用户自己的信息1
        """
        res_json = None
        try:
            api = f"/api/sns/web/v1/user/selfinfo"
            headers, cookies, data = generate_request_params(cookies_str, api, '', 'GET')
            res_json = self._request_json('GET', self.base_url + api, headers=headers, cookies=cookies, proxies=proxies)
            success, msg = res_json.get("success", False), res_json.get("msg", "")
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json


    def get_user_self_info2(self, cookies_str: str, proxies: dict = None):
        """
            获取用户自己的信息2
            :param cookies_str: 你的cookies
            返回用户自己的信息2
        """
        res_json = None
        try:
            api = f"/api/sns/web/v2/user/me"
            headers, cookies, data = generate_request_params(cookies_str, api, '', 'GET')
            res_json = self._request_json('GET', self.base_url + api, headers=headers, cookies=cookies, proxies=proxies)
            success, msg = res_json.get("success", False), res_json.get("msg", "")
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_user_note_info(self, user_id: str, cursor: str, cookies_str: str, xsec_token='', xsec_source='', proxies: dict = None):
        """
            获取用户指定位置的笔记
            :param user_id: 你想要获取的用户的id
            :param cursor: 你想要获取的笔记的cursor
            :param cookies_str: 你的cookies
            返回用户指定位置的笔记
        """
        res_json = None
        try:
            api = f"/api/sns/web/v1/user_posted"
            params = {
                "num": "30",
                "cursor": cursor,
                "user_id": user_id,
                "image_formats": "jpg,webp,avif",
                "xsec_token": xsec_token,
                "xsec_source": xsec_source,
            }
            splice_api = splice_str(api, params)
            headers, cookies, data = generate_request_params(cookies_str, splice_api, '', 'GET')
            res_json = self._request_json('GET', self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies)
            success, msg = res_json.get("success", False), res_json.get("msg", "")
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json


    def get_user_all_notes(self, user_url: str, cookies_str: str, proxies: dict = None):
        """
           获取用户所有笔记
           :param user_id: 你想要获取的用户的id
           :param cookies_str: 你的cookies
           返回用户的所有笔记
        """
        cursor = ''
        note_list = []
        try:
            urlParse, kvDist = self._parse_url_query(user_url)
            user_id = urlParse.path.split("/")[-1]
            xsec_token = kvDist['xsec_token'] if 'xsec_token' in kvDist else ""
            xsec_source = kvDist['xsec_source'] if 'xsec_source' in kvDist else "pc_search"
            while True:
                success, msg, res_json = self.get_user_note_info(user_id, cursor, cookies_str, xsec_token, xsec_source, proxies)
                if not success:
                    raise Exception(msg)
                notes = res_json["data"]["notes"]
                if 'cursor' in res_json["data"]:
                    cursor = str(res_json["data"]["cursor"])
                else:
                    break
                note_list.extend(notes)
                if len(notes) == 0 or not res_json["data"]["has_more"]:
                    break
                self._pause_between_pages('user_notes')
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, note_list

    def get_user_like_note_info(self, user_id: str, cursor: str, cookies_str: str, xsec_token='', xsec_source='', proxies: dict = None):
        """
            获取用户指定位置喜欢的笔记
            :param user_id: 你想要获取的用户的id
            :param cursor: 你想要获取的笔记的cursor
            :param cookies_str: 你的cookies
            返回用户指定位置喜欢的笔记
        """
        res_json = None
        try:
            api = f"/api/sns/web/v1/note/like/page"
            params = {
                "num": "30",
                "cursor": cursor,
                "user_id": user_id,
                "image_formats": "jpg,webp,avif",
                "xsec_token": xsec_token,
                "xsec_source": xsec_source,
            }
            splice_api = splice_str(api, params)
            headers, cookies, data = generate_request_params(cookies_str, splice_api, '', 'GET')
            res_json = self._request_json('GET', self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies)
            success, msg = res_json.get("success", False), res_json.get("msg", "")
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_user_all_like_note_info(self, user_url: str, cookies_str: str, proxies: dict = None):
        """
            获取用户所有喜欢笔记
            :param user_id: 你想要获取的用户的id
            :param cookies_str: 你的cookies
            返回用户的所有喜欢笔记
        """
        cursor = ''
        note_list = []
        try:
            urlParse, kvDist = self._parse_url_query(user_url)
            user_id = urlParse.path.split("/")[-1]
            xsec_token = kvDist['xsec_token'] if 'xsec_token' in kvDist else ""
            xsec_source = kvDist['xsec_source'] if 'xsec_source' in kvDist else "pc_user"
            while True:
                success, msg, res_json = self.get_user_like_note_info(user_id, cursor, cookies_str, xsec_token,
                                                                      xsec_source, proxies)
                if not success:
                    raise Exception(msg)
                notes = res_json["data"]["notes"]
                if 'cursor' in res_json["data"]:
                    cursor = str(res_json["data"]["cursor"])
                else:
                    break
                note_list.extend(notes)
                if len(notes) == 0 or not res_json["data"]["has_more"]:
                    break
                self._pause_between_pages('user_notes')
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, note_list

    def get_user_collect_note_info(self, user_id: str, cursor: str, cookies_str: str, xsec_token='', xsec_source='', proxies: dict = None):
        """
            获取用户指定位置收藏的笔记
            :param user_id: 你想要获取的用户的id
            :param cursor: 你想要获取的笔记的cursor
            :param cookies_str: 你的cookies
            返回用户指定位置收藏的笔记
        """
        res_json = None
        try:
            api = f"/api/sns/web/v2/note/collect/page"
            params = {
                "num": "30",
                "cursor": cursor,
                "user_id": user_id,
                "image_formats": "jpg,webp,avif",
                "xsec_token": xsec_token,
                "xsec_source": xsec_source,
            }
            splice_api = splice_str(api, params)
            headers, cookies, data = generate_request_params(cookies_str, splice_api, '', 'GET')
            res_json = self._request_json('GET', self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies)
            success, msg = res_json.get("success", False), res_json.get("msg", "")
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_user_all_collect_note_info(self, user_url: str, cookies_str: str, proxies: dict = None, max_count: int = None):
        """
            获取用户收藏夹中的笔记列表（Web「收藏-笔记」流，对应 /api/sns/web/v2/note/collect/page 分页）。
            支持主页带 tab=fav&subTab=note 等查询串；user_id 取自路径最后一段。
            :param user_url: 用户主页或收藏页 URL，如 https://www.xiaohongshu.com/user/profile/{user_id}?tab=fav&subTab=note
            :param cookies_str: 你的cookies
            :param max_count: 最多返回多少条简项；None 或 <=0 表示不限制（会翻页直到接口无更多）
            返回用户的所有收藏笔记（简项列表，含 note_id、xsec_token 等）
        """
        cursor = ''
        note_list = []
        limit = max_count if (max_count is not None and max_count > 0) else None
        try:
            urlParse = urllib.parse.urlparse(user_url)
            user_id = urlParse.path.rstrip('/').split('/')[-1]
            kvDist = dict(urllib.parse.parse_qsl(urlParse.query, keep_blank_values=True))
            xsec_token = kvDist.get('xsec_token') or ''
            xsec_source = kvDist.get('xsec_source') or 'pc_user'
            while True:
                success, msg, res_json = self.get_user_collect_note_info(user_id, cursor, cookies_str, xsec_token,
                                                                         xsec_source, proxies)
                if not success:
                    raise Exception(msg)
                notes = res_json["data"]["notes"]
                if 'cursor' in res_json["data"]:
                    cursor = str(res_json["data"]["cursor"])
                else:
                    break
                note_list.extend(notes)
                if limit is not None and len(note_list) >= limit:
                    del note_list[limit:]
                    break
                if len(notes) == 0 or not res_json["data"]["has_more"]:
                    break
                self._pause_between_pages('user_collect')
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, note_list

    def get_note_info(self, url: str, cookies_str: str, proxies: dict = None):
        """
            获取笔记的详细
            :param url: 你想要获取的笔记的url
            :param cookies_str: 你的cookies
            :param xsec_source: 你的xsec_source 默认为pc_search pc_user pc_feed
            返回笔记的详细
        """
        res_json = None
        try:
            final_url = self._resolve_share_url(url, proxies)
            urlParse = urllib.parse.urlparse(final_url)
            note_id = urlParse.path.split("/")[-1]
            kvDist = dict(urllib.parse.parse_qsl(urlParse.query))
            if 'xsec_token' not in kvDist:
                raise ValueError("链接中缺少 xsec_token，请先在浏览器打开分享链接并复制跳转后的完整笔记链接")
            api = f"/api/sns/web/v1/feed"
            data = {
                "source_note_id": note_id,
                "image_formats": [
                    "jpg",
                    "webp",
                    "avif"
                ],
                "extra": {
                    "need_body_topic": "1"
                },
                "xsec_source": kvDist.get('xsec_source', "pc_search"),
                "xsec_token": kvDist['xsec_token']
            }
            headers, cookies, data = generate_request_params(cookies_str, api, data, 'POST')
            headers["x-rap-param"] = generate_x_rap_param(api, data)
            headers["xy-direction"] = "13"
            res_json = self._request_json('POST', self.base_url + api, headers=headers, cookies=cookies, data=data, proxies=proxies)
            success, msg = res_json.get("success", False), res_json.get("msg", "")
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json


    def get_search_keyword(self, word: str, cookies_str: str, proxies: dict = None):
        """
            获取搜索关键词
            :param word: 你的关键词
            :param cookies_str: 你的cookies
            返回搜索关键词
        """
        res_json = None
        try:
            api = "/api/sns/web/v1/search/recommend"
            params = {
                "keyword": urllib.parse.quote(word)
            }
            splice_api = splice_str(api, params)
            headers, cookies, data = generate_request_params(cookies_str, splice_api, '', 'GET')
            res_json = self._request_json('GET', self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies)
            success, msg = res_json.get("success", False), res_json.get("msg", "")
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def search_note(self, query: str, cookies_str: str, page=1, sort_type_choice=0, note_type=0, note_time=0, note_range=0, pos_distance=0, geo="", search_id=None, proxies: dict = None):
        """
            获取搜索笔记的结果
            :param query 搜索的关键词
            :param cookies_str 你的cookies
            :param page 搜索的页数
            :param sort_type_choice 排序方式 0 综合排序, 1 最新, 2 最多点赞, 3 最多评论, 4 最多收藏
            :param note_type 笔记类型 0 不限, 1 视频笔记, 2 普通笔记
            :param note_time 笔记时间 0 不限, 1 一天内, 2 一周内天, 3 半年内
            :param note_range 笔记范围 0 不限, 1 已看过, 2 未看过, 3 已关注
            :param pos_distance 位置距离 0 不限, 1 同城, 2 附近 指定这个必须要指定 geo
            返回搜索的结果
        """
        res_json = None
        sort_type = "general"
        if sort_type_choice == 1:
            sort_type = "time_descending"
        elif sort_type_choice == 2:
            sort_type = "popularity_descending"
        elif sort_type_choice == 3:
            sort_type = "comment_descending"
        elif sort_type_choice == 4:
            sort_type = "collect_descending"
        filter_note_type = "不限"
        if note_type == 1:
            filter_note_type = "视频笔记"
        elif note_type == 2:
            filter_note_type = "普通笔记"
        filter_note_time = "不限"
        if note_time == 1:
            filter_note_time = "一天内"
        elif note_time == 2:
            filter_note_time = "一周内"
        elif note_time == 3:
            filter_note_time = "半年内"
        filter_note_range = "不限"
        if note_range == 1:
            filter_note_range = "已看过"
        elif note_range == 2:
            filter_note_range = "未看过"
        elif note_range == 3:
            filter_note_range = "已关注"
        filter_pos_distance = "不限"
        if pos_distance == 1:
            filter_pos_distance = "同城"
        elif pos_distance == 2:
            filter_pos_distance = "附近"
        if geo:
            geo = json.dumps(geo, separators=(',', ':'))
        try:
            api = "/api/sns/web/v1/search/notes"
            data = {
                "keyword": query,
                "page": page,
                "page_size": 20,
                "search_id": search_id or generate_search_id(),
                "sort": "general",
                "note_type": 0,
                "ext_flags": [],
                "filters": [
                    {
                        "tags": [
                            sort_type
                        ],
                        "type": "sort_type"
                    },
                    {
                        "tags": [
                            filter_note_type
                        ],
                        "type": "filter_note_type"
                    },
                    {
                        "tags": [
                            filter_note_time
                        ],
                        "type": "filter_note_time"
                    },
                    {
                        "tags": [
                            filter_note_range
                        ],
                        "type": "filter_note_range"
                    },
                    {
                        "tags": [
                            filter_pos_distance
                        ],
                        "type": "filter_pos_distance"
                    }
                ],
                "geo": geo,
                "image_formats": [
                    "jpg",
                    "webp",
                    "avif"
                ]
            }
            headers, cookies, data = generate_request_params(cookies_str, api, data, 'POST')
            headers["x-rap-param"] = generate_x_rap_param(api, data)
            res_json = self._request_json('POST', self.base_url + api, headers=headers, cookies=cookies, data=data.encode('utf-8'), proxies=proxies)
            success, msg = res_json.get("success", False), res_json.get("msg", "")
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def search_some_note(self, query: str, require_num: int, cookies_str: str, sort_type_choice=0, note_type=0, note_time=0, note_range=0, pos_distance=0, geo="", proxies: dict = None):
        """
            指定数量搜索笔记，设置排序方式和笔记类型和笔记数量
            :param query 搜索的关键词
            :param require_num 搜索的数量
            :param cookies_str 你的cookies
            :param sort_type_choice 排序方式 0 综合排序, 1 最新, 2 最多点赞, 3 最多评论, 4 最多收藏
            :param note_type 笔记类型 0 不限, 1 视频笔记, 2 普通笔记
            :param note_time 笔记时间 0 不限, 1 一天内, 2 一周内天, 3 半年内
            :param note_range 笔记范围 0 不限, 1 已看过, 2 未看过, 3 已关注
            :param pos_distance 位置距离 0 不限, 1 同城, 2 附近 指定这个必须要指定 geo
            :param geo: 定位信息 经纬度
            返回搜索的结果
        """
        page = 1
        note_list = []
        root_search_id = generate_search_id()
        try:
            while True:
                search_id = generate_search_id(root_search_id)
                success, msg, res_json = self.search_note(
                    query, cookies_str, page, sort_type_choice, note_type, note_time,
                    note_range, pos_distance, geo, search_id, proxies
                )
                if not success:
                    raise Exception(msg)
                if "items" not in res_json["data"]:
                    break
                notes = res_json["data"]["items"]
                note_list.extend(notes)
                page += 1
                if len(note_list) >= require_num or not res_json["data"]["has_more"]:
                    break
                self._pause_between_pages('search_notes')
        except Exception as e:
            success = False
            msg = str(e)
        if len(note_list) > require_num:
            note_list = note_list[:require_num]
        return success, msg, note_list

    def search_user(self, query: str, cookies_str: str, page=1, proxies: dict = None):
        """
            获取搜索用户的结果
            :param query 搜索的关键词
            :param cookies_str 你的cookies
            :param page 搜索的页数
            返回搜索的结果
        """
        res_json = None
        try:
            api = "/api/sns/web/v1/search/usersearch"
            data = {
                "search_user_request": {
                    "keyword": query,
                    "search_id": generate_search_id(),
                    "page": page,
                    "page_size": 15,
                    "biz_type": "web_search_user",
                    "request_id": generate_search_request_id()
                }
            }
            headers, cookies, data = generate_request_params(cookies_str, api, data, 'POST')
            res_json = self._request_json('POST', self.base_url + api, headers=headers, cookies=cookies, data=data.encode('utf-8'), proxies=proxies)
            success, msg = res_json.get("success", False), res_json.get("msg", "")
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def search_some_user(self, query: str, require_num: int, cookies_str: str, proxies: dict = None):
        """
            指定数量搜索用户
            :param query 搜索的关键词
            :param require_num 搜索的数量
            :param cookies_str 你的cookies
            返回搜索的结果
        """
        page = 1
        user_list = []
        try:
            while True:
                success, msg, res_json = self.search_user(query, cookies_str, page, proxies)
                if not success:
                    raise Exception(msg)
                if "users" not in res_json["data"]:
                    break
                users = res_json["data"]["users"]
                user_list.extend(users)
                page += 1
                if len(user_list) >= require_num or not res_json["data"]["has_more"]:
                    break
                self._pause_between_pages('search_users')
        except Exception as e:
            success = False
            msg = str(e)
        if len(user_list) > require_num:
            user_list = user_list[:require_num]
        return success, msg, user_list

    def get_note_out_comment(self, note_id: str, cursor: str, xsec_token: str, cookies_str: str, proxies: dict = None):
        """
            获取指定位置的笔记一级评论
            :param note_id 笔记的id
            :param cursor 指定位置的评论的cursor
            :param cookies_str 你的cookies
            返回指定位置的笔记一级评论
        """
        res_json = None
        try:
            api = "/api/sns/web/v2/comment/page"
            params = {
                "note_id": note_id,
                "cursor": cursor,
                "top_comment_id": "",
                "image_formats": "jpg,webp,avif",
                "xsec_token": xsec_token
            }
            splice_api = splice_str(api, params)
            headers, cookies, data = generate_request_params(cookies_str, splice_api, '', 'GET')
            res_json = self._request_json('GET', self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies)
            success, msg = res_json.get("success", False), res_json.get("msg", "")
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_note_all_out_comment(self, note_id: str, xsec_token: str, cookies_str: str, proxies: dict = None):
        """
            获取笔记的全部一级评论
            :param note_id 笔记的id
            :param cookies_str 你的cookies
            返回笔记的全部一级评论
        """
        cursor = ''
        note_out_comment_list = []
        try:
            while True:
                success, msg, res_json = self.get_note_out_comment(note_id, cursor, xsec_token, cookies_str, proxies)
                if not success:
                    raise Exception(msg)
                comments = res_json["data"]["comments"]
                if 'cursor' in res_json["data"]:
                    cursor = str(res_json["data"]["cursor"])
                else:
                    break
                note_out_comment_list.extend(comments)
                if len(note_out_comment_list) == 0 or not res_json["data"]["has_more"]:
                    break
                self._pause_between_pages('comments')
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, note_out_comment_list

    def get_note_inner_comment(self, comment: dict, cursor: str, xsec_token: str, cookies_str: str, proxies: dict = None):
        """
            获取指定位置的笔记二级评论
            :param comment 笔记的一级评论
            :param cursor 指定位置的评论的cursor
            :param cookies_str 你的cookies
            返回指定位置的笔记二级评论
        """
        res_json = None
        try:
            api = "/api/sns/web/v2/comment/sub/page"
            params = {
                "note_id": comment['note_id'],
                "root_comment_id": comment['id'],
                "num": "10",
                "cursor": cursor,
                "image_formats": "jpg,webp,avif",
                "top_comment_id": '',
                "xsec_token": xsec_token
            }
            splice_api = splice_str(api, params)
            headers, cookies, data = generate_request_params(cookies_str, splice_api, '', 'GET')
            res_json = self._request_json('GET', self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies)
            success, msg = res_json.get("success", False), res_json.get("msg", "")
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_note_all_inner_comment(self, comment: dict, xsec_token: str, cookies_str: str, proxies: dict = None):
        """
            获取笔记的全部二级评论
            :param comment 笔记的一级评论
            :param cookies_str 你的cookies
            返回笔记的全部二级评论
        """
        try:
            if not comment['sub_comment_has_more']:
                return True, 'success', comment
            cursor = comment['sub_comment_cursor']
            inner_comment_list = []
            while True:
                success, msg, res_json = self.get_note_inner_comment(comment, cursor, xsec_token, cookies_str, proxies)
                if not success:
                    raise Exception(msg)
                comments = res_json["data"]["comments"]
                if 'cursor' in res_json["data"]:
                    cursor = str(res_json["data"]["cursor"])
                else:
                    break
                inner_comment_list.extend(comments)
                if not res_json["data"]["has_more"]:
                    break
                self._pause_between_pages('sub_comments')
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, comment

    def get_note_all_comment(self, url: str, cookies_str: str, proxies: dict = None):
        """
            获取一篇文章的所有评论
            :param note_id: 你想要获取的笔记的id
            :param cookies_str: 你的cookies
            返回一篇文章的所有评论
        """
        out_comment_list = []
        try:
            urlParse, kvDist = self._parse_url_query(url)
            note_id = urlParse.path.split("/")[-1]
            success, msg, out_comment_list = self.get_note_all_out_comment(note_id, kvDist['xsec_token'], cookies_str, proxies)
            if not success:
                raise Exception(msg)
            for comment in out_comment_list:
                success, msg, _ = self.get_note_all_inner_comment(comment, kvDist['xsec_token'], cookies_str, proxies)
                if not success:
                    raise Exception(msg)
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, out_comment_list

    def get_unread_message(self, cookies_str: str, proxies: dict = None):
        """
            获取未读消息
            :param cookies_str: 你的cookies
            返回未读消息
        """
        res_json = None
        try:
            api = "/api/sns/web/unread_count"
            headers, cookies, data = generate_request_params(cookies_str, api, '', 'GET')
            res_json = self._request_json('GET', self.base_url + api, headers=headers, cookies=cookies, proxies=proxies)
            success, msg = res_json.get("success", False), res_json.get("msg", "")
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_metions(self, cursor: str, cookies_str: str, proxies: dict = None):
        """
            获取评论和@提醒
            :param cursor: 你想要获取的评论和@提醒的cursor
            :param cookies_str: 你的cookies
            返回评论和@提醒
        """
        res_json = None
        try:
            api = "/api/sns/web/v1/you/mentions"
            params = {
                "num": "20",
                "cursor": cursor
            }
            splice_api = splice_str(api, params)
            headers, cookies, data = generate_request_params(cookies_str, splice_api, '', 'GET')
            res_json = self._request_json('GET', self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies)
            success, msg = res_json.get("success", False), res_json.get("msg", "")
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_all_metions(self, cookies_str: str, proxies: dict = None):
        """
            获取全部的评论和@提醒
            :param cookies_str: 你的cookies
            返回全部的评论和@提醒
        """
        cursor = ''
        metions_list = []
        try:
            while True:
                success, msg, res_json = self.get_metions(cursor, cookies_str, proxies)
                if not success:
                    raise Exception(msg)
                metions = res_json["data"]["message_list"]
                if 'cursor' in res_json["data"]:
                    cursor = str(res_json["data"]["cursor"])
                else:
                    break
                metions_list.extend(metions)
                if not res_json["data"]["has_more"]:
                    break
                self._pause_between_pages('mentions')
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, metions_list

    def get_likesAndcollects(self, cursor: str, cookies_str: str, proxies: dict = None):
        """
            获取赞和收藏
            :param cursor: 你想要获取的赞和收藏的cursor
            :param cookies_str: 你的cookies
            返回赞和收藏
        """
        res_json = None
        try:
            api = "/api/sns/web/v1/you/likes"
            params = {
                "num": "20",
                "cursor": cursor
            }
            splice_api = splice_str(api, params)
            headers, cookies, data = generate_request_params(cookies_str, splice_api, '', 'GET')
            res_json = self._request_json('GET', self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies)
            success, msg = res_json.get("success", False), res_json.get("msg", "")
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_all_likesAndcollects(self, cookies_str: str, proxies: dict = None):
        """
            获取全部的赞和收藏
            :param cookies_str: 你的cookies
            返回全部的赞和收藏
        """
        cursor = ''
        likesAndcollects_list = []
        try:
            while True:
                success, msg, res_json = self.get_likesAndcollects(cursor, cookies_str, proxies)
                if not success:
                    raise Exception(msg)
                likesAndcollects = res_json["data"]["message_list"]
                if 'cursor' in res_json["data"]:
                    cursor = str(res_json["data"]["cursor"])
                else:
                    break
                likesAndcollects_list.extend(likesAndcollects)
                if not res_json["data"]["has_more"]:
                    break
                self._pause_between_pages('likes_collects')
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, likesAndcollects_list

    def get_new_connections(self, cursor: str, cookies_str: str, proxies: dict = None):
        """
            获取新增关注
            :param cursor: 你想要获取的新增关注的cursor
            :param cookies_str: 你的cookies
            返回新增关注
        """
        res_json = None
        try:
            api = "/api/sns/web/v1/you/connections"
            params = {
                "num": "20",
                "cursor": cursor
            }
            splice_api = splice_str(api, params)
            headers, cookies, data = generate_request_params(cookies_str, splice_api, '', 'GET')
            res_json = self._request_json('GET', self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies)
            success, msg = res_json.get("success", False), res_json.get("msg", "")
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_all_new_connections(self, cookies_str: str, proxies: dict = None):
        """
            获取全部的新增关注
            :param cookies_str: 你的cookies
            返回全部的新增关注
        """
        cursor = ''
        connections_list = []
        try:
            while True:
                success, msg, res_json = self.get_new_connections(cursor, cookies_str, proxies)
                if not success:
                    raise Exception(msg)
                connections = res_json["data"]["message_list"]
                if 'cursor' in res_json["data"]:
                    cursor = str(res_json["data"]["cursor"])
                else:
                    break
                connections_list.extend(connections)
                if not res_json["data"]["has_more"]:
                    break
                self._pause_between_pages('connections')
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, connections_list

    @staticmethod
    def get_note_no_water_video(note_id):
        """
            获取笔记无水印视频
            :param note_id: 你想要获取的笔记的id
            返回笔记无水印视频
        """
        success = True
        msg = '成功'
        video_addr = None
        try:
            headers = get_common_headers()
            url = f"https://www.xiaohongshu.com/explore/{note_id}"
            response = requests.get(url, headers=headers)
            res = response.text
            video_addr = re.findall(r'<meta name="og:video" content="(.*?)">', res)[0]
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, video_addr


    @staticmethod
    def get_note_no_water_img(img_url):
        """
            获取笔记无水印图片
            :param img_url: 你想要获取的图片的url
            返回笔记无水印图片
        """
        success = True
        msg = '成功'
        new_url = None
        try:
            # 新版图片资源优先保留 notes_pre_post token，使用 ci.xiaohongshu.com 输出 JPEG。
            # 例：
            # https://sns-webpic-qc.xhscdn.com/<time>/<hash>/notes_pre_post/<img_id>!nd_dft_wlteh_webp_3
            # -> https://ci.xiaohongshu.com/notes_pre_post/<img_id>?imageView2/format/jpeg
            if 'notes_pre_post/' in img_url:
                token = 'notes_pre_post/' + img_url.split('notes_pre_post/', 1)[1].split('!', 1)[0].split('?', 1)[0]
                new_url = f'https://ci.xiaohongshu.com/{token}?imageView2/format/jpeg'
            elif 'spectrum' in img_url:
                token = '/'.join(img_url.split('/')[-2:]).split('!', 1)[0].split('?', 1)[0]
                new_url = f'https://ci.xiaohongshu.com/{token}?imageView2/format/jpeg'
            elif '.jpg' in img_url:
                token = '/'.join([split for split in img_url.split('/')[-3:]]).split('!', 1)[0].split('?', 1)[0]
                new_url = f'https://ci.xiaohongshu.com/{token}?imageView2/format/jpeg'
            else:
                token = img_url.split('/')[-1].split('!', 1)[0].split('?', 1)[0]
                new_url = f'https://ci.xiaohongshu.com/{token}?imageView2/format/jpeg'
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, new_url

if __name__ == '__main__':
    """
        此文件为小红书api的使用示例
        所有涉及数据爬取的api都在此文件中
        数据注入的api违规请勿尝试
    """
    xhs_apis = XHS_Apis()
    cookies_str = r''
    # 获取用户信息
    user_url = 'https://www.xiaohongshu.com/user/profile/67a332a2000000000d008358?xsec_token=ABTf9yz4cLHhTycIlksF0jOi1yIZgfcaQ6IXNNGdKJ8xg=&xsec_source=pc_feed'
    success, msg, user_info = xhs_apis.get_user_info('67a332a2000000000d008358', cookies_str)
    logger.info(f'获取用户信息结果 {json.dumps(user_info, ensure_ascii=False)}: {success}, msg: {msg}')
    success, msg, note_list = xhs_apis.get_user_all_notes(user_url, cookies_str)
    logger.info(f'获取用户所有笔记结果 {json.dumps(note_list, ensure_ascii=False)}: {success}, msg: {msg}')
    # 获取笔记信息
    note_url = r'https://www.xiaohongshu.com/explore/67d7c713000000000900e391?xsec_token=AB1ACxbo5cevHxV_bWibTmK8R1DDz0NnAW1PbFZLABXtE=&xsec_source=pc_user'
    success, msg, note_info = xhs_apis.get_note_info(note_url, cookies_str)
    logger.info(f'获取笔记信息结果 {json.dumps(note_info, ensure_ascii=False)}: {success}, msg: {msg}')
    # 获取搜索关键词
    query = "榴莲"
    success, msg, search_keyword = xhs_apis.get_search_keyword(query, cookies_str)
    logger.info(f'获取搜索关键词结果 {json.dumps(search_keyword, ensure_ascii=False)}: {success}, msg: {msg}')
    # 搜索笔记
    query = "榴莲"
    query_num = 10
    sort = "general"
    note_type = 0
    success, msg, notes = xhs_apis.search_some_note(query, query_num, cookies_str, sort, note_type)
    logger.info(f'搜索笔记结果 {json.dumps(notes, ensure_ascii=False)}: {success}, msg: {msg}')
    # 获取笔记评论
    note_url = r'https://www.xiaohongshu.com/explore/67d7c713000000000900e391?xsec_token=AB1ACxbo5cevHxV_bWibTmK8R1DDz0NnAW1PbFZLABXtE=&xsec_source=pc_user'
    success, msg, note_all_comment = xhs_apis.get_note_all_comment(note_url, cookies_str)
    logger.info(f'获取笔记评论结果 {json.dumps(note_all_comment, ensure_ascii=False)}: {success}, msg: {msg}')



