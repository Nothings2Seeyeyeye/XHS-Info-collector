import os
import re

# 默认与当前主流 Chrome 对齐；可通过环境变量覆盖为浏览器复制 Cookie 时的 UA
_DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
)
_DEFAULT_SEC_CH_UA = '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'
_DEFAULT_PLATFORM = '"Windows"'


def get_user_agent():
    return os.getenv('XHS_USER_AGENT', '').strip() or _DEFAULT_USER_AGENT


def get_sec_ch_ua():
    override = os.getenv('XHS_SEC_CH_UA', '').strip()
    if override:
        return override
    ua = get_user_agent()
    match = re.search(r'Chrome/(\d+)', ua)
    if match:
        major = match.group(1)
        return f'"Google Chrome";v="{major}", "Chromium";v="{major}", "Not_A Brand";v="24"'
    return _DEFAULT_SEC_CH_UA


def get_sec_ch_ua_platform():
    return os.getenv('XHS_SEC_CH_UA_PLATFORM', '').strip() or _DEFAULT_PLATFORM


def apply_browser_headers(headers: dict) -> dict:
    """将统一浏览器指纹写入请求头（不覆盖已有非空值）。"""
    merged = dict(headers or {})
    if not merged.get('user-agent'):
        merged['user-agent'] = get_user_agent()
    if not merged.get('sec-ch-ua'):
        merged['sec-ch-ua'] = get_sec_ch_ua()
    if not merged.get('sec-ch-ua-mobile'):
        merged['sec-ch-ua-mobile'] = '?0'
    if not merged.get('sec-ch-ua-platform'):
        merged['sec-ch-ua-platform'] = get_sec_ch_ua_platform()
    return merged
