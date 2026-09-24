import os
from datetime import date, timedelta

from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

# --------------------------------------------------------------------------
# App / Config
# --------------------------------------------------------------------------
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

DEFAULT_LOAN_DAYS = 14

# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    role = db.Column(db.String(20), nullable=False)  # admin, librarian, student
    created_at = db.Column(db.Date, default=date.today)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(150), nullable=False)
    isbn = db.Column(db.String(30), unique=True)
    category = db.Column(db.String(80))
    quantity = db.Column(db.Integer, default=1, nullable=False)
    added_on = db.Column(db.Date, default=date.today)

    @property
    def available_copies(self):
        active_issues = IssueRecord.query.filter_by(book_id=self.id, status='issued').count()
        return self.quantity - active_issues


class IssueRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    issued_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    issue_date = db.Column(db.Date, default=date.today)
    due_date = db.Column(db.Date)
    return_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='issued')  # issued, returned

    book = db.relationship('Book', backref='issue_records')
    student = db.relationship('User', foreign_keys=[student_id])
    librarian = db.relationship('User', foreign_keys=[issued_by])

    @property
    def is_overdue(self):
        return self.status == 'issued' and self.due_date and date.today() > self.due_date


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --------------------------------------------------------------------------
# Access control helpers
# --------------------------------------------------------------------------
def roles_required(*roles):
    from functools import wraps

    def decorator(f):
        @wraps(f)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                flash('You do not have permission to access that page.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return wrapped
    return decorator


# --------------------------------------------------------------------------
# Auth routes
# --------------------------------------------------------------------------
@app.route('/', methods=['GET'])
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif current_user.role == 'librarian':
        return redirect(url_for('librarian_dashboard'))
    else:
        return redirect(url_for('student_dashboard'))


# --------------------------------------------------------------------------
# Dashboards
# --------------------------------------------------------------------------
@app.route('/admin/dashboard')
@roles_required('admin')
def admin_dashboard():
    stats = {
        'total_books': Book.query.count(),
        'total_copies': db.session.query(db.func.sum(Book.quantity)).scalar() or 0,
        'total_students': User.query.filter_by(role='student').count(),
        'total_librarians': User.query.filter_by(role='librarian').count(),
        'books_issued': IssueRecord.query.filter_by(status='issued').count(),
        'overdue': len([r for r in IssueRecord.query.filter_by(status='issued').all() if r.is_overdue]),
    }
    recent_issues = IssueRecord.query.order_by(IssueRecord.issue_date.desc()).limit(8).all()
    return render_template('admin_dashboard.html', stats=stats, recent_issues=recent_issues)


@app.route('/librarian/dashboard')
@roles_required('librarian', 'admin')
def librarian_dashboard():
    stats = {
        'total_books': Book.query.count(),
        'books_issued': IssueRecord.query.filter_by(status='issued').count(),
        'overdue': len([r for r in IssueRecord.query.filter_by(status='issued').all() if r.is_overdue]),
        'total_students': User.query.filter_by(role='student').count(),
    }
    active_issues = IssueRecord.query.filter_by(status='issued').order_by(IssueRecord.due_date).all()
    return render_template('librarian_dashboard.html', stats=stats, active_issues=active_issues)


@app.route('/student/dashboard')
@roles_required('student')
def student_dashboard():
    my_issues = IssueRecord.query.filter_by(student_id=current_user.id, status='issued').all()
    history_count = IssueRecord.query.filter_by(student_id=current_user.id).count()
    total_books = Book.query.count()
    return render_template('student_dashboard.html', my_issues=my_issues,
                            history_count=history_count, total_books=total_books)


# --------------------------------------------------------------------------
# Book management
# --------------------------------------------------------------------------
@app.route('/books')
@login_required
def books():
    query = request.args.get('q', '').strip()
    if query:
        like = f'%{query}%'
        all_books = Book.query.filter(
            db.or_(Book.title.ilike(like), Book.author.ilike(like), Book.isbn.ilike(like))
        ).order_by(Book.title).all()
    else:
        all_books = Book.query.order_by(Book.title).all()
    return render_template('books.html', books=all_books, query=query)


@app.route('/books/add', methods=['GET', 'POST'])
@roles_required('admin', 'librarian')
def add_book():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        isbn = request.form.get('isbn', '').strip() or None
        category = request.form.get('category', '').strip()
        quantity = request.form.get('quantity', '1')

        if not title or not author:
            flash('Title and author are required.', 'danger')
            return render_template('add_book.html')

        if isbn and Book.query.filter_by(isbn=isbn).first():
            flash('A book with that ISBN already exists.', 'danger')
            return render_template('add_book.html')

        book = Book(title=title, author=author, isbn=isbn, category=category,
                    quantity=int(quantity) if quantity.isdigit() else 1)
        db.session.add(book)
        db.session.commit()
        flash(f'"{title}" was added to the catalog.', 'success')
        return redirect(url_for('books'))

    return render_template('add_book.html')


@app.route('/books/edit/<int:book_id>', methods=['GET', 'POST'])
@roles_required('admin', 'librarian')
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)

    if request.method == 'POST':
        book.title = request.form.get('title', book.title).strip()
        book.author = request.form.get('author', book.author).strip()
        book.isbn = request.form.get('isbn', book.isbn).strip() or None
        book.category = request.form.get('category', book.category).strip()
        quantity = request.form.get('quantity', str(book.quantity))
        book.quantity = int(quantity) if quantity.isdigit() else book.quantity

        db.session.commit()
        flash(f'"{book.title}" was updated.', 'success')
        return redirect(url_for('books'))

    return render_template('edit_book.html', book=book)


