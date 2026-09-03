"""Exercise real persistence and media preparation against a controlled model stream."""
import json
import threading
import time

import pytest
from sqlalchemy import select

from tests.test_web import env, login, make_note
from spider_xhs.web.ai import ChatService, prepare_sources
from spider_xhs.web.db import AIModel, ChatMessage, ChatThread, Note
from spider_xhs.web.library import import_existing


class ModelResponse:
    status_code = 200
    encoding = 'utf-8'

    def __init__(self, text='一份有依据的回答。', gate=None, started=None, truncated=False):
        self.text, self.gate, self.started, self.truncated = text, gate, started, truncated
        self.closed = False

    def iter_lines(self, **kwargs):
        if self.started:
            self.started.set()
        if self.gate:
            self.gate.wait(5)
        for value in [self.text[:4], self.text[4:]]:
            yield 'data: ' + json.dumps({'choices': [{'delta': {'content': value}}]}, ensure_ascii=False)
        if not self.truncated:
            yield 'data: [DONE]'

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def json(self):
        return {'choices': [{'message': {'content': self.text}}]}


def model(client, vision=True):
    result = client.post('/api/settings/ai/models', json={'name': '测试模型', 'base_url': 'https://model.example.invalid/v1',
        'model': 'test-vision', 'vision': vision, 'key': 'test-secret-never-return'})
    assert result.status_code == 200, result.text
    return result.json()['id']


def question(client, thread_id, model_id, note_ids=None, content='分析这些资料', request_id='1' * 32):
    return client.post(f'/api/chat/threads/{thread_id}/messages', json={'model_id': model_id, 'note_ids': note_ids or [],
        'content': content, 'request_id': request_id})


def finished(client, thread_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        result = client.get(f'/api/chat/threads/{thread_id}').json()
        if result['messages'][-1]['status'] not in {'pending', 'generating'}:
            return result
        time.sleep(.02)
    pytest.fail('generation did not finish')


def test_models_require_login_encrypt_keys_and_preserve_them_on_edit(env, monkeypatch):
    store, client, _, _ = env
    assert client.get('/api/settings/ai/models').status_code == 401
    assert client.get('/api/chat/threads').status_code == 401
    login(client)
    model_id = model(client)
    result = client.get('/api/settings/ai/models').json()[0]
    assert result['has_key'] and 'key' not in result and 'encrypted_key' not in result
    with store.session() as db:
        encrypted = db.get(AIModel, model_id).encrypted_key
        assert 'test-secret' not in encrypted
        assert store.cipher.decrypt(encrypted.encode()).decode() == 'test-secret-never-return'
    update = {k: result[k] for k in ['name', 'base_url', 'model', 'vision']}
    update['key'] = ''
    assert client.put(f'/api/settings/ai/models/{model_id}', json=update).status_code == 200
    with store.session() as db:
        assert db.get(AIModel, model_id).encrypted_key == encrypted
    update['base_url'] = 'https://name:password@model.invalid/v1'
    assert client.post('/api/settings/ai/models', json=update).status_code == 422
    monkeypatch.setattr('spider_xhs.utils.network.post', lambda *a, **kw: ModelResponse())
    assert client.post(f'/api/settings/ai/models/{model_id}/test').json()['ok']


def test_multi_source_stream_context_citations_and_followup(env, monkeypatch):
    store, client, data, _ = env
    login(client)
    second, _ = make_note(store.media, 'b' * 24, '第二份资料')
    third, _ = make_note(store.media, 'c' * 24, '绝不自动发送的资料')
    import_existing(store)
    with store.session() as db:
        db.get(Note, data['note_id']).ocr_text = '独立的 OCR 证据'
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return ModelResponse(f"参考[露营资料](#source-{data['note_id']})，建议先整理清单。")
    monkeypatch.setattr('spider_xhs.utils.network.post', post)
    model_id = model(client)
    thread_id = client.post('/api/chat/threads', json={}).json()['id']
    first = question(client, thread_id, model_id, [data['note_id'], second['note_id']]).json()
    result = finished(client, thread_id)
    assert [m['role'] for m in result['messages']] == ['user', 'assistant']
    assert result['messages'][-1]['status'] == 'completed'
    assert len(result['messages'][-1]['sources']) == 2
    payload = calls[0][1]['json']['messages'][-1]['content']
    assert len([p for p in payload if p['type'] == 'image_url']) == 2
    assert all(p['image_url']['url'].startswith('data:image/jpeg;base64,') for p in payload if p['type'] == 'image_url')
    text = '\n'.join(p.get('text', '') for p in payload)
    assert '独立的 OCR 证据' in text and second['note_id'] in text
    assert third['note_id'] not in text and '绝不自动发送' not in text
    assert 'test-secret' not in text and 'note_url' not in text
    assert calls[0][1]['allow_redirects'] is False
    assert client.get(f"/api/chat/messages/{first['id']}/events").text.startswith('data: ')
    assert question(client, thread_id, model_id, [data['note_id'], second['note_id']]).json()['id'] == first['id']
    assert len(calls) == 1  # idempotent retry cannot incur a second model call
    assert question(client, thread_id, model_id, [data['note_id']], '再解释一下', '2' * 32).status_code == 200
    result = finished(client, thread_id)
    assert len(result['messages']) == 4
    assert calls[1][1]['json']['messages'][1]['role'] == 'user'
    assert '分析这些资料' in calls[1][1]['json']['messages'][1]['content']
    assert '参考' in calls[1][1]['json']['messages'][2]['content']
    assert client.patch(f'/api/chat/threads/{thread_id}', json={'title': '新的名字'}).status_code == 200
    assert client.get(f'/api/chat/threads/{thread_id}').json()['title'] == '新的名字'
    assert client.delete(f'/api/chat/threads/{thread_id}').status_code == 200
    assert client.get(f'/api/notes/{data["note_id"]}').status_code == 200
    with store.session() as db:
        assert not list(db.scalars(select(ChatMessage).where(ChatMessage.thread_id == thread_id)))


def test_text_only_attachments_no_images_and_trashed_sources_rejected(env, monkeypatch):
    store, client, data, _ = env
    login(client)
    calls = []
    monkeypatch.setattr('spider_xhs.utils.network.post', lambda *a, **kw: calls.append(kw) or ModelResponse())
    model_id = model(client, False)
    thread_id = client.post('/api/chat/threads', json={}).json()['id']
    assert question(client, thread_id, model_id, [data['note_id']]).status_code == 200
    result = finished(client, thread_id)
    assert isinstance(calls[0]['json']['messages'][-1]['content'], str)
    assert '仅文本' in result['messages'][-1]['sources'][0]['coverage']
    with store.session() as db:
        db.get(Note, data['note_id']).trashed_at = time.time()
    assert question(client, thread_id, model_id, [data['note_id']], request_id='2' * 32).status_code == 422
    assert question(client, thread_id, model_id, ['missing'], request_id='3' * 32).status_code == 422
    assert question(client, thread_id, model_id, ['a'] * 9, request_id='4' * 32).status_code == 422


def test_video_uses_sampled_real_frames_and_states_no_audio(env):
    import cv2
    import numpy as np
    store, _, data, base = env
    with store.session() as db:
        db.get(Note, data['note_id']).kind = '视频'
    path = base / 'video_files/video.mp4'
    path.parent.mkdir()
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), 10, (64, 64))
    for i in range(30):
        writer.write(np.full((64, 64, 3), i * 7, dtype=np.uint8))
    writer.release()
    parts, sources, context = prepare_sources(store, [data['note_id']], True, threading.Event())
    assert len([p for p in parts if p['type'] == 'image_url']) == 6
    assert '6 帧' in sources[0]['coverage'] and '不含音频' in context
    path.unlink()
    path.symlink_to(store.root / 'secret.key')
    with pytest.raises(ValueError):
        prepare_sources(store, [data['note_id']], True, threading.Event())


