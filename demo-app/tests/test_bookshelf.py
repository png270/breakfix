import re
import sys
from pathlib import Path

import pytest
from werkzeug.security import check_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app


@pytest.fixture
def app(tmp_path):
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test-only', 'DATABASE': str(tmp_path / 'test.sqlite3')})
    result = app.test_cli_runner().invoke(args=['init-db'])
    assert result.exit_code == 0
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def post(client, path, data=None):
    client.get('/')
    with client.session_transaction() as session:
        token = session['csrf_token']
    return client.post(path, data={**(data or {}), 'csrf_token': token}, follow_redirects=True)


def signup(client, username='reader'):
    return post(client, '/signup', {'username': username, 'password': 'long-password'})


def test_catalog_seed_and_foreign_keys(app, client):
    assert b'Stories worth exploring' in client.get('/').data
    result = app.test_cli_runner().invoke(args=['init-db'])
    assert result.exit_code == 0
    with app.app_context():
        assert app.get_db().execute('SELECT COUNT(*) FROM books').fetchone()[0] == 12
        assert app.get_db().execute('PRAGMA foreign_keys').fetchone()[0] == 1
    assert client.get('/books/1').status_code == 200
    assert client.get('/books/999').status_code == 404


def test_signup_password_hash_and_session(app, client):
    assert b'Make it yours' in signup(client).data
    with app.app_context():
        user = app.get_db().execute('SELECT * FROM users').fetchone()
        assert user['password_hash'] != 'long-password'
        assert check_password_hash(user['password_hash'], 'long-password')
    with client.session_transaction() as session:
        assert session['user_id'] == 1
    assert b'already taken' in signup(client).data


def test_validation(client):
    assert b'3' in post(client, '/signup', {'username': 'x', 'password': 'short'}).data
    assert b'Invalid username or password' in post(client, '/login', {'username': "' OR 1=1 --", 'password': 'wrong'}).data
    signup(client)
    assert b'Profile saved' not in post(client, '/users/1/edit', {'display_name': '', 'bio': ''}).data
    assert b'between 1 and 5,000' in post(client, '/books/1/reviews', {'review_text': ' '}).data
    assert b'between 1 and 5,000' in post(client, '/books/1/reviews', {'review_text': 'x' * 5001}).data


def test_login_logout(client):
    signup(client)
    post(client, '/logout')
    with client.session_transaction() as session:
        assert 'user_id' not in session
    assert b'Invalid username or password' in post(client, '/login', {'username': 'reader', 'password': 'wrong'}).data
    assert b'My profile' in post(client, '/login', {'username': 'reader', 'password': 'long-password'}).data
    assert client.get('/logout').status_code == 405


def test_profile_ownership_and_escaping(app, client):
    signup(client)
    response = post(client, '/users/1/edit', {'display_name': '<b>Reader</b>', 'bio': '<script>alert(1)</script>', 'favorite_genre': 'Fantasy'})
    assert b'&lt;b&gt;Reader&lt;/b&gt;' in response.data
    assert b'&lt;script&gt;' in response.data
    post(client, '/logout')
    signup(client, 'other')
    assert client.get('/users/1/edit').status_code == 403
    assert post(client, '/users/1/edit', {'display_name': 'Overwritten'}).status_code == 403
    with app.app_context():
        assert app.get_db().execute('SELECT display_name FROM users WHERE id = 1').fetchone()[0] == '<b>Reader</b>'
    assert client.get('/users/999').status_code == 404


def test_unauthenticated_writes(app, client):
    assert b'Log in to continue' in post(client, '/books/1/reviews', {'review_text': 'unauthorized'}).data
    assert client.get('/users/1/edit').status_code == 302
    with app.app_context():
        assert app.get_db().execute('SELECT COUNT(*) FROM reviews').fetchone()[0] == 0


def test_search_treats_sql_as_data(app, client):
    assert b'The Hobbit' in client.get('/?q=Hobbit').data
    assert b'The Dispossessed' in client.get('/?q=Le+Guin').data
    for payload in ["' OR 1=1 --", "'; DROP TABLE books; --"]:
        response = client.get('/', query_string={'q': payload})
        assert b'No books found' in response.data
    with app.app_context():
        assert app.get_db().execute('SELECT COUNT(*) FROM books').fetchone()[0] == 12


def test_reviews_escape_and_persist_after_restart(app, client):
    signup(client)
    payload = '<script>alert("xss")</script><img src=x onerror=alert(1)>'
    response = post(client, '/books/1/reviews', {'review_text': payload, 'user_id': 99})
    assert payload.encode() not in response.data
    assert b'&lt;script&gt;' in response.data and b'&lt;img' in response.data
    with app.app_context():
        review = app.get_db().execute('SELECT * FROM reviews').fetchone()
        assert review['user_id'] == 1
        assert review['review_text'] == payload
        assert re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', review['created_at'])
    restarted = create_app({'TESTING': True, 'SECRET_KEY': 'test-only', 'DATABASE': app.config['DATABASE']})
    assert b'&lt;script&gt;' in restarted.test_client().get('/books/1').data
    assert b'&lt;script&gt;' in client.get('/users/1').data
    assert post(client, '/books/999/reviews', {'review_text': 'hello'}).status_code == 404


def test_csrf_protects_mutations(client):
    assert client.post('/signup', data={'username': 'reader', 'password': 'long-password'}).status_code == 400
    signup(client)
    assert client.post('/users/1/edit', data={'display_name': 'Forged'}).status_code == 400
    assert client.post('/books/1/reviews', data={'review_text': 'Forged', 'csrf_token': 'bad'}).status_code == 400
    assert client.post('/logout').status_code == 400
