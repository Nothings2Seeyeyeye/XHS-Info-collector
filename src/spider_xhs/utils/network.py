"""HTTP requests that do not inherit VPN/proxy environment variables.

Keep requests' normal certificate verification and stateless per-request session
semantics. Explicit `proxies=` remains available to existing CLI API callers;
the local workbench never supplies it.
"""
import requests as _requests

RequestException = _requests.RequestException
Response = _requests.Response
exceptions = _requests.exceptions


def request(method, url, **kwargs):
    with _requests.Session() as session:
        session.trust_env = False
        return session.request(method=method, url=url, **kwargs)


def get(url, **kwargs):
    kwargs.setdefault("allow_redirects", True)
    return request("GET", url, **kwargs)


def post(url, data=None, json=None, **kwargs):
    return request("POST", url, data=data, json=json, **kwargs)


def put(url, data=None, **kwargs):
    return request("PUT", url, data=data, **kwargs)
