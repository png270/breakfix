"""BookShelf: a local, authorized security-testing demo."""
import os
import re
import secrets
import sqlite3
from functools import wraps
from pathlib import Path

import click
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BOOKS = [
    ('The Left Hand of Darkness', 'Ursula K. Le Guin', 'Science fiction', 'An envoy on a winter world discovers new ways of thinking about identity and belonging.'),
    ('Pride and Prejudice', 'Jane Austen', 'Classic', 'Wit, first impressions and unexpected affection in the English countryside.'),
    ('The Hobbit', 'J. R. R. Tolkien', 'Fantasy', 'A reluctant adventurer leaves home for a journey of dragons and discovery.'),
    ('Beloved', 'Toni Morrison', 'Literary fiction', 'A powerful story of memory, family and the enduring weight of the past.'),
    ('Dune', 'Frank Herbert', 'Science fiction', 'Power, ecology and prophecy collide on a desert planet.'),
    ('The Secret History', 'Donna Tartt', 'Mystery', 'A close circle of classics students becomes entangled in a dark secret.'),
    ('A Wizard of Earthsea', 'Ursula K. Le Guin', 'Fantasy', 'A young magician learns that power requires responsibility.'),
    ('Jane Eyre', 'Charlotte Brontë', 'Classic', 'An independent woman searches for love without surrendering herself.'),
    ('The Ocean at the End of the Lane', 'Neil Gaiman', 'Fantasy', 'Childhood memories open a door into a strange and luminous world.'),
    ('Frankenstein', 'Mary Shelley', 'Classic', 'An ambitious scientist confronts the consequences of creating life.'),
    ('The Murder of Roger Ackroyd', 'Agatha Christie', 'Mystery', 'Hercule Poirot investigates a murder in a quiet English village.'),
    ('The Dispossessed', 'Ursula K. Le Guin', 'Science fiction', 'A physicist crosses between two societies in search of freedom and understanding.'),
]
SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
 password_hash TEXT NOT NULL, display_name TEXT NOT NULL,
 bio TEXT NOT NULL DEFAULT '', favorite_genre TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS books (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, author TEXT NOT NULL,
 genre TEXT NOT NULL, description TEXT NOT NULL, UNIQUE(title, author)
);
CREATE TABLE IF NOT EXISTS reviews (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 book_id INTEGER NOT NULL REFERENCES books(id), review_text TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
'''


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('BOOKSHELF_SECRET_KEY', 'bookshelf-local-development-only'),
        DATABASE=str(Path(__file__).parent / 'bookshelf.sqlite3'),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.environ.get('BOOKSHELF_COOKIE_SECURE') == '1',
        MAX_CONTENT_LENGTH=64 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    def db():
        if 'db' not in g:
            g.db = sqlite3.connect(app.config['DATABASE'])
            g.db.row_factory = sqlite3.Row
            g.db.execute('PRAGMA foreign_keys = ON')
        return g.db

    app.get_db = db

    @app.teardown_appcontext
    def close_db(error):
        connection = g.pop('db', None)
        if connection is not None:
            connection.close()

    @app.cli.command('init-db')
    def init_db():
        db().executescript(SCHEMA)
        db().executemany('INSERT OR IGNORE INTO books (title, author, genre, description) VALUES (?, ?, ?, ?)', BOOKS)
        db().commit()
        click.echo('Database initialized; 12-book catalog seeded without duplicates.')

    @app.before_request
    def load_user_and_check_csrf():
        g.user = db().execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone() if session.get('user_id') else None
        if request.method == 'POST':
            expected = session.get('csrf_token')
            if not expected or not secrets.compare_digest(expected, request.form.get('csrf_token', '')):
                abort(400, 'Invalid form token. Reload the page and try again.')

    @app.context_processor
    def template_context():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(32)
        return {'csrf_token': session['csrf_token']}

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                flash('Log in to continue.', 'error')
                return redirect(url_for('login'))
            return view(*args, **kwargs)
        return wrapped

    @app.get('/')
    def browse():
        query = request.args.get('q', '').strip()[:200]
        # Bind search input as data; keep LIKE substring/wildcard behavior.
        books = db().execute(
            "SELECT * FROM books WHERE title LIKE ? OR author LIKE ? ORDER BY title",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()
        return render_template('browse.html', books=books, query=query)

    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        if request.method == 'POST':
            username = request.form.get('username', '').strip().lower()
            password = request.form.get('password', '')
            if not re.fullmatch(r'[a-z0-9_]{3,30}', username) or not 8 <= len(password) <= 128:
                flash('Use a username of 3–30 letters, numbers or underscores and a password of 8–128 characters.', 'error')
            else:
                try:
                    cursor = db().execute('INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)', (username, generate_password_hash(password), username))
                    db().commit()
                except sqlite3.IntegrityError:
                    flash('That username is already taken.', 'error')
                else:
                    session.clear()
                    session['user_id'] = cursor.lastrowid
                    flash('Welcome to your next chapter. Make your profile yours.', 'success')
                    return redirect(url_for('edit_profile', user_id=cursor.lastrowid))
        return render_template('auth.html', signup=True)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            user = db().execute('SELECT * FROM users WHERE username = ?', (request.form.get('username', '').strip().lower(),)).fetchone()
            password = request.form.get('password', '')
            if user and len(password) <= 128 and check_password_hash(user['password_hash'], password):
                session.clear()
                session['user_id'] = user['id']
                return redirect(url_for('browse'))
            flash('Invalid username or password.', 'error')
        return render_template('auth.html', signup=False)

    @app.post('/logout')
    def logout():
        session.clear()
        return redirect(url_for('browse'))

    @app.get('/users/<int:user_id>')
    def profile(user_id):
        user = db().execute('SELECT id, username, display_name, bio, favorite_genre FROM users WHERE id = ?', (user_id,)).fetchone()
        if user is None:
            abort(404)
        reviews = db().execute('SELECT reviews.*, books.title FROM reviews JOIN books ON books.id = reviews.book_id WHERE user_id = ? ORDER BY created_at DESC, reviews.id DESC', (user_id,)).fetchall()
        return render_template('profile.html', user=user, reviews=reviews)

    @app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_profile(user_id):
        if user_id != g.user['id']:
            abort(403)
        if request.method == 'POST':
            name = request.form.get('display_name', '').strip()
            bio = request.form.get('bio', '').strip()
            genre = request.form.get('favorite_genre', '').strip()
            if not 1 <= len(name) <= 60 or len(bio) > 500 or len(genre) > 60:
                flash('Display name is required (up to 60 characters); bio up to 500; genre up to 60.', 'error')
            else:
                db().execute('UPDATE users SET display_name = ?, bio = ?, favorite_genre = ? WHERE id = ?', (name, bio, genre, g.user['id']))
                db().commit()
                flash('Profile saved.', 'success')
                return redirect(url_for('profile', user_id=user_id))
        return render_template('edit_profile.html')

    @app.get('/books/<int:book_id>')
    def book_detail(book_id):
        book = db().execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
        if book is None:
            abort(404)
        reviews = db().execute('SELECT reviews.*, users.display_name FROM reviews JOIN users ON users.id = reviews.user_id WHERE book_id = ? ORDER BY created_at DESC, reviews.id DESC', (book_id,)).fetchall()
        return render_template('book.html', book=book, reviews=reviews)

    @app.post('/books/<int:book_id>/reviews')
    @login_required
    def add_review(book_id):
        if db().execute('SELECT id FROM books WHERE id = ?', (book_id,)).fetchone() is None:
            abort(404)
        review = request.form.get('review_text', '').strip()
        if not 1 <= len(review) <= 5000:
            flash('Write a review between 1 and 5,000 characters.', 'error')
        else:
            db().execute('INSERT INTO reviews (user_id, book_id, review_text) VALUES (?, ?, ?)', (g.user['id'], book_id, review))
            db().commit()
            flash('Your review is on the shelf.', 'success')
        return redirect(url_for('book_detail', book_id=book_id))

    return app


app = create_app()
