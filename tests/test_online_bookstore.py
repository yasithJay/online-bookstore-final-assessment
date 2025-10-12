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

# ===========================
# FR-002: Cart Functionality
# ===========================

def test_add_to_cart(client):
    # TC002-01: Add book to cart
    client.post('/add-to-cart', data={'title': '1984', 'quantity': 2})
    assert '1984' in cart.items
    assert cart.items['1984'].quantity == 2

def test_add_invalid_quantity(client):
    # TC002-02: Edge case - invalid quantity input (non-integer)
    response = client.post('/add-to-cart', data={'title': '1984', 'quantity': 'abc'})
    # Should handle error and not crash
    assert response.status_code == 302  # Redirects back to index

def test_remove_from_cart(client):
    # TC002-03: Remove book from cart
    cart.add_book(BOOKS[0], 1)
    client.post('/remove-from-cart', data={'title': BOOKS[0].title})
    assert BOOKS[0].title not in cart.items

def test_update_cart_quantity(client):
    # TC002-04: Update quantity of a book
    cart.add_book(BOOKS[0], 1)
    client.post('/update-cart', data={'title': BOOKS[0].title, 'quantity': 5})
    assert cart.items[BOOKS[0].title].quantity == 5

def test_update_cart_zero_quantity(client):
    # TC002-05: Edge case - quantity zero removes item (intentional bug)
    cart.add_book(BOOKS[0], 1)
    client.post('/update-cart', data={'title': BOOKS[0].title, 'quantity': 0})
    # Bug: Cart.update_quantity doesn't remove item
    assert cart.items[BOOKS[0].title].quantity == 0

def test_clear_cart(client):
    # TC002-06: Clear the cart
    cart.add_book(BOOKS[0], 1)
    client.post('/clear-cart')
    assert cart.is_empty()

# ===========================
# FR-003: Checkout & Discounts
# ===========================

def test_checkout_empty_cart(client):
    # TC003-01: Checkout should fail if cart is empty
    cart.clear()
    response = client.get('/checkout')
    assert response.status_code == 302  # Redirect to index

def test_apply_discount_code_case_sensitive(client):
    # TC003-02: Discount code 'SAVE10' should be applied correctly (intentional bug: case-sensitive)
    cart.add_book(BOOKS[0], 1)
    response = client.post('/process-checkout', data={
        'name': 'John Doe',
        'email': 'test@example.com',
        'address': '123 Street',
        'city': 'City',
        'zip_code': '12345',
        'payment_method': 'credit_card',
        'card_number': '1234567890123456',
        'expiry_date': '12/25',
        'cvv': '123',
        'discount_code': 'save10'  # lower case
    }, follow_redirects=True)
    # Bug: Discount won't apply due to case sensitivity
    assert b'Invalid discount code' in response.data

def test_apply_discount_code_uppercase(client):
    # TC003-03: Discount code 'SAVE10' applies correctly
    cart.add_book(BOOKS[0], 1)
    response = client.post('/process-checkout', data={
        'name': 'John Doe',
        'email': 'test@example.com',
        'address': '123 Street',
        'city': 'City',
        'zip_code': '12345',
        'payment_method': 'credit_card',
        'card_number': '1234567890123456',
        'expiry_date': '12/25',
        'cvv': '123',
        'discount_code': 'SAVE10'
    }, follow_redirects=True)
    assert b'Discount applied!' in response.data

# ===========================
# FR-004: Payment Processing
# ===========================

def test_payment_success():
    # TC004-01: Payment succeeds for valid card
    result = PaymentGateway.process_payment({
        'payment_method': 'credit_card',
        'card_number': '1234567890123456',
        'expiry_date': '12/25',
        'cvv': '123'
    })
    assert result['success'] is True
    assert result['transaction_id'] is not None

def test_payment_failure():
    # TC004-02: Payment fails for card ending with 1111
    result = PaymentGateway.process_payment({
        'payment_method': 'credit_card',
        'card_number': '123456781111',
        'expiry_date': '12/25',
        'cvv': '123'
    })
    assert result['success'] is False

# ===========================
# FR-005: Order Confirmation
# ===========================

def test_order_confirmation_creation():
    # TC005-01: Order object stores correct info
    order = Order(
        order_id='ORD123',
        user_email='test@example.com',
        items=[cart.add_book(BOOKS[0], 1) or cart.items[BOOKS[0].title]],
        shipping_info={'name': 'John', 'email': 'a@b.com', 'address': 'Addr', 'city': 'City', 'zip_code': '123'},
        payment_info={'method': 'credit_card', 'transaction_id': 'TXN123'},
        total_amount=BOOKS[0].price
    )
    assert order.user_email == 'test@example.com'
    assert order.items[0].book.title == BOOKS[0].title

# ===========================
# FR-006: User Account Management
# ===========================

def test_register_user(client):
    # TC006-01: Register new user
    response = client.post('/register', data={
        'email': 'newuser@example.com',
        'password': 'password',
        'name': 'New User'
    }, follow_redirects=True)
    assert b'Account created successfully' in response.data
    assert 'newuser@example.com' in users

def test_register_duplicate_email_case(client):
    # TC006-02: Duplicate email check (intentional bug: case-sensitive)
    response = client.post('/register', data={
        'email': 'DEMO@bookstore.com',  # Different case than demo@bookstore.com
        'password': 'password',
        'name': 'Demo'
    }, follow_redirects=True)
    # Bug allows duplicate because of case sensitivity
    assert b'Account created successfully' in response.data

def test_login_logout_user(client):
    # TC006-03: Login and logout user
    response = client.post('/login', data={'email': 'demo@bookstore.com', 'password': 'demo123'}, follow_redirects=True)
    assert b'Logged in successfully' in response.data
    response = client.get('/logout', follow_redirects=True)
    assert b'Logged out successfully' in response.data

# ===========================
# FR-007: Responsive / Usability Placeholder
# ===========================
# Note: Automated UI testing not included, normally use Selenium or Playwright

# ===========================
# Performance Tests
# ===========================

def test_cart_total_performance():
    # TC-P01: Measure cart total price calculation for performance
    cart.clear()
    for i in range(1000):
        cart.add_book(BOOKS[0], 1)
    time_taken = timeit.timeit(lambda: cart.get_total_price(), number=10)
    print(f"Time to calculate total price 10x for 1000 items: {time_taken:.4f} seconds")
    assert time_taken < 1  # Should not take more than 1 second

def test_order_history_profile():
    # TC-P02: Profile user order history retrieval
    user = users['demo@bookstore.com']
    profiler = cProfile.Profile()
    profiler.enable()
    _ = user.get_order_history()
    profiler.disable()
    profiler.print_stats(0)

# ===========================
# Security Tests
# ===========================

def test_password_storage_security():
    # TC-S01: Check passwords stored as plain text (intentional bug)
    user = users['demo@bookstore.com']
    assert user.password == 'demo123'  # Bug: passwords are plain text

def test_email_case_insensitive_security(client):
    # TC-S02: Register email in different case should not allow duplicate (intentional bug)
    client.post('/register', data={
        'email': 'Demo@Bookstore.com',
        'password': 'pass',
        'name': 'Demo2'
    }, follow_redirects=True)
    # Bug: duplicate user allowed due to case sensitivity
    assert 'Demo@Bookstore.com' in users

