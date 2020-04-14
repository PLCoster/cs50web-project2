import os
import pytz

from flask import Flask, session, flash, jsonify, redirect, render_template, request
from flask_session import Session
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from models import *

from datetime import datetime

if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

if not os.getenv("SECRET_KEY"):
    raise RuntimeError("SECRET_KEY is not set")


# Flask App Configuration
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)
socketio = SocketIO(app)

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

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


def validate_pass(password):
    """Checks password string for minimum length and a least one number and one letter"""

    if len(password) < 8:
        return False

    letter = False
    number = False
    numbers = ["1", "2", "3", "4", "5", "6", "7", "8", "9"]
    letters = list(map(chr, range(97, 123)))

    for i in range(len(password)):
        if password[i] in numbers:
            number = True
        if password[i].lower() in letters:
            letter = True

    if letter and number:
        return True
    else:
        return False


@app.route("/")
def index():
  """ Main single-page app for the site """

  if session.get("user_id") == None:
    return redirect("/login")

  return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user into site"""

    # If user is already logged in, return to home screen:
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
        user_query = User.query.filter_by(username=username).first()

        print(user_query)

        # Check username exists and password is correct:
        if not user_query or not check_password_hash(user_query.pass_hash, password):
            flash("Invalid username and/or password! Please try again!")
            return render_template("login.html")

        # Otherwise log in user and redirect to homepage:
        session["user_id"] = user_query.id
        session["screen_name"] = user_query.screen_name

        flash('Log in Successful! Welcome back to Flack Teams!')
        return redirect("/")

    # If User reaches Route via GET (e.g. clicking login link):
    else:
        return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user for the website"""

    # If user is already logged in, return to home screen:
    if session.get("user_id") != None:
        return redirect("/")

    # If reached via POST by submitting form - try to register new user:
    if request.method == "POST":

        # Get input from registration form:
        username = request.form.get("username")
        screen_name = request.form.get("screenname")
        password = request.form.get("password")
        confirm = request.form.get("confirmation")
        profile_img = request.form.get("profile")

        # If form is incomplete, return and flash apology:
        if not all([username, screen_name, password, confirm, profile_img]):
            flash('Please fill in all fields to register!')
            return render_template("register.html")

        # If password and confirmation do not match, return and flash apology:
        elif password != confirm:
            flash('Password and confirmation did not match! Please try again.')
            return render_template("register.html")

        # Ensure password meets password requirements:
        elif not validate_pass(password):
            flash('Password must be eight characters long with at least one number and one letter!')
            return render_template("register.html")

        # Otherwise information from registration is complete:
        else:
            # Check username does not already exist, if it does then ask for a different name:

            user_query = User.query.filter_by(username=username).first()

            print(user_query)

            if user_query:
                flash('Sorry but that username is already in use, please pick a different username!')
                return render_template("register.html")

            # Otherwise add user to database using hashed password:
            pass_hash = generate_password_hash(password)

            # Add new user to users table:
            new_user = User(username=username, screen_name=screen_name, pass_hash=pass_hash, profile_img=profile_img)
            db.session.add(new_user)
            db.session.commit()

            # Put unique user ID and username into session:
            user_info = User.query.filter_by(username=username).first()
            session["user_id"] = user_info.id
            session["screen_name"] = user_info.screen_name

            # Return to main page, logged in:
            #flash('Welcome to Flack Teams! You have been succesfully registered and logged in!')
            return redirect("/")

    # If User reaches Route via GET (e.g. clicking registration link):
    else:
        return render_template("register.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # If user not logged in return to login screen:
    if session.get("user_id") == None:
        return redirect("/login")

    # Forget any user_id
    session.clear()

    # Redirect user to home page
    flash('You have been logged out from Flack Teams. See you again soon!')
    return redirect("/login")


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

  emit("channel logon", {"message_history" : message_history, "channel_name" : data['channel']}, room=user)
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