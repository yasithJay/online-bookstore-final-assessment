import sys
import os
import pytest

# Add the parent directory to sys.path so imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, BOOKS, cart, users, get_book_by_title
from models import Book, Cart, User, Order, PaymentGateway, EmailService

import pytest
from flask import session
import timeit
import cProfile

# Configure Flask for testing
app.config['TESTING'] = True
app.config['SECRET_KEY'] = 'test_secret'

@pytest.fixture
def client():
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess.clear()
        yield client



# ===========================
# FR-001: Book Catalog Tests
# ===========================

def test_books_loaded():
    # TC001-01: Ensure books are loaded in catalog
    assert len(BOOKS) > 0
    for book in BOOKS:
        assert isinstance(book.title, str)
        assert isinstance(book.price, float)

def test_get_book_by_title_exists():
    # TC001-02: get_book_by_title returns correct book
    book = get_book_by_title("1984")
    assert book is not None
    assert book.title == "1984"

def test_get_book_by_title_not_exists():
    # TC001-03: get_book_by_title returns None if not found
    book = get_book_by_title("Nonexistent Book")
    assert book is None
