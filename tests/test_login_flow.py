"""Regression coverage for QR confirmation, session exchange and bounded verification."""
import pytest
import requests
from sqlalchemy import select

from tests.test_web import env, login
from spider_xhs.apis.xhs_pc_login_apis import XHSLoginApi
from spider_xhs.web.db import Job
from spider_xhs.web.tasks import LoginRequired, WebXHS, verify_cookie


class Response:
    def __init__(self, payload, cookies=None, status=200):
        self.payload = payload
        self.cookies = requests.cookies.cookiejar_from_dict(cookies or {})
        self.status_code = status

    def json(self):
        return self.payload


@pytest.mark.parametrize('old_session', ['', 'anonymous-session', 'expired-session'])
def test_native_status_replaces_old_session(monkeypatch, old_session):
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        return Response({'success': True, 'data': {'code_status': 2, 'login_info': {'session': 'fresh-session'}}})
    monkeypatch.setattr('spider_xhs.utils.network.get', get)
    monkeypatch.setattr('spider_xhs.utils.network.post', lambda *args, **kwargs: pytest.fail('must not mix the legacy confirmation endpoint'))
    api = XHSLoginApi()
    ok, _, cookies = api.check_qrcode_status('qr', 'code', {'a1': 'test-a1', 'web_session': old_session})
    assert ok
    assert cookies['web_session'] == 'fresh-session'
    assert len(calls) == 1 and '/api/sns/web/v1/login/qrcode/status?' in calls[0]


def test_phone_confirmation_without_new_session_is_not_success(monkeypatch):
    monkeypatch.setattr('spider_xhs.utils.network.get', lambda *args, **kwargs: Response({'success': True, 'data': {'code_status': 2}}))
    api = XHSLoginApi()
    ok, message, _ = api.check_qrcode_status('qr', 'code', {'a1': 'test', 'web_session': 'old-session'})
    assert not ok
    assert api.last_auth_issue['kind'] == 'protocol'
    assert '登录凭据' in message


def test_profile_rejects_guest_and_signs_get(monkeypatch):
    methods = []
    monkeypatch.setattr('spider_xhs.apis.xhs_pc_login_apis.generate_headers', lambda *args, **kwargs: (methods.append(kwargs.get('method')) or {}, ''))
    monkeypatch.setattr('spider_xhs.utils.network.get', lambda *args, **kwargs: Response({'success': True, 'data': {'guest': True, 'user_id': 'guest-id'}}))
    api = XHSLoginApi()
    ok, _, _ = api.get_user_info({'a1': 'test', 'web_session': 'guest-session'})
    assert not ok and api.last_auth_issue['kind'] == 'authentication'
    assert methods == ['GET']


@pytest.mark.parametrize('stage', ['create', 'status', 'profile'])
def test_http_471_overrides_success_true_and_code_zero(monkeypatch, stage):
    # Observed after the phone confirmed login: HTTP 471 with success=true,
    # code=0 and no usable data. Neither success nor code overrides HTTP.
    response = Response({'code': 0, 'success': True}, status=471)
    monkeypatch.setattr('spider_xhs.utils.network.get', lambda *args, **kwargs: response)
    monkeypatch.setattr('spider_xhs.utils.network.post', lambda *args, **kwargs: response)
    api = XHSLoginApi()
    cookies = {'a1': 'test', 'web_session': 'old-session'}
    if stage == 'create':
        ok, _, _ = api.generate_qrcode(cookies)
    elif stage == 'status':
        ok, _, _ = api.check_qrcode_status('qr', 'code', cookies)
    else:
        ok, _, _ = api.get_user_info(cookies)
    assert not ok
    assert api.last_auth_issue['kind'] == 'blocked'
    assert 'HTTP 471' in api.last_auth_issue['message']
    assert '错误码 0' not in api.last_auth_issue['message']


def test_http_471_with_non_json_body_is_still_blocked(monkeypatch):
    response = Response({}, status=471)
    def invalid_json():
        raise ValueError('not JSON')
    response.json = invalid_json
    monkeypatch.setattr('spider_xhs.utils.network.get', lambda *args, **kwargs: response)
    api = XHSLoginApi()
    ok, _, _ = api.check_qrcode_status('qr', 'code', {'a1': 'test'})
    assert not ok and api.last_auth_issue['kind'] == 'blocked'


def test_code_zero_without_success_does_not_authenticate(monkeypatch):
    response = Response({'code': 0, 'data': {'guest': False, 'user_id': 'real-user'}})
    monkeypatch.setattr('spider_xhs.utils.network.get', lambda *args, **kwargs: response)
    api = XHSLoginApi()
    ok, _, _ = api.get_user_info({'a1': 'test', 'web_session': 'session'})
    assert not ok and api.last_auth_issue['kind'] == 'protocol'
    assert '错误码 0' not in api.last_auth_issue['message']


def mock_qrcode(monkeypatch):
    cookies = {'a1': 'test', 'web_session': 'fresh-session'}
    monkeypatch.setattr(XHSLoginApi, 'generate_init_cookies', lambda self: cookies.copy())
    monkeypatch.setattr(XHSLoginApi, 'generate_qrcode', lambda self, value: (True, 'ok', {
        'qr_id': 'qr', 'code': 'code', 'qr_url': 'https://example.invalid/qr', 'cookies': value,
    }))
    return cookies


