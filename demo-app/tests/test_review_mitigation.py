"""Review mitigation tests, including a controlled local bypass demonstration."""
import pytest
from test_bookshelf import app, client, post, signup
from app import create_app


@pytest.mark.parametrize('review', ['A thoughtful review.', '<em>A thoughtful review.</em>'])
def test_normal_reviews_remain_visible(client, review):
    signup(client)
    response = post(client, '/books/1/reviews', {'review_text': review})
    assert response.status_code == 200
    assert review.encode() in response.data


@pytest.mark.parametrize('script', [
    '<script>document.documentElement.dataset.basicScript="demo";</script>',
    '<SCRIPT type="text/javascript">\ndocument.documentElement.dataset.basicScript="demo";\n</SCRIPT>',
])
def test_basic_script_elements_removed_including_existing_reviews(app, client, script):
    signup(client)
    post(client, '/books/1/reviews', {'review_text': 'Before' + script + 'After'})
    response = app.test_client().get('/books/1')
    assert response.status_code == 200
    assert b'basicScript' not in response.data
    assert b'BeforeAfter' in response.data
    with app.app_context():
        assert script in app.get_db().execute('SELECT review_text FROM reviews').fetchone()[0]


def test_controlled_demo_event_handler_bypass_persists(app, client):
    # Harmless executable SVG handler: page marker only, no network or data access.
    payload = '<svg onload="document.documentElement.dataset.bookshelfBypass=\'demo-only\'"></svg>'
    signup(client)
    response = post(client, '/books/1/reviews', {'review_text': payload})
    assert response.status_code == 200
    assert payload.encode() in response.data
    restarted = create_app({'TESTING': True, 'SECRET_KEY': 'test-only', 'DATABASE': app.config['DATABASE']})
    assert payload.encode() in restarted.test_client().get('/books/1').data
    assert b'&lt;svg' in client.get('/users/1').data
