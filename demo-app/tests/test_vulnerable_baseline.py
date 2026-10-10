"""INTENTIONALLY VULNERABLE DEMO BASELINE: assertions confirm unsafe behavior.

These tests belong only to demo/vulnerable-bookshelf. They are expected to fail
once the respective security fix is complete. Payloads only read seeded books
or set an in-page marker; no external access or data exfiltration.
"""
from test_bookshelf import app, client, post, signup  # reuse isolated DB fixtures
from app import create_app

XSS_MARKER = '<script>document.documentElement.dataset.bookshelfXss="demo-only";</script>'


def test_demo_baseline_normal_search(client):
    response = client.get('/', query_string={'q': 'Hobbit'})
    assert response.status_code == 200
    assert b'The Hobbit' in response.data
    assert b'Dune' not in response.data
    assert b'The Dispossessed' in client.get('/', query_string={'q': 'Le Guin'}).data


def test_demo_baseline_sql_injection(client):
    assert b'No books found' in client.get('/', query_string={'q': 'no-such-demo-book'}).data
    response = client.get('/', query_string={'q': "no-such-demo-book' OR 1=1 -- "})
    assert response.status_code == 200
    assert response.data.count(b'class="book-card"') == 12
    assert b'The Hobbit' in response.data and b'Dune' in response.data


def test_demo_baseline_normal_review_persistence(app, client):
    signup(client)
    response = post(client, '/books/1/reviews', {'review_text': 'A thoughtful demo review.'})
    assert response.status_code == 200
    assert b'A thoughtful demo review.' in response.data
    assert b'reader' in response.data
    with app.app_context():
        row = app.get_db().execute('SELECT * FROM reviews').fetchone()
        assert row['user_id'] == 1 and row['book_id'] == 1 and row['created_at']
    restarted = create_app({'TESTING': True, 'SECRET_KEY': 'test-only', 'DATABASE': app.config['DATABASE']})
    assert b'A thoughtful demo review.' in restarted.test_client().get('/books/1').data


def test_demo_baseline_stored_xss_html(app, client):
    signup(client)
    response = post(client, '/books/1/reviews', {'review_text': XSS_MARKER})
    assert response.status_code == 200
    assert XSS_MARKER.encode() in response.data
    with app.app_context():
        assert app.get_db().execute('SELECT review_text FROM reviews').fetchone()[0] == XSS_MARKER
    # The persisted script is served to subsequent visitors, without login.
    assert XSS_MARKER.encode() in app.test_client().get('/books/1').data
    # Profile rendering remains escaped; only book-detail reviews were weakened.
    assert b'&lt;script&gt;' in client.get('/users/1').data
