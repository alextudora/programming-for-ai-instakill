import base64
import sqlite3
import math
from html.parser import HTMLParser

from scripts import evaluate


def make_db(path):
    with sqlite3.connect(path) as c:
        c.executescript('''
        CREATE TABLE user (id INTEGER PRIMARY KEY, username TEXT, created_at TEXT DEFAULT '2020-01-01T00:00:00Z');
        CREATE TABLE post (id INTEGER PRIMARY KEY, user_id INTEGER, content TEXT, created_at TEXT);
        CREATE TABLE follow (follower_id INTEGER, followee_id INTEGER, created_at TEXT);
        CREATE TABLE "like" (user_id INTEGER, post_id INTEGER, created_at TEXT);
        INSERT INTO user(id,username) VALUES (1,'a'),(2,'b');
        INSERT INTO post VALUES (1,2,'old1','2020-01-01T00:00:00Z'),(2,2,'old2','2020-01-02T00:00:00Z'),
          (3,2,'old3','2020-01-03T00:00:00Z'),(4,2,'future','2020-01-04T00:00:00Z'),(5,2,'post-after','2021-01-01T00:00:00Z'),
          (6,1,'own post','2020-01-05T00:00:00Z');
        INSERT INTO "like" VALUES (1,1,'2020-02-01T00:00:00Z'),(1,2,'2020-02-02T00:00:00Z'),
          (1,3,'2020-02-03T00:00:00Z'),(1,4,'2020-03-01T00:00:00Z'),(1,6,'2020-03-02T00:00:00Z');
        INSERT INTO follow VALUES (1,2,'2020-02-01T00:00:00Z'),(2,1,'2020-04-01T00:00:00Z');
        ''')


def test_ndcg_at_10_handmade_rankings():
    assert evaluate.ndcg_at_10([1, 2], {3}) == 0
    assert evaluate.ndcg_at_10([1, 2], {1, 2}) == 1
    assert math.isclose(evaluate.ndcg_at_10([8, 9, 7, 3], {3}), 1 / math.log2(5))


def test_snapshot_removes_rows_at_or_after_cutoff(tmp_path):
    source, snap = tmp_path / 'source.db', tmp_path / 'snapshot.db'
    make_db(source)
    evaluate.create_snapshot(source, snap, '2020-03-01T00:00:00Z')
    with sqlite3.connect(snap) as c:
        assert c.execute('SELECT count(*) FROM "like" WHERE julianday(created_at)>=julianday(?)', ('2020-03-01T00:00:00Z',)).fetchone()[0] == 0
        assert c.execute('SELECT count(*) FROM post WHERE julianday(created_at)>=julianday(?)', ('2020-03-01T00:00:00Z',)).fetchone()[0] == 0
        assert c.execute('SELECT count(*) FROM follow WHERE julianday(created_at)>=julianday(?)', ('2020-03-01T00:00:00Z',)).fetchone()[0] == 0
        assert c.execute('SELECT count(*) FROM user WHERE julianday(created_at)>=julianday(?)', ('2020-03-01T00:00:00Z',)).fetchone()[0] == 0


def test_evaluation_is_deterministic_and_calls_feed_service(tmp_path, monkeypatch):
    db = tmp_path / 'fixture.db'
    make_db(db)
    monkeypatch.setattr(evaluate, 'load_model', lambda: True)
    calls = []

    def fake_feed(self, user_id, limit, strategy, now, db_path):
        calls.append((user_id, strategy, now.isoformat(), db_path))
        return [{'post_id': 4}]

    monkeypatch.setattr(evaluate.PostService, 'get_feed', fake_feed)
    out1, out2 = tmp_path / 'one', tmp_path / 'two'
    evaluate.evaluate(db, '2020-03-01T00:00:00Z', 42, out1)
    first = (out1 / 'eval_results.csv').read_bytes()
    first_table = (out1 / 'baseline_table.md').read_bytes()
    evaluate.evaluate(db, '2020-03-01T00:00:00Z', 42, out2)
    assert first == (out2 / 'eval_results.csv').read_bytes()
    assert first_table == (out2 / 'baseline_table.md').read_bytes()
    csv_rows = (out1 / 'eval_results.csv').read_text(encoding='utf-8').splitlines()
    user_rows = [line for line in csv_rows[1:] if line.startswith('1,')]
    assert len(user_rows) == 4
    assert all(line.split(',')[3] == '2' for line in user_rows)
    assert len(calls) == 6
    assert {call[1] for call in calls} == {'chronological', 'for_you', 'learned'}

    class ImageSourceParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.sources = []
            self.table_count = 0

        def handle_starttag(self, tag, attrs):
            if tag == 'img':
                self.sources.append(dict(attrs).get('src', ''))
            elif tag == 'table':
                self.table_count += 1

    parser = ImageSourceParser()
    parser.feed((out1 / 'dashboard.html').read_text(encoding='utf-8'))
    assert len(parser.sources) == 3
    assert parser.table_count == 2
    for src in parser.sources:
        assert src.startswith('data:image/png;base64,')
        png = base64.b64decode(src.split(',', 1)[1], validate=True)
        assert png.startswith(b'\x89PNG\r\n\x1a\n')
