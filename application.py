import os
import pytz

from flask import Flask, session, flash, jsonify, redirect, render_template, request
from flask_session import Session
from flask_socketio import SocketIO, emit, join_room, leave_room
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError

from datetime import datetime


# Flask App Configuration
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
socketio = SocketIO(app)

if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

# Server Message Channel Storage - Starts with Standard Main Channel:
channels = {'Home':
                  {'messages': {},
                   'next_message': 1 ,
                   'subchannels':{

                   }}, 'News': {'messages': {}, 'next_message': 1 , 'subchannels':{}}, 'Sports': {'messages': {}, 'next_message': 1 , 'subchannels':{}}, 'Gaming':{'messages': {}, 'next_message': 1 , 'subchannels':{}}}

def sanitize_message(message):
  """ Helper function that takes a user's message string and replaces special HTML chars with their HTML entities to keep the chars and prevent adding HTML to the message board

  Returns the sanitized message string
  """

  return message.replace('&', '&amp;').replace('"', '&quot;').replace('\'', '&apos;').replace('<', '&lt;').replace('>', '&gt;')


@app.route("/")
def index():
  return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user into site"""

    # If user is already logged in, return to home:
    if session.get("user_id") != None:
        return redirect("/")

    # If reached via POST by submitting login form:
    if request.method == "POST":

        # Get input from login form:
        username = request.form.get("username")
        password = request.form.get("password")

        # Check that login has been filled out:
        if not username or not password:
            flash("Please enter username AND password to Log in!")
            return render_template("login.html")

        # Query database for username:
        user = db.execute("SELECT * FROM users WHERE username = :username", {"username" : username}).fetchone()

        # Check username exists and password is correct:
        if not user or not check_password_hash(user[2], password):
            flash("Invalid username and/or password! Please try again!")
            return render_template("login.html")

        # Otherwise log in user and redirect to homepage:
        session["user_id"] = user[0]
        session["username"] = user[1]

        flash('Log in Successful! Welcome back to READ-RATE!')
        return redirect("/")

    # If User reaches Route via GET (e.g. clicking login link):
    else:
        return render_template("login.html")



@socketio.on("send message")
def send_message(data):
  """ Sends a message to all users in the same room, and stores the message on the server """

  print('Server has received a message, Sending message to users in room')

  # Get data from incoming message:
  message_text = sanitize_message(data['message'])
  screen_name = data['screen_name']
  room = data['channel']

  print('Room: ', room)

  # Date and Timestamp the message:
  timestamp = datetime.now(pytz.utc).timestamp()
  date = datetime.now().strftime("%d %b %Y")

  # Save message data to channel log:
  next = channels[room]['next_message']
  message = [message_text, screen_name, timestamp, date, next]
  channels[room]['messages'][next] = message

  print('Message received by server:', message)

  # Store up to 100 messages, then overwrite the first message
  channels[room]['next_message'] += 1
  if channels[room]['next_message'] > 100:
    channels[room]['next_message'] = 1

  emit("announce vote", {"message": message}, room=room)


@socketio.on("join channel")
def join_channel(data):
  """ Lets a user join a specific channel, relays last 100 messages from the channel to that specific user """

  # Leave the previous channel and join the new channel:
  leave_room(data['previous'])
  join_room(data['channel'])
  user = request.sid

  # Send sorted channel history back to user who has just joined:
  message_history = sorted(list(channels[data['channel']]['messages'].values()), key = lambda x : x[2])

  print('Channel status:', channels)
  print('Sending message history:', message_history)

  emit("channel logon", {"message_history" : message_history}, room=user)
  print("channel logo emitted")
  # Send current channel list to the user
  channel_list = list(channels.keys())

  emit('channel added', {'channel_list': channel_list}, room=user)
  print("channel list emitted")


@socketio.on('create channel')
def create_channel(data):
  """ Lets a user create a new chat channel, with a unique name """

  # Check name not already in use:
  if data['new_channel'] in channels.keys():
    # This should send back some kind of error message
    return False

  # Otherwise create a new chat channel and send channel list to all users:
  channels[data['new_channel']] = {'messages': {}, 'next_message': 1 , 'subchannels':{}}

  channel_list = list(channels.keys())

  emit('channel added', {'channel_list': channel_list}, broadcast=True)


if __name__ == '__main__':
  socketio.run(app)