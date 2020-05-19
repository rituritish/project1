import os, json

from flask import Flask, session ,render_template, redirect, url_for, request, logging, flash, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
#from helpers import login_required

from passlib.hash import sha256_crypt

import requests

books=[]


app = Flask(__name__)
# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():
    #return "hello world"
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        username = request.form.get("username")
        password = request.form.get("password")
        confirm = request.form.get("confirm")
        secure_password = sha256_crypt.encrypt(str(password))
        usernamedata = db.execute("SELECT username FROM users WHERE username=:username",{"username":username}).fetchone()
        if usernamedata is None:
            if password == confirm:
                db.execute("INSERT INTO users(name, username, password) VALUES(:name, :username, :password)",
                                         {"name":name, "username":username, "password":secure_password}
                        )   
                db.commit()
                flash("you are registerd and can login","success")
                return redirect(url_for('login'))
            else:
                flash("password does not match","danger")
                return render_template("register.html")
        else:
            flash("this user name already register. Please change username","danger")
            return render_template("register.html")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("name")
        password = request.form.get("password")

        usernamedata= db.execute("SELECT username FROM users WHERE username=:username",{"username":username}).fetchone()
        passwordata= db.execute("SELECT password FROM users WHERE username=:username",{"username":username}).fetchone()
        u_id= db.execute("SELECT id FROM users WHERE username=:username",{"username":username}).fetchone()
        u_id = u_id[0]
        if usernamedata is None:
            flash("no username","danger")
            return render_template("login.html")
        else:
            for passwor_data in passwordata:
                if sha256_crypt.verify(password,passwor_data):
                    session["log"] = True
                    session["user_id"] = u_id
                    flash("you are now login","success")
                    return redirect(url_for('search'))
                    #return render_template("search.html")
                else:
                    flash("Incorrect password","danger")
                    return render_template("login.html")


    return render_template("login.html")

@app.route("/search", methods=["GET","POST"])
def search():
    if request.method == "POST":
    #option = request.form['inlineRadioOptions']   if request.method == "POST":
        #titles=request.form.get("name")
        #title=request.form.get("title")
        name=request.form["name"]
        nameisbn=request.form["nameisbn"]
        nameauthor=request.form["nameauthor"]
#    books=db.execute("SELECT * FROM books WHERE title=:title",{"title":title}).fetchall()
        if nameisbn:
            return redirect(url_for("result",titles=nameisbn))
        if name:
            return redirect(url_for("result",titles=name))
        if nameauthor:
            return redirect(url_for("result",titles=nameauthor))
        flash("Please fill any value","danger")
        return redirect(url_for("search"))
    else:
        return render_template("search.html")
 #   return render_template("index.html")
    
@app.route("/<titles>", methods=["GET","POST"])
def result(titles):
    
    #option = request.form['inlineRadioOptions']
    #titles=request.form.get("name")
        #return f"<h1>{titles}</h>"
        title=titles
        books=db.execute("SELECT * FROM books WHERE title like :title OR isbn like :isbn OR author like :author",
                                                    {"title":"%"+title+"%",
                                                     "isbn":"%"+title+"%",
                                                     "author":"%"+title+"%"})

        
        if books.rowcount==0:
            flash("not found","danger")
            return redirect(url_for('search'))
            #return render_template("search.html")
        else:
            books = books.fetchall()
            return render_template("result.html", books=books)

    
   # return render_template("result.html")





