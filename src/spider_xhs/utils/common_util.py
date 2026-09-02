import os
import time
import random
import hashlib
import binascii
import json

import execjs
import requests
from loguru import logger
from dotenv import load_dotenv

from spider_xhs.paths import REPO_ROOT, static_js_dir
from spider_xhs.utils.http_util import REQUEST_TIMEOUT
from spider_xhs.utils.browser_profile import apply_browser_headers
from spider_xhs.utils.xhs_creator_util import generate_xsc
from spider_xhs.utils.xhs_util import generate_xs_xs_common

_STATIC_DIR = static_js_dir()
_WEBSECTIGA_ENV_PATH = os.path.join(_STATIC_DIR, 'xhs_websectiga_env.js')

_A1_CHARSET = 'abcdefghijklmnopqrstuvwxyz1234567890'
_AS_URL = 'https://as.xiaohongshu.com'


def load_env():
    load_dotenv()
    cookies_str = os.getenv('COOKIES')
    return cookies_str


def init():
    load_dotenv()
    project_root = str(REPO_ROOT)
    media_override = os.getenv('XHS_MEDIA_BASE', '').strip()
    excel_override = os.getenv('XHS_EXCEL_BASE', '').strip()
    if media_override:
        media_base_path = os.path.abspath(media_override)
    else:
        media_base_path = os.path.abspath(os.path.join(project_root, 'datas/media_datas'))
    if excel_override:
        excel_base_path = os.path.abspath(excel_override)
    else:
        excel_base_path = os.path.abspath(os.path.join(project_root, 'datas/excel_datas'))
    for base_path in [media_base_path, excel_base_path]:
        if not os.path.exists(base_path):
            os.makedirs(base_path)
            logger.info(f'创建目录 {base_path}')
    cookies_str = load_env()
    if cookies_str:
        from spider_xhs.utils.cookie_util import check_cookie_health
        for warning in check_cookie_health(cookies_str):
            logger.warning(f'Cookie 健康检查: {warning}')
    base_path = {
        'media': media_base_path,
        'excel': excel_base_path,
    }
    return cookies_str, base_path


def generate_a1():
    ts_hex = hex(int(time.time() * 1000))[2:]
    random_str = ''.join(random.choices(_A1_CHARSET, k=30))
    a_part = ts_hex + random_str + '5' + '0' + '000'
    crc = binascii.crc32(a_part.encode()) & 0xFFFFFFFF
    return (a_part + str(crc))[:52]


def generate_web_id(a1):
    return hashlib.md5(a1.encode()).hexdigest()


def _load_websectiga_env():
    try:
        return open(_WEBSECTIGA_ENV_PATH, 'r', encoding='utf-8').read()
    except FileNotFoundError:
        return None


def fetch_sec_cookies(cookies, headers, app_id=None):
    sec_poison_id = None
    websectiga = None

    api = '/api/sec/v1/scripting'
    if app_id == 'xhs-pc-web':
        data = {"callFrom": "web", "callback": "seccallback", "type": "ds", "appId": "xhs-pc-web"}
    else:
        data = {"callFrom": "web", "callback": "seccallback"}
    h = apply_browser_headers(dict(headers))
    h['content-type'] = 'application/json;charset=UTF-8'
    if app_id == 'xhs-pc-web':
        sign_h = generate_xs_xs_common(cookies['a1'], api, data)
        h['x-s'] = sign_h[0]
        h['x-t'] = str(sign_h[1])
        h['x-s-common'] = sign_h[2]
    else:
        h.update(generate_xsc(cookies['a1'], api, data))
    data_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
    try:
        resp = requests.post(
            _AS_URL + api,
            headers=h,
            cookies=cookies,
            data=data_str.encode('utf-8'),
            timeout=REQUEST_TIMEOUT
        )
        res = resp.json()
        sec_poison_id = res.get('data', {}).get('secPoisonId')
        jsvmp_code = res.get('data', {}).get('data', '')
        if jsvmp_code:
            env = _load_websectiga_env()
            if env:
                try:
                    js_code = env + '\n' + jsvmp_code + '\nvar __result = _websectiga_result;'
                    ctx = execjs.compile(js_code)
                    websectiga = ctx.eval('__result') or None
                except Exception as e:
                    logger.debug(f'websectiga jsvmp execution failed: {e}')
    except Exception as e:
        logger.debug(f'fetch sec cookies failed: {e}')
    return sec_poison_id, websectiga


def fetch_gid(cookies, headers, app_id=None):
    api = '/api/sec/v1/shield/webprofile'
    data = {
        "platform": "Windows",
        "sdkVersion": "4.3.5",
        "svn": "2",
        "profileData": ""
    }
    h = apply_browser_headers(dict(headers))
    h['content-type'] = 'application/json'
    if app_id == 'xhs-pc-web':
        xs, xt, xs_common = generate_xs_xs_common(cookies['a1'], api, data)
        h['x-s'] = xs
        h['x-t'] = str(xt)
        h['x-s-common'] = xs_common
    else:
        h.update(generate_xsc(cookies['a1'], api, data))
    data_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
    try:
        resp = requests.post(
            _AS_URL + api,
            headers=h,
            cookies=cookies,
            data=data_str.encode('utf-8'),
            timeout=REQUEST_TIMEOUT
        )
        for key, value in resp.cookies.items():
            cookies[key] = value
        if 'gid' in cookies:
            return cookies['gid']
    except Exception as e:
        logger.debug(f'fetch gid failed: {e}')
    return None
