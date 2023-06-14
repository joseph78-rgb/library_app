from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from os import getcwd
import math

#create flask and sqlalchemy instance and configure
app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{getcwd()}/library.db'

db = SQLAlchemy(app)

#create database schema
class Books(db.Model):
    serial = db.Column(db.Integer, primary_key=True, autoincrement=False)
    title = db.Column(db.String(50), nullable=False)
    author = db.Column(db.String(50), nullable=False)
    category = db.Column(db.String(50), nullable=True)
    borrower_id = db.Column(db.Integer, db.ForeignKey('borrower.id'), nullable=True)
    date_lenderd = db.Column(db.DateTime, nullable=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

class Borrower(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    books_lendered = db.Relationship('Books', backref='borrower')

#route to get homepage and perform search
@app.route('/', methods=['POST', 'GET'])
def index():
    #if method is get query for all books and render 
    if request.method == 'GET':
        books = Books.query.order_by(Books.date_created.desc()).all()
        return render_template('index.html', books=books)
    
    #else if route is post serch for a book and return results
    creteria = request.form['creteria']
    search = request.form['search']
    search = f'%{search}%'
    result = Books.query.filter(getattr(Books,creteria).like(search))
    return render_template('index.html', books=result)
    
#route to add a new book to the database 
@app.route('/add_book', methods=['POST'])
def add_books():
    serial = request.form['serial']
    title = request.form['title']
    author = request.form['author']
    category = request.form['category']

    book = Books(serial=serial, title=title, author=author, category=category)
    db.session.add(book)
    db.session.commit()
    return redirect('/')

#route to return book to borrow and borrow the book
@app.route('/borrow', methods=['POST', 'GET'])
def borrow():
    #get the book to lend if reuest method is get
    if request.method == 'GET':
        book_id = request.args.get('book_id')
        return render_template('lendingpage.html',book=Books.query.filter_by(serial=book_id).first(), error=None)
    
    #else get form fields for user and book id to lend
    id = request.form['id']
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    book_id = request.form['book_id']
    
    #add user to database if new
    if first_name and last_name:
        borrower = Borrower(id=id, first_name=first_name, last_name=last_name)
        db.session.add(borrower)
        db.session.commit()

    #uery for the book and perform a relationship with the borrower
    book = Books.query.filter_by(serial=book_id).first()
    borrower = Borrower.query.filter_by(id=id).first()
    if not borrower:
        return render_template('lendingpage.html',book=book, error='No user with such ID! Please register first')
    book.borrower = borrower
    book.date_lenderd=datetime.utcnow()
    db.session.add(book)
    db.session.commit()
    return render_template('lendingpage.html',book=book, success_lending=True)

#route to update a book
@app.route('/modify_book', methods=['POST', 'GET'])
def modify_book():
    #get the book to update if request method is get
    if request.method == 'GET':
        book_id = request.args.get('book_id')
        return render_template('modifyingpage.html', book = Books.query.filter_by(serial=book_id).first())
    
    #else read for any form field entered and update the book table row  
    book_id = request.form['book_id']
    book = Books.query.filter_by(serial=book_id).first()
    for key in request.form:
        if request.form[key] and key != 'book_id':
            setattr(book, key, request.form[key])
    db.session.add(book)
    db.session.commit() 
    return render_template('modifyingpage.html', book = book, update_status=True)

#route to delete a book provided book id 
@app.route('/delete_book<int:book_id>')
def delete_book(book_id):
    book = Books.query.filter_by(serial=book_id).first()
    db.session.delete(book)
    db.session.commit()
    return render_template('modifyingpage.html', book=book, delete_status=True)

#function that accepts books object and rebuild the object by adding new fields and calculating balance then returning new object 
def calculate_and_format(book_object):
    books = []
    for bk in book_object:
        borrower = Borrower.query.filter_by(id=bk.borrower_id).first()
        bal = math.floor(((datetime.utcnow() - datetime.strptime(str(bk.date_lenderd), "%Y-%m-%d %H:%M:%S.%f")).total_seconds()))
        book = {
            'serial':bk.serial,
            'title': bk.title,
            'author': bk.author,
            'category': bk.category,
            'borrower_id': bk.borrower_id,
            'borrower': f'{borrower.first_name} {borrower.last_name}',
            'bal': bal if bal < 500 else 500
        }
        books.append(book)
    return books

#route to render lending status page by reading only books that are lendered
@app.route('/lending_status')
def lending_status():
    result = Books.query.filter(Books.borrower_id != None)
    return render_template('lendingstatus.html', books = calculate_and_format(result))

#route to search for a book borrower
@app.route('/search_borrower')
def search_borrower():
    id = request.args.get('id')
    borrower = Borrower.query.filter_by(id=id).first()
    result = Books.query.filter(Books.borrower_id != None)
    if not borrower:
        return render_template('lendingstatus.html', books = calculate_and_format(result), error='Sorry! No registerd user with such ID exists')
    if len(borrower.books_lendered)==0:
        return render_template('lendingstatus.html', books = calculate_and_format(result), error='This user has not been lendered any book')
    
    return render_template('lendingstatus.html', books = calculate_and_format(borrower.books_lendered))

#route to perform a boom return provided book id to return
@app.route('/return_book')
def return_book():
    book_id = request.args.get('book_id')
    book = Books.query.filter_by(serial=book_id).first()
    book.borrower = None
    db.session.add(book)
    db.session.commit()
    result = Books.query.filter(Books.borrower_id != None)
    return render_template('lendingstatus.html', books = calculate_and_format(result), success_return=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0',port=5000)
    # with app.app_context():
    #     db.create_all()