@app.route("/book/<isbn>", methods=['GET','POST'])
def book(isbn):
    """ Save user review and load same page with reviews updated."""

    if request.method == "POST":

        # Save current user info
        currentUser = session["user_id"]
        
        # Fetch form data
        rating = request.form.get("rating")
        comment = request.form.get("comment")
        
        # Search book_id by ISBN
        row = db.execute("SELECT isbn FROM books WHERE isbn = :isbn",
                        {"isbn": isbn})

        # Save id into variable
        bookId = row.fetchone() # (id,)
        bookId = bookId[0]

        # Check for user submission (ONLY 1 review/user allowed per book)
        row2 = db.execute("SELECT * FROM reviews WHERE user_id =:user_id AND book_id =:book_id",
                    {"user_id": currentUser,
                     "book_id": bookId})

        # A review already exists
        if row2.rowcount == 1:
            
            flash('You already submitted a review for this book', 'warning')
            return redirect("/book/" + isbn)

        # Convert to save into DB
        rating = int(rating)

        db.execute("INSERT INTO reviews (user_id, book_id, comment, rating) VALUES \
                    (:user_id, :book_id, :comment, :rating)",
                    {"user_id": currentUser, 
                    "book_id": bookId, 
                    "comment": comment, 
                    "rating": rating})

        # Commit transactions to DB and close the connection
        db.commit()

        flash('Review submitted!', 'info')

        return redirect("/book/" + isbn)
    
    # Take the book ISBN and redirect to his page (GET)
    else:

        row = db.execute("SELECT isbn, title, author, year FROM books WHERE \
                        isbn = :isbn",
                        {"isbn": isbn})

        bookInfo = row.fetchall()

        """ GOODREADS reviews """

        # Read API key from env variable
        key = os.getenv("GOODREADS_KEY")
        
        # Query the api with key and ISBN as parameters
        query = requests.get("https://www.goodreads.com/book/review_counts.json",
                params={"key": key, "isbns": isbn})

        # Convert the response to JSON
        response = query.json()

        # "Clean" the JSON before passing it to the bookInfo list
        response = response['books'][0]

        # Append it as the second element on the list. [1]
        bookInfo.append(response)

        """ Users reviews """

         # Search book_id by ISBN
        row = db.execute("SELECT isbn FROM books WHERE isbn = :isbn",
                        {"isbn": isbn})

        # Save id into variable
        book = row.fetchone() # (id,)
        book = book[0]

        # Fetch book reviews
        # Date formatting (https://www.postgresql.org/docs/9.1/functions-formatting.html)
       
       
       
        #results = db.execute("SELECT users.username, comment, rating, \
        #                    to_char(time, 'DD Mon YY - HH24:MI:SS') as time \
        #                    FROM users \
        #                    INNER JOIN reviews \
        #                    ON users.id = reviews.user_id \
        #                    WHERE book_id = :book \
        #                    ORDER BY time",
         #                   {"book": book})

        results = db.execute("SELECT users.username, comment, rating FROM users INNER JOIN reviews ON users.id = reviews.user_id WHERE book_id = :book ",
                            {"book": book})
        #results= db .execute("SELECT * from reviews")
        reviews = results.fetchall()

        return render_template("book.html", bookInfo=bookInfo, reviews=reviews)



@app.route("/api/<isbn>", methods=['GET'])
#@login_required
def api_call(isbn):

    # COUNT returns rowcount
    # SUM returns sum selected cells' values
    # INNER JOIN associates books with reviews tables

    row = db.execute("SELECT title, author, year, isbn, COUNT(reviews.reviews_id) as review_count, AVG(reviews.rating) as average_score FROM books INNER JOIN reviews ON books.isbn = reviews.book_id WHERE isbn = :isbn GROUP BY title, author, year, isbn",
                    {"isbn": isbn})

    # Error checking
    if row.rowcount != 1:
        return jsonify({"Error": "Invalid book ISBN"}), 422

    # Fetch result from RowProxy    
    tmp = row.fetchone()

    # Convert to dict
    result = dict(tmp.items())

    # Round Avg Score to 2 decimal. This returns a string which does not meet the requirement.
    # https://floating-point-gui.de/languages/python/
    result['average_score'] = float('%.2f'%(result['average_score']))

    return jsonify(result)



@app.route("/logout")
def logout():
    session.clear()
    flash("You are now logged out","success")
    return redirect(url_for('index')) 

if __name__=="__main__":
    app.secret_key = "1234567dailywebcoding"
    app.run(debug=True)