@app.route('/books/delete/<int:book_id>', methods=['POST'])
@roles_required('admin', 'librarian')
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)
    if IssueRecord.query.filter_by(book_id=book.id, status='issued').first():
        flash('Cannot delete a book that currently has copies issued.', 'danger')
        return redirect(url_for('books'))

    db.session.delete(book)
    db.session.commit()
    flash('Book removed from catalog.', 'info')
    return redirect(url_for('books'))


# --------------------------------------------------------------------------
# Issue / return
# --------------------------------------------------------------------------
@app.route('/issue', methods=['GET', 'POST'])
@roles_required('admin', 'librarian')
def issue_book():
    students = User.query.filter_by(role='student').order_by(User.full_name).all()
    available_books = [b for b in Book.query.order_by(Book.title).all() if b.available_copies > 0]

    if request.method == 'POST':
        book_id = request.form.get('book_id')
        student_id = request.form.get('student_id')
        days = request.form.get('days', str(DEFAULT_LOAN_DAYS))
        days = int(days) if days.isdigit() else DEFAULT_LOAN_DAYS

        book = Book.query.get(book_id)
        student = User.query.get(student_id)

        if not book or not student:
            flash('Please select a valid book and student.', 'danger')
        elif book.available_copies <= 0:
            flash('No copies of that book are currently available.', 'danger')
        else:
            record = IssueRecord(
                book_id=book.id,
                student_id=student.id,
                issued_by=current_user.id,
                issue_date=date.today(),
                due_date=date.today() + timedelta(days=days),
                status='issued'
            )
            db.session.add(record)
            db.session.commit()
            flash(f'"{book.title}" issued to {student.full_name}.', 'success')
            return redirect(url_for('issue_book'))

    return render_template('issue_book.html', students=students, books=available_books,
                            default_days=DEFAULT_LOAN_DAYS)


@app.route('/return/<int:record_id>', methods=['POST'])
@roles_required('admin', 'librarian')
def return_book(record_id):
    record = IssueRecord.query.get_or_404(record_id)
    if record.status == 'issued':
        record.status = 'returned'
        record.return_date = date.today()
        db.session.commit()
        flash(f'"{record.book.title}" marked as returned.', 'success')
    return redirect(request.referrer or url_for('librarian_dashboard'))


# --------------------------------------------------------------------------
# People management (admin only)
# --------------------------------------------------------------------------
@app.route('/students', methods=['GET', 'POST'])
@roles_required('admin')
def students():
    if request.method == 'POST':
        _create_user('student')
        return redirect(url_for('students'))

    all_students = User.query.filter_by(role='student').order_by(User.full_name).all()
    return render_template('students.html', students=all_students)


