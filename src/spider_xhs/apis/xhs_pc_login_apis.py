import json
import time
import random
import uuid

from spider_xhs.utils import network as requests
import qrcode
from loguru import logger

from spider_xhs.apis.xhs_pc_apis import XHS_Apis
from spider_xhs.utils.http_util import REQUEST_TIMEOUT
from spider_xhs.utils.browser_profile import apply_browser_headers
from spider_xhs.utils.xhs_util import generate_headers, splice_str
from spider_xhs.utils.common_util import generate_a1, generate_web_id, fetch_sec_cookies, fetch_gid


class XHSLoginApi:
    def __init__(self):
        self.base_url = "https://edith.xiaohongshu.com"
        self.as_url = "https://as.xiaohongshu.com"
        self.home_url = 'https://www.xiaohongshu.com/explore'
        self.last_auth_issue = None

    def _auth_issue(self, kind, message, response=None, payload=None):
        # Diagnostics deliberately contain no cookie/session or raw response body.
        self.last_auth_issue = {
            'kind': kind,
            'message': message,
            'http_status': getattr(response, 'status_code', None),
            'code': (payload or {}).get('code'),
        }

    def _check_auth_response(self, response, payload):
        status = response.status_code
        code = str(payload.get('code', ''))
        message = str(payload.get('msg', ''))
        if status in {403, 429, 461, 471} or code == '300012' or any(word in message for word in ('安全限制', 'IP存在风险', 'IP 存在风险', '需要验证', '访问过于频繁')):
            detail = f'（HTTP {status}）' if status >= 400 else ''
            self._auth_issue('blocked', f'本次登录请求被小红书拦截{detail}。请在官网检查并完成安全验证后再试；重新扫码不一定能解除限制。', response, payload)
            return False
        if status >= 500:
            self._auth_issue('temporary', '小红书账号服务暂时不可用。', response, payload)
            return False
        if status >= 400 or payload.get('success') is not True:
            if status < 400 and code in ('', '0'):
                self._auth_issue('protocol', '小红书响应缺少有效的登录确认信息，请稍后重试。', response, payload)
                return False
            suffix = f'（HTTP {status}）' if status >= 400 else f'（错误码 {code[:30]}）'
            self._auth_issue('authentication', f'小红书未确认有效登录{suffix}，请重新生成二维码。', response, payload)
            return False
        return True

    @staticmethod
    def _trace_auth_response(stage, response, payload):
        """Log response shape only; QR tokens, user details and cookies stay private."""
        data = payload.get('data')
        data = data if isinstance(data, dict) else {}
        login_info = data.get('login_info')
        login_info = login_info if isinstance(login_info, dict) else {}
        code = payload.get('code')
        success = payload.get('success')
        if stage == 'qrcode_status' and response.status_code < 400 and success is True and data.get('code_status') in (0, 1):
            return
        logger.debug('XHS auth {}: {}', stage, {
            'http_status': response.status_code,
            'code': code if str(code).lstrip('-').isdigit() else None,
            'success': success if isinstance(success, (bool, int)) else None,
            'success_type': type(success).__name__,
            'code_status': data.get('code_status') if isinstance(data.get('code_status'), int) else None,
            'has_issued_session': bool(login_info.get('session') or response.cookies.get('web_session')),
            'has_user_id': bool(data.get('user_id') or data.get('id')),
            'guest': data.get('guest') if isinstance(data.get('guest'), bool) else None,
        })

    def _auth_payload(self, response, stage):
        # A blocked request can return HTML or an empty body. Classify its HTTP
        # status before treating the missing JSON as a connection/login failure.
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        payload = payload if isinstance(payload, dict) else {}
        self._trace_auth_response(stage, response, payload)
        return payload

    @staticmethod
    def _get_sec_headers():
        return apply_browser_headers({
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9',
            'content-type': 'application/json;charset=UTF-8',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'origin': 'https://www.xiaohongshu.com',
            'referer': 'https://www.xiaohongshu.com/',
        })

    def generate_init_cookies(self):
        ts = int(time.time() * 1000)
        a1 = generate_a1()
        web_id = generate_web_id(a1)
        cookies = {
            'abRequestId': str(uuid.uuid4()),
            'ets': str(ts),
            'webBuild': '6.7.4',
            'xsecappid': 'xhs-pc-web',
            'loadts': str(ts + random.randint(50, 200)),
            'a1': a1,
            'webId': web_id,
        }

        req_headers = self._get_sec_headers()
        sec_poison_id, websectiga = fetch_sec_cookies(cookies, req_headers, app_id='xhs-pc-web')
        if sec_poison_id:
            cookies['sec_poison_id'] = sec_poison_id
        if websectiga:
            cookies['websectiga'] = websectiga

        gid = fetch_gid(cookies, req_headers, app_id='xhs-pc-web')
        if gid:
            cookies['gid'] = gid

        return cookies

    def generate_qrcode(self, cookies):
        api = '/api/sns/web/v1/login/qrcode/create'
        data = {"qr_type": 1}

        headers, data = generate_headers(cookies['a1'], api, data)
        resp = requests.post(
            self.base_url + api,
            headers=headers, cookies=cookies, data=data,
            timeout=REQUEST_TIMEOUT
        )
        for key, value in resp.cookies.items():
            cookies[key] = value

        res = self._auth_payload(resp, 'qrcode_create')
        if not self._check_auth_response(resp, res):
            return False, self.last_auth_issue['message'], None
        data = res.get('data') or {}
        if not all(key in data for key in ('qr_id', 'code', 'url')):
            return False, res.get('msg', '二维码响应缺少必要字段'), {'cookies': cookies, 'res_json': res}

        return True, '成功', {
            'cookies': cookies,
            'qr_id': data['qr_id'],
            'code': data['code'],
            'qr_url': data['url'],
        }

    def check_qrcode_status(self, qr_id, code, cookies):
        """Poll the native endpoint that returns both status and login_info.

        Do not mix the legacy /api/qrcode/userinfo confirmation with a second
        session exchange: the native status response is the single authority.
        """
        self.last_auth_issue = None
        api = '/api/sns/web/v1/login/qrcode/status'
        params = {"qr_id": qr_id, "code": code}
        splice_api = splice_str(api, params)
        headers, _ = generate_headers(cookies['a1'], splice_api, method='GET')
        resp = requests.get(
            self.base_url + splice_api,
            headers=headers, cookies=cookies,
            timeout=REQUEST_TIMEOUT
        )
        for key, value in resp.cookies.items():
            cookies[key] = value
        res = self._auth_payload(resp, 'qrcode_status')
        if not self._check_auth_response(resp, res):
            return False, self.last_auth_issue['message'], cookies
        data = res.get('data') or {}
        try:
            status = int(data.get('code_status'))
        except (TypeError, ValueError):
            self._auth_issue('protocol', '二维码状态响应缺少确认信息，请重新生成二维码。', resp, res)
            return False, self.last_auth_issue['message'], cookies
        if status == 2:
            login_info = data.get('login_info') or {}
            session = login_info.get('session') or resp.cookies.get('web_session')
            if not session:
                self._auth_issue('protocol', '手机已确认，但小红书没有返回登录凭据，请重新生成二维码。', resp, res)
                return False, self.last_auth_issue['message'], cookies
            # Always replace an old or anonymous session with this QR's session.
            cookies['web_session'] = session
            return True, '扫码已确认，正在校验账号', cookies
        mapping = {0: '请扫描二维码', 1: '请在手机上确认登录', 3: '二维码已过期'}
        if status not in mapping:
            self._auth_issue('protocol', '二维码返回了无法识别的状态，请重新生成二维码。', resp, res)
            return False, self.last_auth_issue['message'], cookies
        return False, mapping[status], cookies

    def _login_by_qrcode_status(self, qr_id, code, cookies):
        # Backwards-compatible helper for existing callers.
        self.check_qrcode_status(qr_id, code, cookies)
        return cookies

    def get_user_info(self, cookies):
        self.last_auth_issue = None
        api = '/api/sns/web/v2/user/me'

        headers, _ = generate_headers(cookies['a1'], api, method='GET')
        resp = requests.get(
            self.base_url + api,
            headers=headers, cookies=cookies,
            timeout=REQUEST_TIMEOUT
        )
        for key, value in resp.cookies.items():
            cookies[key] = value

        res = self._auth_payload(resp, 'user_me')
        data = res.get('data') or {}
        if not self._check_auth_response(resp, res):
            return False, data, cookies
        if data.get('guest') in (True, 1, 'true', '1'):
            self._auth_issue('authentication', '小红书返回的仍是游客会话，请重新扫码并在手机上确认登录。', resp, res)
            return False, data, cookies
        if not (data.get('user_id') or data.get('id')):
            self._auth_issue('protocol', '账号校验没有返回用户信息，请重新扫码。', resp, res)
            return False, data, cookies
        if not cookies.get('web_session'):
            self._auth_issue('protocol', '账号校验缺少登录凭据，请重新扫码。', resp, res)
            return False, data, cookies
        return True, data, cookies

    def send_phone_code(self, phone, cookies, zone='86'):
        api = '/api/sns/web/v2/login/send_code'
        params = {"phone": phone, "zone": zone, "type": "login"}
        splice_api = splice_str(api, params)

        headers, _ = generate_headers(cookies['a1'], splice_api)
        resp = requests.get(
            self.base_url + splice_api,
            headers=headers, cookies=cookies,
            timeout=REQUEST_TIMEOUT
        )
        res = resp.json()
        return res.get('success', False), res.get('msg', ''), res

    def login_by_phone(self, phone, code, cookies, zone='86'):
        check_api = '/api/sns/web/v1/login/check_code'
        params = {"phone": phone, "zone": zone, "code": code}
        splice_api = splice_str(check_api, params)

        headers, _ = generate_headers(cookies['a1'], splice_api)
        resp = requests.get(
            self.base_url + splice_api,
            headers=headers, cookies=cookies,
            timeout=REQUEST_TIMEOUT
        )
        res = resp.json()
        if not res.get('success'):
            return False, res.get('msg', '验证码验证失败'), {'cookies': cookies}
        mobile_token = (res.get('data') or {}).get('mobile_token')
        if not mobile_token:
            return False, res.get('msg', '验证码响应缺少 mobile_token'), {'cookies': cookies, 'res_json': res}

        login_api = '/api/sns/web/v2/login/code'
        data = {"mobile_token": mobile_token, "zone": zone, "phone": phone}
        headers, data = generate_headers(cookies['a1'], login_api, data)
        resp = requests.post(
            self.base_url + login_api,
            headers=headers, cookies=cookies, data=data,
            timeout=REQUEST_TIMEOUT
        )
        for key, value in resp.cookies.items():
            cookies[key] = value

        res = resp.json()
        if not res.get('success'):
            return False, res.get('msg', '登录失败'), {'cookies': cookies}
        session = (res.get('data') or {}).get('session')
        if not session:
            return False, res.get('msg', '登录响应缺少 session'), {'cookies': cookies, 'res_json': res}
        cookies['web_session'] = session
        return True, '成功', {
            'cookies': cookies,
            'res_json': res,
        }

    @staticmethod
    def cookies_to_str(cookies):
        return '; '.join(f'{k}={v}' for k, v in cookies.items())

    @staticmethod
    def show_qrcode_terminal(url):
        qr = qrcode.QRCode(box_size=1, border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)

    @staticmethod
    def show_qrcode_image(url):
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.show()

    def qrcode_login(self, show_in_terminal=True):
        logger.info('[1/4] 正在生成初始cookies...')
        cookies = self.generate_init_cookies()
        logger.info(f'{cookies}')

        logger.info('[2/4] 正在获取二维码...')
        success, msg, qr_data = self.generate_qrcode(cookies)
        if not success:
            logger.error(f'获取二维码失败: {msg}')
            return None
        cookies = qr_data['cookies']

        logger.info('请使用小红书APP扫描以下二维码:')
        if show_in_terminal:
            self.show_qrcode_terminal(qr_data['qr_url'])
        else:
            self.show_qrcode_image(qr_data['qr_url'])

        logger.info('[3/4] 等待扫码...')
        while True:
            success, msg, cookies = self.check_qrcode_status(
                qr_data['qr_id'], qr_data['code'], cookies
            )
            if success:
                logger.info(msg)
                break
            if msg == '二维码已过期':
                logger.error(msg)
                return None
            if self.last_auth_issue:
                logger.error(self.last_auth_issue['message'])
                return None
            time.sleep(2)

        logger.info('[4/4] 验证登录状态...')
        success, user_info, cookies = self.get_user_info(cookies)
        if success:
            logger.info(f'用户: {user_info.get("nickname", "未知")} (RedID: {user_info.get("red_id", "未知")})')
        else:
            logger.warning('获取用户信息失败，但cookies可能仍有效')

        cookies_str = self.cookies_to_str(cookies)
        logger.success(f'登录成功!\ncookies:\n{cookies_str}')
        return cookies_str

    def phone_login(self):
        logger.info('[1/4] 正在生成初始cookies...')
        cookies = self.generate_init_cookies()
        logger.info(f'a1={cookies["a1"]}')

        phone = input('请输入手机号: ')
        logger.info('[2/4] 正在发送验证码...')
        success, msg, _ = self.send_phone_code(phone, cookies)
        if not success:
            logger.error(f'发送失败: {msg}')
            return None
        logger.info('验证码已发送')

        code = input('请输入验证码: ')
        logger.info('[3/4] 正在验证...')
        success, msg, result = self.login_by_phone(phone, code, cookies)
        if not success:
            logger.error(f'验证失败: {msg}')
            return None
        cookies = result['cookies']

        logger.info('[4/4] 验证登录状态...')
        success, user_info, cookies = self.get_user_info(cookies)
        if success:
            logger.info(f'用户: {user_info.get("nickname", "未知")} (RedID: {user_info.get("red_id", "未知")})')

        cookies_str = self.cookies_to_str(cookies)
        logger.success(f'登录成功!\ncookies:\n{cookies_str}')
        return cookies_str


if __name__ == '__main__':
    login_api = XHSLoginApi()
    # cookies_str = login_api.qrcode_login(show_in_terminal=True)
    cookies_str = login_api.phone_login()

    xhs_apis = XHS_Apis()
    # 获取用户信息
    user_url = 'https://www.xiaohongshu.com/user/profile/67a332a2000000000d008358?xsec_token=ABTf9yz4cLHhTycIlksF0jOi1yIZgfcaQ6IXNNGdKJ8xg=&xsec_source=pc_feed'
    success, msg, user_info = xhs_apis.search_note("888666", cookies_str)
    print(success, msg, user_info)
