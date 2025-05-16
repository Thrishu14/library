from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import date, timedelta, datetime
import mysql.connector

app = FastAPI()

# Database Connection
def get_db():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="1234",
        database="library",
        charset="utf8"
    )
    return conn

# --- Models ---

class LoginData(BaseModel):
    user_name: str
    password: str

class RegisterData(BaseModel):
    user_name: str
    password: str
    role: str

class BookSearchResponse(BaseModel):
    book_id: int
    title: str
    author_id: int
    quantity: int

class AddBookData(BaseModel):
    book_id: int
    title: str
    author_id: int
    category_id: int
    quantity: int
    publisher: str

class TransactionRenewal(BaseModel):
    transaction_id: int

class ReservationRequest(BaseModel):
    book_id: int

# --- Endpoints ---

@app.post("/login")
def login(data: LoginData):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id, role, member FROM Users WHERE user_name = %s AND password = %s",
        (data.user_name, data.password)
    )
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user:
        return {"user_id": user[0], "role": user[1], "member_id": user[2]}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/register")
def register(data: RegisterData):
    conn = get_db()
    cursor = conn.cursor()

    role = data.role.lower()
    if role not in ['admin', 'member']:
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'member'")

    member_id = 0
    if role == 'member':
        cursor.execute("SELECT MAX(member) FROM Users WHERE member IS NOT NULL")
        max_member = cursor.fetchone()[0]
        member_id = 1 if max_member is None else max_member + 1

    cursor.execute(
        "INSERT INTO Users (user_name, password, role, member) VALUES (%s, %s, %s, %s)",
        (data.user_name, data.password, role, member_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "User registered", "member_id": member_id}

@app.get("/search_books", response_model=List[BookSearchResponse])
def search_books(keyword: str):
    conn = get_db()
    cursor = conn.cursor()
    query = """
        SELECT book_id, title, author_id, quantity 
        FROM Books 
        WHERE title LIKE %s OR author_id LIKE %s
    """
    cursor.execute(query, (f"%{keyword}%", f"%{keyword}%"))
    books = cursor.fetchall()
    cursor.close()
    conn.close()

    return [BookSearchResponse(book_id=b[0], title=b[1], author_id=b[2], quantity=b[3]) for b in books]

@app.post("/borrow/{member_id}")
def borrow_book(member_id: int, book_id: int):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT quantity FROM Books WHERE book_id = %s", (book_id,))
    book = cursor.fetchone()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if book[0] < 1:
        raise HTTPException(status_code=400, detail="Book unavailable")

    issue_date = datetime.now().date()
    due_date = issue_date + timedelta(days=10)

    cursor.execute(
        "INSERT INTO Transactions (book_id, member, issue_date, due_date, status) VALUES (%s, %s, %s, %s, 'Issued')",
        (book_id, member_id, issue_date, due_date)
    )
    cursor.execute("UPDATE Books SET quantity = quantity - 1 WHERE book_id = %s", (book_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Book borrowed", "due_date": due_date}

@app.post("/renew/{member_id}")
def renew_book(member_id: int, data: TransactionRenewal):
    conn = get_db()
    cursor = conn.cursor()
    new_due_date = datetime.now().date() + timedelta(days=10)

    cursor.execute(
        "UPDATE Transactions SET due_date = %s WHERE t_id = %s AND member = %s AND status = 'Issued'",
        (new_due_date, data.t_id, member_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Renewed", "new_due_date": new_due_date}

@app.post("/add_book")
def add_book(book: AddBookData):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Books (book_id, title, author_id, category_id, quantity, publisher) VALUES (%s, %s, %s, %s, %s, %s)",
        (book.book_id, book.title, book.author_id, book.category_id, book.quantity, book.publisher)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Book added"}

@app.post("/reserve/{member_id}")
def reserve_book(member_id: int, data: ReservationRequest):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT quantity FROM Books WHERE book_id = %s", (data.book_id,))
    book = cursor.fetchone()

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if book[0] > 0:
        raise HTTPException(status_code=400, detail="Book is available, no need to reserve")

    reservation_date = datetime.now().date()
    cursor.execute(
        "INSERT INTO Reservations (member, book_id, reservation_date) VALUES (%s, %s, %s)",
        (member_id, data.book_id, reservation_date)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Book reserved"}

@app.get("/reservations/{member_id}")
def view_reservations(member_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT r_id, book_id, reservation_date, status FROM Reservations WHERE member = %s",
        (member_id,)
    )
    reservations = cursor.fetchall()
    cursor.close()
    conn.close()

    return [
        {"r_id":r[0], "book_id":r[1] , "reservation_date":r[2],"status":r[3]}
        for r in reservations
    ]