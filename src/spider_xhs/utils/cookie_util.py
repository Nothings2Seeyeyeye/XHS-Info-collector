def trans_cookies(cookies_str):
    if not cookies_str or not cookies_str.strip():
        return {}
    cookies = {}
    for item in cookies_str.split(';'):
        item = item.strip()
        if not item or '=' not in item:
            continue
        key, value = item.split('=', 1)
        key = key.strip()
        if key:
            cookies[key] = value.strip()
    return cookies


def require_cookie(cookies, key):
    value = (cookies or {}).get(key, '').strip()
    if not value:
        raise ValueError(
            f"COOKIES 缺少必要字段 {key}，请从已登录小红书的浏览器请求中复制完整 Cookie 后重试。"
        )
    return value


def check_cookie_health(cookies_str: str):
    """
    检查 Cookie 完整度，返回可读警告列表（不阻断运行）。
    缺少风控相关字段时更容易触发 403/验证码。
    """
    cookies = trans_cookies(cookies_str)
    warnings = []
    for key in ('a1', 'webId'):
        if not (cookies.get(key) or '').strip():
            warnings.append(f'缺少必要字段 {key}')
    for key in ('gid', 'websectiga', 'sec_poison_id'):
        if not (cookies.get(key) or '').strip():
            warnings.append(
                f'缺少风控字段 {key}，建议使用 `python main.py --mode login-pc-qrcode` 重新登录获取完整 Cookie'
            )
    return warnings
