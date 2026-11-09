from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from backend.app.main import app
from backend.app.routers import investigations as api
from backend.app.services import investigation as agent
from backend.app import security
from pydantic import SecretStr


EVIDENCE = [{"id": "a", "source_id": "7", "product_id": "luna-smartwatch", "review_text": "Battery runs out early", "title": None, "rating": 2, "review_date": None, "source_url": "https://example.test", "similarity": 0.7}]
FINDING = {"kind": "reported_problem", "text": "A customer reports short battery life.", "citations": [{"review_id": "7", "evidence_quote": "Battery runs out early"}]}


def graph_with_mocks(monkeypatch, saver):
    monkeypatch.setattr(agent, 'retrieve', lambda state: {'evidence': EVIDENCE, 'stage': 'analyze_evidence'})
    monkeypatch.setattr(agent, 'analyze', lambda state: {'analysis': {'findings': [FINDING]}, 'stage': 'draft_report'})
    return agent.build_graph(saver)


def test_workflow_interrupt_and_resume_after_recompile(monkeypatch):
    saver = InMemorySaver()
    graph = graph_with_mocks(monkeypatch, saver)
    config = {'configurable': {'thread_id': str(uuid4())}}
    graph.invoke({'request': 'Investigate battery complaints', 'product_id': 'luna-smartwatch'}, config)
    paused = graph.get_state(config)
    assert paused.next == ('human_approval',)
    assert paused.values['report']['findings'] == [FINDING]
    graph = graph_with_mocks(monkeypatch, saver)
    graph.invoke(Command(resume={'decision': 'approve', 'notes': 'Reviewed'}), config)
    result = graph.get_state(config)
    assert not result.next and result.values['decision']['decision'] == 'approve'
    assert result.values['decision']['decided_at']


def test_invalid_quotes_and_single_review_patterns_fail_closed():
    base = {'evidence': EVIDENCE, 'analysis': {'findings': []}}
    assert agent.draft(base)['report']['evidence_status'] == 'insufficient evidence'
    for item in [{**FINDING, 'citations': [{'review_id': '7', 'evidence_quote': 'not in review'}]},
                 {**FINDING, 'kind': 'pattern'}, {**FINDING, 'text': '50% report this'}]:
        assert agent.draft({**base, 'analysis': {'findings': [item]}})['report']['evidence_status'] == 'insufficient evidence'


def test_quote_references_resolve_only_to_retrieved_evidence():
    good = {**FINDING, 'citations': [{'review_id': '7', 'quote_id': 'review_text'}]}
    invalid = [
        {**good, 'citations': [{'review_id': 'missing', 'quote_id': 'review_text'}]},
        {**good, 'citations': [{'review_id': '7', 'quote_id': 'missing'}]},
        {**good, 'citations': [{'review_id': '7', 'quote_id': 'title'}]},
        {**good, 'citations': [*good['citations'], {'review_id': 'missing', 'quote_id': 'review_text'}]},
    ]
    report = agent.draft({'evidence': EVIDENCE, 'analysis': {'findings': [good, *invalid]}})['report']
    assert report['findings'] == [FINDING]
    assert agent.draft({'evidence': EVIDENCE, 'analysis': {'findings': invalid}})['report']['evidence_status'] == 'insufficient evidence'


def test_endpoints_pause_and_record_revision(monkeypatch):
    saver = InMemorySaver()
    @contextmanager
    def memory_graph():
        yield graph_with_mocks(monkeypatch, saver)
    monkeypatch.setattr(api, 'graph_context', memory_graph)
    client = TestClient(app)
    response = client.post('/api/investigations', json={'request': 'Investigate battery complaints'})
    assert response.status_code == 201 and response.json()['status'] == 'awaiting_review'
    ident = response.json()['id']
    assert client.get(f'/api/investigations/{ident}').json()['report']['findings'] == [FINDING]
    monkeypatch.setattr(security, 'get_settings', lambda: SimpleNamespace(admin_token=SecretStr('test-admin-token')))
    assert client.post(f'/api/investigations/{ident}/decision', json={'decision': 'approve'}).status_code == 401
    assert client.post(f'/api/investigations/{ident}/decision', headers={'Authorization': 'Bearer wrong'}, json={'decision': 'approve'}).status_code == 401
    assert client.get('/api/investigations/authorization', headers={'Authorization': 'Bearer wrong'}).status_code == 401
    headers = {'Authorization': 'Bearer test-admin-token'}
    assert client.get('/api/investigations/authorization', headers=headers).status_code == 200
    decision = client.post(f'/api/investigations/{ident}/decision', headers=headers, json={'decision': 'request_revision', 'notes': 'More detail'})
    assert decision.json()['status'] == 'request_revision'
    assert decision.json()['stage'] == 'revision_requested'
    assert decision.json()['decision']['notes'] == 'More detail'
    assert client.post(f'/api/investigations/{ident}/decision', headers=headers, json={'decision': 'approve'}).status_code == 409
    assert client.get(f'/api/investigations/{uuid4()}').status_code == 404
    assert client.post('/api/investigations', json={'request': 'battery', 'product_id': 'other'}).status_code == 422


def test_analysis_uses_structured_model_and_original_evidence(monkeypatch):
    calls = []
    class MockGroq:
        def __init__(self, **kwargs):
            assert kwargs['model'] == 'openai/gpt-oss-20b'
        def with_structured_output(self, schema, **kwargs):
            assert schema is agent.Analysis and kwargs['strict'] is True
            return self
        def invoke(self, messages):
            calls.append(messages)
            return {'findings': [{**FINDING, 'citations': [{'review_id': '7', 'quote_id': 'review_text'}]}]}
    monkeypatch.setattr(agent, 'ChatGroq', MockGroq)
    monkeypatch.setattr(agent, 'get_settings', lambda: SimpleNamespace(groq_api_key='test-key', groq_model='openai/gpt-oss-20b'))
    result = agent.analyze({'request': 'battery', 'evidence': EVIDENCE})
    assert agent.draft({'evidence': EVIDENCE, **result})['report']['findings'] == [FINDING]
    assert 'Battery runs out early' in calls[0][1].content
    assert agent.analyze({'request': 'battery', 'evidence': []})['analysis']['findings'] == []
    assert len(calls) == 1


def test_investigation_timeout_is_sanitized(monkeypatch, caplog):
    class FailedGraph:
        def invoke(self, *args):
            raise TimeoutError('private credential and customer text')
        def get_state(self, *args):
            return SimpleNamespace(next=('analyze_evidence',))
    @contextmanager
    def failing_graph():
        yield FailedGraph()
    monkeypatch.setattr(api, 'graph_context', failing_graph)
    response = TestClient(app).post('/api/investigations', json={'request': 'battery'})
    assert response.status_code == 504
    assert 'private credential' not in response.text + caplog.text
    assert 'stage=analyze_evidence type=TimeoutError' in caplog.text