@app.route('/students/delete/<int:user_id>', methods=['POST'])
@roles_required('admin')
def delete_student(user_id):
    _delete_user(user_id, 'student')
    return redirect(url_for('students'))


@app.route('/librarians', methods=['GET', 'POST'])
@roles_required('admin')
def librarians():
    if request.method == 'POST':
        _create_user('librarian')
        return redirect(url_for('librarians'))

    all_librarians = User.query.filter_by(role='librarian').order_by(User.full_name).all()
    return render_template('librarians.html', librarians=all_librarians)


@app.route('/librarians/delete/<int:user_id>', methods=['POST'])
@roles_required('admin')
def delete_librarian(user_id):
    _delete_user(user_id, 'librarian')
    return redirect(url_for('librarians'))


def _create_user(role):
    username = request.form.get('username', '').strip()
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')

    if not username or not full_name or not password:
        flash('Username, full name, and password are required.', 'danger')
        return

    if User.query.filter_by(username=username).first():
        flash('That username is already taken.', 'danger')
        return

    user = User(username=username, full_name=full_name, email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f'{role.capitalize()} account created for {full_name}.', 'success')


def _delete_user(user_id, role):
    user = User.query.filter_by(id=user_id, role=role).first_or_404()
    if IssueRecord.query.filter_by(student_id=user.id, status='issued').first():
        flash('Cannot remove a student who currently has books issued.', 'danger')
        return
    db.session.delete(user)
    db.session.commit()
    flash(f'{role.capitalize()} account removed.', 'info')


# --------------------------------------------------------------------------
# Student: my books
# --------------------------------------------------------------------------
@app.route('/my-books')
@roles_required('student')
def my_books():
    active = IssueRecord.query.filter_by(student_id=current_user.id, status='issued').all()
    history = IssueRecord.query.filter_by(student_id=current_user.id, status='returned') \
        .order_by(IssueRecord.return_date.desc()).all()
    return render_template('my_books.html', active=active, history=history)


# --------------------------------------------------------------------------
# DB init + seed
# --------------------------------------------------------------------------
def init_db():
    with app.app_context():
        db.create_all()

        if not User.query.filter_by(role='admin').first():
            admin = User(
                username='admin',
                full_name='System Administrator',
                email='admin@library.local',
                role='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)

        if not User.query.filter_by(username='librarian1').first():
            librarian = User(
                username='librarian1',
                full_name='Jane Librarian',
                email='librarian@library.local',
                role='librarian'
            )
            librarian.set_password('librarian123')
            db.session.add(librarian)

        if not User.query.filter_by(username='student1').first():
            student = User(
                username='student1',
                full_name='Alex Student',
                email='student@library.local',
                role='student'
            )
            student.set_password('student123')
            db.session.add(student)

        if Book.query.count() == 0:
            sample_books = [
                Book(
                    title='The Pragmatic Programmer',
                    author='David Thomas',
                    isbn='9780135957059',
                    category='Technology',
                    quantity=3
                ),
                Book(
                    title='Clean Code',
                    author='Robert C. Martin',
                    isbn='9780132350884',
                    category='Technology',
                    quantity=2
                ),
                Book(
                    title='To Kill a Mockingbird',
                    author='Harper Lee',
                    isbn='9780061120084',
                    category='Fiction',
                    quantity=4
                ),
                Book(
                    title='A Brief History of Time',
                    author='Stephen Hawking',
                    isbn='9780553380163',
                    category='Science',
                    quantity=2
                ),
                Book(
                    title='Sapiens',
                    author='Yuval Noah Harari',
                    isbn='9780062316097',
                    category='History',
                    quantity=3
                )
            ]

            db.session.bulk_save_objects(sample_books)

        db.session.commit()


# Initialize database when deployed
try:
    init_db()
except Exception as e:
    print("Database initialization error:", e)


if __name__ == '__main__':
    app.run(debug=True)