def test_stop_prevents_late_completion_and_rejects_duplicate_active_turn(env, monkeypatch):
    _, client, _, _ = env
    login(client)
    gate, started = threading.Event(), threading.Event()
    monkeypatch.setattr('spider_xhs.utils.network.post', lambda *a, **kw: ModelResponse(gate=gate, started=started))
    model_id = model(client)
    thread_id = client.post('/api/chat/threads', json={}).json()['id']
    answer = question(client, thread_id, model_id).json()
    assert started.wait(3)
    assert question(client, thread_id, model_id, request_id='2' * 32).status_code == 409
    assert client.post(f"/api/chat/messages/{answer['id']}/stop").json()['status'] == 'stopped'
    gate.set()
    result = finished(client, thread_id)
    assert result['messages'][-1]['status'] == 'stopped'


@pytest.mark.parametrize('failure', ['http_error', 'truncated', 'empty'])
def test_provider_failure_is_saved_and_never_exposes_key(env, monkeypatch, failure):
    _, client, _, _ = env
    login(client)
    response = ModelResponse('' if failure == 'empty' else '保留的部分', truncated=failure == 'truncated')
    if failure == 'http_error':
        response.status_code = 401
    monkeypatch.setattr('spider_xhs.utils.network.post', lambda *a, **kw: response)
    model_id = model(client)
    thread_id = client.post('/api/chat/threads', json={}).json()['id']
    question(client, thread_id, model_id)
    result = finished(client, thread_id)
    assert result['messages'][-1]['status'] == 'error'
    assert result['messages'][-1]['error'] and 'test-secret' not in str(result)
    if failure == 'truncated':
        assert result['messages'][-1]['content'] == '保留的部分'


def test_restart_preserves_partial_answer_without_resending(env):
    store, _, _, _ = env
    with store.session() as db:
        thread = ChatThread(title='重启测试')
        db.add(thread)
        db.flush()
        message = ChatMessage(thread_id=thread.id, role='assistant', status='generating', content='部分回答')
        db.add(message)
        db.flush()
        message_id = message.id
    service = ChatService(store)
    service.recover()
    with store.session() as db:
        message = db.get(ChatMessage, message_id)
        assert message.status == 'stopped' and message.content == '部分回答'
    service.close()
