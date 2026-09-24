# Library Management System

A Flask-based library management system with three roles: **Admin**, **Librarian**, and **Student**.

## Features

- **Admin**: manage librarian and student accounts, view system-wide stats, full book catalog control
- **Librarian**: issue/return books, manage the book catalog, view active loans and overdue items
- **Student**: browse the catalog, view currently borrowed books and due dates, view loan history

## Setup

1. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the app (this also creates the SQLite database and seeds demo data on first run):
   ```bash
   python app.py
   ```

4. Open http://127.0.0.1:5000 in your browser.

## Demo Accounts

| Role      | Username    | Password      |
|-----------|-------------|---------------|
| Admin     | admin       | admin123      |
| Librarian | librarian1  | librarian123  |
| Student   | student1    | student123    |

**Change these credentials before deploying anywhere beyond local testing.**

## Project Structure

```
library-management-system/
│
├── app.py                  # Application factory, models, and routes
├── requirements.txt
├── README.md
├── .gitignore
│
├── templates/               # Jinja2 templates
│   ├── base.html
│   ├── login.html
│   ├── admin_dashboard.html
│   ├── librarian_dashboard.html
│   ├── student_dashboard.html
│   ├── books.html
│   ├── add_book.html
│   ├── edit_book.html
│   ├── students.html
│   ├── librarians.html
│   ├── issue_book.html
│   └── my_books.html
│
└── static/
    ├── css/style.css
    └── js/script.js
```

## Notes

- Database: SQLite (`library.db`), created automatically on first run.
- Passwords are hashed with Werkzeug's security helpers — never stored in plain text.
- To reset the database, stop the app and delete `library.db`, then run `python app.py` again.
