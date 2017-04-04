from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    user = db.execute("SELECT username, cash FROM users WHERE id=:id", id=session["user_id"])
    user[0]["cash"] = usd(float(user[0]["cash"]))

    # this will include symbols and # of shares currently in user's portfolio
    portfolio = db.execute("SELECT stock, shares FROM portfolio WHERE user_id=:id", id=session["user_id"])

    # quotes will include the results of the lookup function for each stock in user's portfolio
    quotes = []

    for line in portfolio:
        q = quotes.append(lookup(str(line["stock"])))

    return render_template("index.html", user=user, portfolio=portfolio, quotes=quotes)

@app.route("/buy", methods=["GET", "POST"])
@app.route("/success", methods=["GET, POST"])
@login_required
def buy():
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must enter stock symbol")
        
        if not request.form.get("shares"):
            return apology("must enter number of shares")
        
        shares = int(request.form.get("shares"))
        if not shares >= 0:
            return apology("pleae enter a valid number")
        rows = db.execute("SELECT cash FROM users WHERE id = :current", current=session["user_id"])
        balance = rows[0]["cash"]
        stock = lookup(request.form.get("symbol"))
        if not stock:
            apology("stock was not found")
        name = stock['name']
        symbol = stock['symbol']
        price = stock['price']
        cost = shares*price
        user = session["user_id"]
        
        if not balance >= cost:
            return apology("not sufficent funds")
        else:
            transactions = db.execute("INSERT INTO portfolio (shares, stock, price, user_id) VALUES (:shares, :symbol, :cost, :user)", shares = shares, symbol = symbol, cost = cost, user = user)
            db.execute("UPDATE users SET cash = cash - :cost WHERE id = :user", user= user, cost = cost)
            return render_template("success.html")
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    return render_template("history.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@app.route("/quoted", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        if not request.form.get("search"):
            return apology("enter symbol")
        quote = lookup(request.form.get("search"))
        return render_template("quoted.html", stock = quote)
    else:
        return render_template("quote.html")
            
   
    
    

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
   
    #forget any user_id
    session.clear()
   
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
       
        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")
       
        #ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")
       
        # ensure same password was entered twice
        if request.form.get("password") != request.form.get("password confirmation"):
            return apology("passwords much match! (password field and password confirmation field)")
       

        hash = pwd_context.encrypt(request.form.get("password"))
        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username=request.form.get("username"), hash=hash)
        if not result:
            return apology("username already exists!")
       
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        if not rows:
            apology("something went wrong")
        session["user_id"] = rows[0]["id"]
        return render_template("success.html")
    else:
        return render_template("register.html")
        
    



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must enter stock symbol")
        
        if not request.form.get("shares"):
            return apology("must enter number of shares")
            
        shares = int(request.form.get("shares"))
        stock = lookup(request.form.get("symbol"))
        
        name = stock['name']
        symbol = stock['symbol']
        price = stock['price']
        
        in_depot = db.execute("SELECT SUM(shares) AS share_amount FROM portfolio WHERE stock = :symbol AND user_id = :id", symbol = symbol, id = session["user_id"])
        share_amount = in_depot[0]["share_amount"] if in_depot else 0
        amount = -1*shares*price
        
        if share_amount >= int(request.form.get("shares")):
            db.execute("DELETE FROM portfolio WHERE user_id=:uid AND stock=:symbol", uid=session["user_id"], symbol=stock["symbol"])
            transaction = db.execute("INSERT INTO portfolio (shares, stock, price, user_id) VALUES (:shares, :symbol, :amount, :id)", shares = shares, symbol = symbol, amount = amount, id = session["user_id"])
            cashupdate = db.execute("UPDATE users SET cash = cash - :amount WHERE id = :id", amount = amount, id = session["user_id"])
            return render_template ("success.html")
        elif share_amount < int(request.form.get("shares")):
            return apology("you dont have this many shares to sell")
            
    else:
        return render_template("sell.html")
        