from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3

app = Flask(__name__)
app.secret_key = 'secret'
socketio = SocketIO(app)
login_manager = LoginManager()
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    con = sqlite3.connect('users.db')
    cur = con.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    con.close()
    if user:
        return User(user[0], user[1], user[3])
    return None

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        r = request.form['role']
        con = sqlite3.connect('users.db')
        cur = con.cursor()
        cur.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)", (u, p, r))
        con.commit()
        con.close()
        return redirect('/')
    return render_template('register.html')

@app.route('/login', methods=['POST'])
def login():
    u = request.form['username']
    p = request.form['password']
    con = sqlite3.connect('users.db')
    cur = con.cursor()
    cur.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p))
    user = cur.fetchone()
    con.close()
    if user:
        login_user(User(user[0], user[1], user[3]))
        return redirect('/dashboard')
    return redirect('/')

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        con = sqlite3.connect('users.db')
        cur = con.cursor()
        cur.execute("SELECT username, role FROM users WHERE role='regular'")
        users = cur.fetchall()
        con.close()
        return render_template('admin.html', users=users)
    return render_template('user.html', name=current_user.username)

@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html', name=current_user.username)

@app.route('/teaser')
@login_required
def teaser():
    return render_template('teaser.html', name=current_user.username)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')

@socketio.on('send_message')
def handle_message(data):
    emit('receive_message', data, broadcast=True)

if __name__ == '__main__':
    con = sqlite3.connect('users.db')
    cur = con.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT,
        role TEXT)''')
    con.commit()
    con.close()
    socketio.run(app, debug=True)

players = []
game_state = {"question": "12 + 9", "answer": "21", "scores": {}}

@socketio.on('join_teaser')
def handle_join(user):
    if user not in players:
        players.append(user)
    if len(players) == 2:
        socketio.emit('start_teaser', {"question": game_state["question"]})
        for p in players:
            if p not in game_state["scores"]:
                game_state["scores"][p] = 0
    else:
        emit('waiting', 'Waiting for opponent...')

@socketio.on('submit_teaser_answer')
def handle_answer(data):
    user = data['user']
    answer = data['answer'].strip()
    if answer == game_state["answer"]:
        game_state["scores"][user] += 1
        socketio.emit('teaser_result', {
            "message": f"{user} answered correctly!",
            "scores": format_scores()
        })
        reset_round()
    else:
        emit('teaser_result', {
            "message": f"{user} answered incorrectly!",
            "scores": format_scores()
        })

def format_scores():
    return " | ".join([f"{p}: {s}" for p, s in game_state["scores"].items()])

def reset_round():
    game_state["question"] = "7 + 8"
    game_state["answer"] = "15"

