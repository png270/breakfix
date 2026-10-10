"""Search security regressions: exercise the public endpoint, not SQL text."""
import pytest
from test_bookshelf import app, client


@pytest.mark.parametrize(('query', 'count'), [('Hobbit', 1), ('Le Guin', 3), ('hObBiT', 1), ('', 12), ('%', 12)])
def test_legitimate_search(client, query, count):
    response = client.get('/', query_string={'q': query})
    assert response.status_code == 200
    assert response.data.count(b'class="book-card"') == count


@pytest.mark.parametrize('payload', [
    "no-such-demo-book' OR 1=1 -- ",
    "' OR 1=1 --",
    "' OR '1'='1",
    "' UNION SELECT id, username, password_hash, bio, display_name FROM users -- ",
    "'; DROP TABLE books; --",
    "' OR 1=1 /*",
    "\" OR 1=1 --",
])
def test_injection_remains_search_data(app, client, payload):
    response = client.get('/', query_string={'q': payload})
    assert response.status_code == 200
    assert b'No books found' in response.data
    assert b'class="book-card"' not in response.data
    with app.app_context():
        assert app.get_db().execute('SELECT COUNT(*) FROM books').fetchone()[0] == 12


def test_apostrophe_search_matches_literal_title(app, client):
    title = "A Reader's Journey"
    with app.app_context():
        app.get_db().execute('INSERT INTO books (title, author, genre, description) VALUES (?, ?, ?, ?)', (title, 'Demo Author', 'Demo', 'Test-only book'))
        app.get_db().commit()
    response = client.get('/', query_string={'q': "Reader's"})
    assert response.status_code == 200
    assert response.data.count(b'class="book-card"') == 1
    assert b'A Reader&#39;s Journey' in response.data
