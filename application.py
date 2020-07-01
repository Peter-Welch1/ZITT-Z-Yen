import csv
from datetime import datetime
from cs50 import SQL
import random
import codecs

from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError

#upload extensions
ALLOWED_EXTENSIONS = {'csv'}

# Configure application
app = Flask(__name__)


# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure SQLite database object
db = SQL("sqlite:///quiz.db")



@app.route("/", methods=['GET', 'POST'])
def index():
    #clear any current session
    session.clear()

    if request.method == 'GET':
        return render_template('index.html')

    else:
        #todays date
        time_id = datetime.today()
        date = time_id.strftime('%Y-%m-%d')

        # give the user a session id
        session["user_id"] = time_id
        
        # create a temporary entry into the db to keep track of the game
        db.execute('INSERT INTO game (name, date, category, time_id) VALUES(?,?,?,?)', request.form.get('username'), date, request.form.get('category'), time_id)

        return redirect('/game')


@app.route("/game", methods=['GET', 'POST'])
def game():
    # users session
    user = session["user_id"]

    # game question length
    game_length = 20

    # query the game table for the users game info
    row = db.execute('SELECT * FROM game WHERE time_id = ?', user)

    category = row[0]['category']
    question_no = row[0]['question']
    score = row[0]['correct']

    # query length of question set selected
    length = db.execute('SELECT MAX(id) as m FROM ?', category)[0]['m']

    # generate random question number
    number = random.randint(1, int(length))

    # query the q and a for the category selected
    info = db.execute('SELECT q, a FROM ? WHERE id = ?', category, number)
    question = info[0]['q']
    answer = info[0]['a']

    if request.method == 'GET':

        # saving current Q number to display
        row = db.execute('SELECT * FROM game WHERE time_id = ?', user)
        question_no = row[0]['question']

        # finish game if past 20 q's
        if question_no > game_length:
            return redirect('/user_score')

        return render_template('game.html', score=score, question_no=question_no, question=question, answer=answer, game_length=game_length)
    
    else:
        # update q number and score if correct button submitted
        db.execute('UPDATE game SET question = ? WHERE time_id = ?', question_no + 1, user)
        db.execute('UPDATE game SET correct = ? WHERE time_id = ?', score + 1, user)

        # select updated infomation to display
        row = db.execute('SELECT * FROM game WHERE time_id = ?', user)
        question_no = row[0]['question']
        score = row[0]['correct']

        # finish game if past 20 q's
        if question_no > game_length:
            return redirect('/user_score')

        return render_template('game.html', score=score, question_no=question_no, question=question, answer=answer, game_length=game_length)

@app.route("/wrong", methods=['POST'])
def wrong():
    # cycle to the next question, update question number when wrong button submitted
    user = session["user_id"]
    row = db.execute('SELECT * FROM game WHERE time_id = ?', user)
    question_no = row[0]['question']
    db.execute('UPDATE game SET question = ? WHERE time_id = ?', question_no + 1, user)

    return redirect('/game')

@app.route('/change_cat', methods=['POST'])
def change_cat():
    # updating the category when changed during game
    user = session["user_id"]
    cat = request.form.get('category')
    db.execute('UPDATE game SET category = ? WHERE time_id = ?', cat, user)

    return redirect('/game')


@app.route("/user_score")
def user_score():
    # users session
    user = session["user_id"]

    # select infomation to render in table
    row = db.execute('SELECT * FROM game WHERE time_id = ?', user)
    name = row[0]['name']
    score = row[0]['correct']
    date = row[0]['date']

    # personalised message
    if score == 0:
        message = 'Brilliant. You got every single question wrong. Don’t quit the day job.'
    elif score < 5:
        message = f'{score}. My goldfish can score higher than that!' 
    elif score < 10:
        message = f'You got {score} correct. Why not try another round. I bet you can do better.'
    elif score < 15:
        message = f'You scored {score}, and you made it into double figures. Well done!'
    elif score< 20:
        message = f'Hey, {score} is a good score. You should be proud!'
    else:
        message = 'Full marks! Are you sure you didn’t cheat…'

    # removes user data from the game table at the end of the game
    db.execute('DELETE FROM game WHERE time_id = ?', user)

    return render_template('user_score.html', name=name, score=score, date=date, message=message)

@app.route("/upload", methods=['GET', 'POST'])
def upload():
    if request.method == 'GET':
        return render_template('upload.html')
    else:
        # insert data into the USE table
        question = request.form.get('question')
        answer = request.form.get('answer')

        db.execute('INSERT INTO USE (q, a) VALUES(?,?)', question, answer)

        return render_template('success.html', message='Question imported successfully')

@app.route("/instructions")
def instructions():
    return render_template('instructions.html')


# function to check file extention
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/question_set", methods=['POST'])
def question_set():

    # Create variable for uploaded file
    f = request.files['upload_file'] 

    # check that file has been submitted and that it is a csv 
    if f.filename != '' and allowed_file(f.filename):

        #store the file contents as a string
        fstring = f.read()
        
        #create list of dictionaries keyed by header, need to use codecs to transtate binary stream
        csv_dicts = [{k: v for k, v in row.items()} for row in csv.DictReader(codecs.iterdecode(fstring.splitlines(), 'utf-8'), skipinitialspace=True)]

        #iterate each row in the csv
        for row in csv_dicts:

            q = row['question']

            a = row['answer']

            # inserting the information from each row in the csv into the sql database
            db.execute('INSERT INTO USE (q, a) VALUES(?,?)',q,a)

        return render_template('success.html', message='Question set imported successfully')
    else:
        return render_template('success.html', message='Upload failed')