def test_confirmed_qr_only_verifies_account_and_success_is_idempotent(env, monkeypatch):
    store, client, _, _ = env
    login(client)
    cookies = mock_qrcode(monkeypatch)
    counts = {'exchange': 0, 'verify': 0}
    def confirm(*args):
        counts['exchange'] += 1
        return True, 'ok', cookies
    def verify(self, value):
        counts['verify'] += 1
        if counts['verify'] == 1:
            self._auth_issue('temporary', '账号服务暂时不可用')
            return False, {}, value
        return True, {'user_id': 'real-user', 'nickname': '测试用户', 'guest': False}, value
    monkeypatch.setattr(XHSLoginApi, 'check_qrcode_status', confirm)
    monkeypatch.setattr(XHSLoginApi, 'get_user_info', verify)
    store.put('xhs_status', {'state': 'expired'})
    with store.session() as db:
        job = Job(title='等待扫码', state='waiting_login')
        db.add(job)
        db.flush()
        job_id = job.id
    qr = client.post('/api/xhs/qrcode').json()
    path = f"/api/xhs/qrcode/{qr['id']}"
    assert client.get(path).json()['state'] == 'verifying'
    with store.session() as db:
        assert db.get(Job, job_id).state == 'waiting_login'
    assert client.get(path).json()['state'] == 'success'
    assert client.get(path).json()['state'] == 'success'
    assert counts == {'exchange': 1, 'verify': 2}
    assert store.secret('xhs_cookie').endswith('web_session=fresh-session')
    with store.session() as db:
        assert db.get(Job, job_id).state == 'queued'


def test_failed_verification_ends_without_replacing_saved_credentials(env, monkeypatch):
    store, client, _, _ = env
    login(client)
    cookies = mock_qrcode(monkeypatch)
    monkeypatch.setattr(XHSLoginApi, 'check_qrcode_status', lambda *args: (True, 'ok', cookies))
    store.put_secret('xhs_cookie', 'previous-verified-cookie')
    attempts = []
    def unavailable(self, value):
        attempts.append(1)
        self._auth_issue('temporary', '账号服务暂时不可用')
        return False, {}, value
    monkeypatch.setattr(XHSLoginApi, 'get_user_info', unavailable)
    qr = client.post('/api/xhs/qrcode').json()
    path = f"/api/xhs/qrcode/{qr['id']}"
    states = [client.get(path).json()['state'] for _ in range(4)]
    assert states == ['verifying', 'verifying', 'error', 'error']
    assert len(attempts) == 3
    assert store.secret('xhs_cookie') == 'previous-verified-cookie'


def test_account_guest_response_is_terminal(env, monkeypatch):
    store, client, _, _ = env
    login(client)
    cookies = mock_qrcode(monkeypatch)
    monkeypatch.setattr(XHSLoginApi, 'check_qrcode_status', lambda *args: (True, 'ok', cookies))
    monkeypatch.setattr(XHSLoginApi, 'get_user_info', lambda *args: (True, {'user_id': 'guest', 'guest': True}, cookies))
    qr = client.post('/api/xhs/qrcode').json()
    result = client.get(f"/api/xhs/qrcode/{qr['id']}").json()
    assert result['state'] == 'error'


def test_stored_cookie_check_rejects_guest(env, monkeypatch):
    store, _, _, _ = env
    store.put_secret('xhs_cookie', 'a1=test; web_session=anonymous-session')
    monkeypatch.setattr(WebXHS, 'get_user_self_info2', lambda *args: (True, 'ok', {'success': True, 'data': {'user_id': 'guest', 'guest': True}}))
    with pytest.raises(LoginRequired):
        verify_cookie(store)
    assert store.get('xhs_status')['state'] == 'expired'


@pytest.mark.parametrize('saved_state', ['valid', 'expired', 'guest', 'different_account', 'missing'])
def test_blocked_qr_only_reuses_a_verified_saved_account(env, monkeypatch, saved_state):
    store, client, _, _ = env
    login(client)
    mock_qrcode(monkeypatch)
    saved_cookie = 'a1=saved-a1; web_session=saved-session'
    store.put_secret('xhs_cookie', saved_cookie if saved_state != 'missing' else '')
    store.put('xhs_status', {'state': 'expired', 'user_id': 'original-user'})
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        if '/qrcode/status?' in url:
            return Response({'success': True, 'code': 0}, status=471)
        assert url.endswith('/api/sns/web/v2/user/me')
        assert kwargs['cookies']['web_session'] == 'saved-session'
        if saved_state == 'expired':
            return Response({'success': False, 'code': -100}, status=401)
        return Response({'success': True, 'code': 0, 'data': {
            'user_id': 'another-user' if saved_state == 'different_account' else 'original-user',
            'guest': saved_state == 'guest', 'nickname': '测试用户',
        }})
    monkeypatch.setattr('spider_xhs.utils.network.get', get)
    with store.session() as db:
        jobs = [Job(title=state, state=state) for state in ('waiting_login', 'paused', 'cancelled')]
        db.add_all(jobs)
        db.flush()
        job_ids = [job.id for job in jobs]
    qr = client.post('/api/xhs/qrcode').json()
    path = f"/api/xhs/qrcode/{qr['id']}"
    result = client.get(path).json()
    assert client.get(path).json() == result
    if saved_state == 'valid':
        assert result['state'] == 'success'
        assert '已保存的登录' in result['message']
        assert store.get('xhs_status')['state'] == 'valid'
    else:
        assert result['state'] == 'blocked'
        assert 'HTTP 471' in result['message']
        assert store.get('xhs_status')['state'] == 'expired'
    assert store.secret('xhs_cookie') == (saved_cookie if saved_state != 'missing' else '')
    assert len(calls) == (1 if saved_state == 'missing' else 2)
    with store.session() as db:
        assert [db.get(Job, id).state for id in job_ids] == [
            'queued' if saved_state == 'valid' else 'waiting_login', 'paused', 'cancelled',
        ]


def test_collection_treats_http_471_as_platform_restriction():
    blocked, message = WebXHS()._is_risk_response(471, '', {'success': True, 'code': 0})
    assert blocked and '[PLATFORM_BLOCKED]' in message
