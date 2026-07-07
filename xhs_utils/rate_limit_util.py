import os
import random
import time

from loguru import logger


def _read_float(name: str, default: float) -> float:
    raw = os.getenv(name, '').strip()
    if not raw:
        return default
    try:
        return max(0.0, float(raw))
    except ValueError:
        logger.warning(f'环境变量 {name}={raw!r} 无效，使用默认值 {default}')
        return default


def get_request_delay_range():
    """普通 API 请求间隔（秒）。"""
    min_delay = _read_float('XHS_REQUEST_DELAY_MIN', 1.5)
    max_delay = _read_float('XHS_REQUEST_DELAY_MAX', 3.5)
    if max_delay < min_delay:
        max_delay = min_delay
    return min_delay, max_delay


def get_pagination_delay_range():
    """翻页/批量列表请求间隔（秒），通常略长于普通请求。"""
    min_delay = _read_float('XHS_PAGINATION_DELAY_MIN', 2.5)
    max_delay = _read_float('XHS_PAGINATION_DELAY_MAX', 5.0)
    if max_delay < min_delay:
        max_delay = min_delay
    return min_delay, max_delay


def get_media_delay_range():
    """媒体下载间隔（秒）。"""
    min_delay = _read_float('XHS_MEDIA_DELAY_MIN', 0.8)
    max_delay = _read_float('XHS_MEDIA_DELAY_MAX', 2.0)
    if max_delay < min_delay:
        max_delay = min_delay
    return min_delay, max_delay


def is_rate_limit_enabled() -> bool:
    flag = os.getenv('XHS_RATE_LIMIT', '1').strip().lower()
    return flag not in {'0', 'false', 'no', 'off'}


def sleep_random(min_seconds: float, max_seconds: float, label: str = ''):
    if not is_rate_limit_enabled():
        return
    if max_seconds <= 0:
        return
    delay = random.uniform(min_seconds, max_seconds)
    if label:
        logger.debug(f'[限速] {label} 等待 {delay:.2f}s')
    time.sleep(delay)


def sleep_before_request(label: str = 'api'):
    min_delay, max_delay = get_request_delay_range()
    sleep_random(min_delay, max_delay, label)


def sleep_before_pagination(label: str = 'pagination'):
    min_delay, max_delay = get_pagination_delay_range()
    sleep_random(min_delay, max_delay, label)


def sleep_before_media(label: str = 'media'):
    min_delay, max_delay = get_media_delay_range()
    sleep_random(min_delay, max_delay, label)
