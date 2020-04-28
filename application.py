import os
import pytz

from flask import Flask, session, flash, jsonify, redirect, render_template, request
from flask_session import Session
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.utils import secure_filename
from models import *

from datetime import datetime

if not os.getenv('DATABASE_URL'):
  raise RuntimeError('DATABASE_URL is not set')

if not os.getenv('SECRET_KEY'):
  raise RuntimeError('SECRET_KEY is not set')

if not os.getenv('UPLOAD_FOLDER'):
  raise RuntimeError('UPLOAD_FOLDER is not set')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Flask App Configuration
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
socketio = SocketIO(app)

# Configure session to use filesystem
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Server WS/Channel Storage - Starts with Standard Welcome Channel:
workspaces = {'Welcome!':
                {'channels':
                  {'Getting Started':
                    {'messages':
                      {1 : {'message_text': 'Welcome to Flack-Teams. Here you can find some info to help you get started! Flack teams uses workspaces and channels to separate different chats. A workspace can contain several different chat channels, specific to the workspace. To create a new workspace with its own channels to chat in, click the <i class="fas fa-plus-square"></i> symbol next to \'Workspaces\' in the side bar to the left.', 'screen_name': 'Flack-Teams Help', 'message_timestamp' : 1586888725, 'message_date': '14 Apr 2020', 'message_id': 1, 'profile_img': 'admin.png', 'user_id': -1, 'edited': False, 'edit_text': None, 'edit_date': None, 'deleted': False, 'private': False},
                      2 : {'message_text': 'Flack teams uses workspaces and channels to separate different chats. To create a new channel in a workspace, click the <i class="fas fa-plus-square"></i> symbol next to \'Channels\' in the side bar to the left. Each channel in a workspace must have a unique name, and cannot be viewed when you are logged into a different workspace!', 'screen_name': 'Flack-Teams Help', 'message_timestamp' : 1586888726, 'message_date': '14 Apr 2020', 'message_id': 2, 'profile_img': 'admin.png', 'user_id': -1, 'edited': False, 'edit_text': None, 'edit_date': None, 'deleted': False, 'private': False},
                      3 : {'message_text': 'Private chats can be started with any other user. Hover over the message posted by the user you wish to chat with and click the \'<i class="fas fa-user"></i> Private Message\' link that appears to start a private chatroom with that user. Private chats are not specific to a workspace; they can be accessed at any time.', 'screen_name': 'Flack-Teams Help', 'message_timestamp' : 1586888727, 'message_date': '14 Apr 2020', 'message_id': 3, 'profile_img': 'admin.png', 'user_id': -1, 'edited': False, 'edit_text': None, 'edit_date': None, 'deleted': False, 'private': False}},
                    'next_message': 4},
                  'Announcements': {'messages': {}, 'next_message': 1 },
                  'News': {'messages': {}, 'next_message': 1 }
                  },
                'users_online': set()
                }
             }

# Server Private Channel Storage - Each User gets a personal 'Memo' Private Chat:
private_channels = {'user_private_list': {}, 'channels': {}}


def sanitize_message(message):
  """ Helper function that takes a user's message string and replaces special HTML chars with their HTML entities to keep the chars and prevent adding HTML to the message board

  Returns the sanitized message string
  """

  return message.replace('&', '&#38;').replace('"', '&#34;').replace('\'', '&#92;').replace('<', '&#60;').replace('>', '&#62;').replace('`', '&#96;').replace('=', '&#61;')


def sanitize_name(name):
  """ Helper function to remove non-permitted characters from a channel or workspace name
  Non-permitted characters are HTML special chars &, ", ', <, >, `, = and (, ), ~.

  Returns the sanitize channel/ws name
  """

  return name.replace('&', '').replace('"', '').replace('\'', '').replace('<', '').replace('>', '').replace('(', '').replace(')', '').replace('~', '').replace('`', '').replace('=', '')


def validate_pass(password):
    """Checks password string for minimum length and a least one number and one letter"""

    if len(password) < 8:
        return False

    letter = False
    number = False
    numbers = ['1', '2', '3', '4', '5', '6', '7', '8', '9']
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

def load_user(user):
  """ Loads a user's personal information from DB into the session """

  session['user_id'] = user.id
  session['screen_name'] = user.screen_name
  session['profile_img'] = user.profile_img


def load_hist(user):
  """ Loads a user's ws and channel hist from DB into the session """

  session['curr_ws'] = user.curr_ws
  session['curr_chan'] = user.curr_chan
  session['curr_ws_chan'] = f'{session["curr_ws"]}~{session["curr_chan"]}'
  session['curr_private'] = (session['user_id'], session['user_id'])


def load_private(user_id):
  """ Initialises and loads all private chat channels for a user, sends the
  channel list to the user """

  # If the user does not have a private channel list in on the server, create it and a default memo channel:
  if not private_channels['user_private_list'].get(user_id):

    private_channels['user_private_list'][user_id] = {}

    memo_id = (user_id, user_id)

    private_channels['user_private_list'][user_id][memo_id] = {'name': 'Private Memo'}
    private_channels['channels'][memo_id] = {'messages': {1 : {'message_text': 'This is your private memo space that can only be viewed by you! Use it to leave yourself reminders, to-do lists or anything else you would like!', 'screen_name': 'Flack-Teams Help', 'message_timestamp': datetime.now(pytz.utc).timestamp(), 'message_date': datetime.now().strftime('%d %b %Y'), 'message_id': 1, 'profile_img': 'admin.png','user_id': -1, 'edited': False, 'edit_text': None, 'edit_date': None, 'deleted' : False, 'private': True}}, 'next_message': 2}

  # Send user list of all their current private channels:
  user_room = f'{(user_id,)}'
  user_private_channels = private_channels['user_private_list'][user_id]
  user_private_chan_list = [[x[0], x[1], user_private_channels[x]['name']] for x in user_private_channels]

  emit('private_list amended', {'priv_chan_list': user_private_chan_list}, room=user_room)


def update_ws_users(ws_name):
  """ Sends out an updated list and count of all users in a workspace, when someone signs in or out of ws """

  # Get count of current ws users:
  num_users = len(workspaces[ws_name]['users_online'])

  user_details = []

  print('UPDATING WORKSPACE USERS: ', workspaces[ws_name]['users_online'])

  # Get names, user_ids and icons for all users online:
  for user_id in workspaces[ws_name]['users_online']:
    user_info = User.query.get(user_id)

    user = {}
    user['name'] = user_info.screen_name
    user['id'] = user_id
    user['icon'] = user_info.profile_img

    user_details.append(user)

  emit('ws_users amended', {'users' : num_users, 'user_details' : user_details}, room=ws_name)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


"""
================================================================================
FLASK APP ROUTES
================================================================================
"""

@app.route('/')
def index():
  """ Main single-page app for the site """

  if session.get('user_id') == None:
    return redirect('/login')

  print('Loading Index Page for User')

  return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Log user into site"""

    # If user is already logged in, return to home screen:
    if session.get('user_id') != None:
        return redirect('/')

    # If reached via POST by submitting login form:
    if request.method == 'POST':

        # Get input from login form:
        username = request.form.get('username')
        password = request.form.get('password')

        # Check that login has been filled out:
        if not username or not password:
            flash('Please enter username AND password to Log in!')
            return render_template('login.html')

        # Query database for username:
        user_info = User.query.filter_by(username=username).first()

        # Check username exists and password is correct:
        if not user_info or not check_password_hash(user_info.pass_hash, password):
            flash('Invalid username and/or password! Please try again!')
            return render_template('login.html')

        # Otherwise load user session and redirect to homepage:
        load_user(user_info)

        #flash('Log in Successful! Welcome back to Flack Teams!')
        return redirect('/')

    # If User reaches Route via GET (e.g. clicking login link):
    else:
        return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Register user for the website"""

    # If user is already logged in, return to home screen:
    if session.get('user_id') != None:
        return redirect('/')

    # If reached via POST by submitting form - try to register new user:
    if request.method == 'POST':

        # Get input from registration form:
        username = request.form.get('username')
        screen_name = request.form.get('screenname')
        password = request.form.get('password')
        confirm = request.form.get('confirmation')
        profile_img = request.form.get('profile')
        file = None

        # If form is incomplete, return and flash apology:
        if not all([username, screen_name, password, confirm, profile_img]):
            flash('Please fill in all fields to register!')
            return render_template('register.html')

        # If password and confirmation do not match, return and flash apology:
        elif password != confirm:
            flash('Password and confirmation did not match! Please try again.')
            return render_template('register.html')

        # Ensure password meets password requirements:
        elif not validate_pass(password):
            flash('Password must be eight characters long with at least one number and one letter!')
            return render_template('register.html')

        # Check that file is uploaded if own profile img selected:
        if profile_img == 'user_upload':
          print('TRYING TO FIND USER IMAGE')
          # See https://flask.palletsprojects.com/en/1.1.x/patterns/fileuploads/
          if 'user_profile_img' not in request.files:
            flash('No profile image uploaded for custom icon!')
            return render_template('register.html')

          file = request.files['user_profile_img']
          print('FILE FOUND: ', file)
          # If no filename:
          if file.filename == '':
            flash('No custom profile image selected!')
            return render_template('register.html')
          if not file or not allowed_file(file.filename):
            flash('File type not supported! Please try again.')
            return render_template('register.html')

        # Otherwise information from registration is complete:

        # Check username does not already exist, if it does then ask for a different name:
        user_query = User.query.filter_by(username=username).first()

        if user_query:
          flash('Sorry but that username is already in use, please pick a different username!')
          return render_template('register.html')

        # Otherwise add user to database using hashed password:
        pass_hash = generate_password_hash(password)

        # Add new user to users table:
        new_user = User(username=username, screen_name=screen_name, pass_hash=pass_hash, profile_img=profile_img)
        db.session.add(new_user)
        db.session.commit()

        # Put unique user ID and username into session:
        user_info = User.query.filter_by(username=username).first()
        load_user(user_info)

        # If user uploaded a custom image file, add its path to DB, and save in Images folder:
        if file:

          filename = secure_filename(str(session['user_id']) + '.' + file.filename.split('.')[-1])
          file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
          session['profile_img'] = filename
          user_info.profile_img = filename
          db.session.commit()

        # Go to main chat page
        return redirect('/')

    # If User reaches Route via GET (e.g. clicking registration link):
    else:
        return render_template('register.html')


@app.route('/logout')
def logout():
    """Log user out"""

    # If user not logged in return to login screen:
    if session.get('user_id') == None:
        return redirect('/login')

    # Forget any user session info
    session.clear()

    # Redirect user to home page
    flash('You have been logged out from Flack Teams. See you again soon!')
    return redirect('/login')

# Error Handler
def errorhandler(e):
    """Handles access to non-supported routes, redirects to index"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return redirect('/')

# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


"""
================================================================================
SOCKET IO FUNCTIONS
================================================================================
"""

@socketio.on('initial logon')
def init_logon():
  """ Initial set up of client history and local storage for app functionality """

  # Join a private room for the user:
  join_room(f'{(session["user_id"],)}')

  # Load user ws, channel and private history
  user_info = User.query.get(session['user_id'])
  load_hist(user_info)
  load_private(session['user_id'])

  # Set up local storage for client
  user_sid = request.sid
  emit('local storage setup', {'user_id' : session['user_id']}, room=user_sid)


@socketio.on('join workspace')
def join_workspace(data):
  """ Joins a user to a workspace and a channel in that workspace """

  print('JOINING WORKSPACE')

  # If switching channels, sign out of current workspace and update current ws/chan:
  if not data['sign in']:
    leave_room(session['curr_ws'])
    leave_room(session['curr_ws_chan'])

    # Update online users in workspace
    workspaces[session['curr_ws']]['users_online'].remove(session['user_id'])
    update_ws_users(session['curr_ws'])

    # Join new workspace on default announcements channel
    session['curr_ws'] = data['workspace']
    session['curr_chan'] = 'Announcements'
    session['curr_ws_chan'] = f'{session["curr_ws"]}~{session["curr_chan"]}'

  # If workspace no longer exists (e.g. deleted), revert to default ws and channel:
  if not workspaces.get(session['curr_ws']):
      print('WORKSPACE NO LONGER EXISTS, GOING TO DEFAULT WS')
      session['curr_ws'] = 'Welcome!'
      session['curr_chan'] = 'Getting Started'
      session['curr_ws_chan'] = f'{session["curr_ws"]}~{session["curr_chan"]}'

  # Join chat for specified workspace and channel
  join_room(session['curr_ws'])
  join_room(session['curr_ws_chan'])

  user_sid = request.sid

  data['channel'] = session['curr_chan']

  # Log on to workspace and send user list of all workspaces:
  emit('workspace logon', {'workspace_name' : session['curr_ws']}, room=user_sid)
  workspace_list = list(workspaces.keys())
  emit('workspace_list amended', {'workspace_list': workspace_list}, room=user_sid)

  # Log user into channel and send user list of all channels in the workspace:
  join_channel(data)
  channel_list = list(workspaces[session['curr_ws']]['channels'].keys())
  emit('channel_list amended', {'channel_list': channel_list}, room=user_sid)

  # Update number of users in workspace:
  workspaces[session['curr_ws']]['users_online'].add(session['user_id'])
  update_ws_users(session['curr_ws'])

  # Update user's workspace history in DB:
  user_info = User.query.get(session['user_id'])
  user_info.curr_ws = session['curr_ws']
  user_info.curr_chan = session['curr_chan']
  db.session.commit()


@socketio.on('join channel')
def join_channel(data):
  """ Lets a user join a specific channel, relays last 100 messages from the channel to that specific user """

  # Leave the previous channel and join the new channel:
  leave_room(session['curr_ws_chan'])

  print('JOINING CHANNEL')

  # Check that channel exists in ws, if not then go to default Announcements channel:
  if not workspaces[session['curr_ws']]['channels'].get(data['channel']):
    session['curr_chan'] = 'Announcements'
  else:
    session['curr_chan'] = data['channel']

  session['curr_ws_chan'] = f"{session['curr_ws']}~{session['curr_chan']}"
  join_room(session['curr_ws_chan'])
  user_sid = request.sid

  current_chan = workspaces[session['curr_ws']]['channels'][session['curr_chan']]

  # Send sorted channel history back to user who has just joined:
  message_history = sorted(list(current_chan['messages'].values()), key = lambda x : x['message_timestamp'])

  emit('channel logon', {'channel_name' : session['curr_chan'], 'message_history' : message_history}, room=user_sid)

  # Update user's channel history in DB:
  user_info = User.query.get(session['user_id'])
  user_info.curr_chan = session['curr_chan']
  db.session.commit()


@socketio.on('join private')
def join_private(data):
  """ Lets a user joing a specific private chat room with one other user, relays last
  100 messages from that private chat """

  private_id = (int(data['user_1']), int(data['user_2']))

  # Check that user can join the private chat:
  if session['user_id'] not in private_id:
    # Send some kind of error message
    return False

  # Leave the previous private channel and join new one:
  leave_room(session['curr_private'])

  print('JOINING PRIVATE CHAT')

  # Check that private exists in private_channels, if not then go to default memo:
  if not private_channels['channels'].get(private_id):
    session['curr_private'] = (session['user_id'], session['user_id'])
  else:
    session['curr_private'] = private_id

  join_room(session['curr_private'])
  user_sid = request.sid

  private_chan = private_channels['channels'][session['curr_private']]
  private_name = private_channels['user_private_list'][session['user_id']][private_id]['name']

  # Send private message history to user joining:
  message_history = sorted(list(private_chan['messages'].values()), key = lambda x : x['message_timestamp'])

  emit('private logon', {'channel_name' : private_name, 'message_history' : message_history}, room=user_sid)

  # NEED TO SAVE TO DB HERE


@socketio.on('send message')
def send_message(data):
  """ Sends a message to all users in the same room, and stores the message on the server """

  print('Server has received a message, Sending message to users in channel')

  # Get data from incoming message:
  message_text = sanitize_message(data['message'])
  screen_name = session['screen_name']
  workspace = session['curr_ws']
  channel = session['curr_chan']
  ws_channel = session['curr_ws_chan']
  private = session['curr_private']
  profile_img = session['profile_img']

  # Create message object:

  message = {'user_id': session['user_id'],
             'message_text': message_text,
             'screen_name': screen_name,
             'message_date': datetime.now().strftime('%d %b %Y'),
             'message_timestamp': datetime.now(pytz.utc).timestamp(),
             'profile_img': profile_img,
             'edited': False,
             'edit_text': None,
             'edit_date': None,
             'deleted' : False
            }

  # If public channel message, save to workspaces
  if not data['private']:
    # Save message data to channel log:
    next = workspaces[workspace]['channels'][channel]['next_message']
    message['message_id'] = next
    message['private'] = False
    workspaces[workspace]['channels'][channel]['messages'][next] = message

    # Store up to 100 messages, then overwrite the first message
    workspaces[workspace]['channels'][channel]['next_message'] += 1
    if workspaces[workspace]['channels'][channel]['next_message'] > 100:
      workspaces[workspace]['channels'][channel]['next_message'] = 1

    emit('emit message', {'message': message, 'private': False}, room=ws_channel)

  # If private channel message, save to private_channels
  else:
    # Save message to private channel log:
    next = private_channels['channels'][private]['next_message']
    message['message_id'] = next
    message['private'] = True
    private_channels['channels'][private]['messages'][next] = message

    # Store up to 100 messages, the overwrite the first message
    private_channels['channels'][private]['next_message'] += 1
    if private_channels['channels'][private]['next_message'] > 100:
      private_channels['channels'][private]['next_message'] = 1

    emit('emit message', {'message': message, 'private': True}, room=private)


@socketio.on('delete message')
def delete_message(data):
  """ Deletes a message in a specific channel. Removes that message for all users. """

  print('TRYING TO DELETE MESSAGE')

  timestamp = float(data['timestamp'])
  message_id = int(data['message_id'])
  private = data['private']

  if not private:
    # Check if message exists in workspaces
    messages = workspaces[session['curr_ws']]['channels'][session['curr_chan']]['messages']
    room = session['curr_ws_chan']
  else :
    # Check if message exists in private_channels
    messages = private_channels['channels'][session['curr_private']]['messages']
    room = session['curr_private']

  # Check if message exists and user is allowed to delete it:
  if messages.get(message_id) and (messages[message_id]['message_timestamp'] == timestamp) and (session['user_id'] == messages[message_id]['user_id']):

    messages[message_id]['message_text'] = 'This message was deleted'
    messages[message_id]['edited'] = True
    messages[message_id]['edit_text'] = 'Message Deleted'
    messages[message_id]['edit_date'] = datetime.now().strftime('%d %b %Y')
    messages[message_id]['deleted'] = True

    emit('emit edited message', {'message_id': message_id, 'timestamp': timestamp, 'edited_text': messages[message_id]['message_text'], 'edit_type': messages[message_id]['edit_text'], 'edit_date': messages[message_id]['edit_date'], 'deleted': True, 'private': private}, room=session['curr_ws_chan'])


@socketio.on('edit message')
def edit_message(data):
  """ Edit the text of a message in a specific channel. Updates the message for all users """

  print('TRYING TO EDIT MESSAGE')

  timestamp = float(data['timestamp'])
  message_id = int(data['message_id'])
  text = sanitize_message(data['message_text'])
  private = data['private']

  if not private:
    # Check if message exists in workspaces
    messages = workspaces[session['curr_ws']]['channels'][session['curr_chan']]['messages']
    room = session['curr_ws_chan']
  else :
    # Check if message exists in private_channels
    messages = private_channels['channels'][session['curr_private']]['messages']
    room = session['curr_private']

  # Check if message exists and user is allowed to edit it:
  if messages.get(message_id) and (messages[message_id]['message_timestamp'] == timestamp) and (session['user_id'] == messages[message_id]['user_id']):

    messages[message_id]['message_text'] = text
    messages[message_id]['edited'] = True
    messages[message_id]['edit_text'] = 'Message Edited'
    messages[message_id]['edit_date'] = datetime.now().strftime('%d %b %Y')

    emit('emit edited message', {'message_id': message_id, 'timestamp': timestamp, 'edited_text': messages[message_id]['message_text'], 'edit_type': messages[message_id]['edit_text'], 'edit_date': messages[message_id]['edit_date'], 'deleted': False, 'private': private}, room=room)


@socketio.on('create channel')
def create_channel(data):
  """ Lets a user create a new chat channel in a ws, with a unique name in that ws."""

  chan_name = sanitize_name(data['new_channel'])

  # Check name not already in use in current workspace:
  if chan_name in workspaces[session['curr_ws']]['channels'].keys():
    # This should send back some kind of error message
    return False

  # Otherwise create a new chat channel and send channel list to all users:
  workspaces[session['curr_ws']]['channels'][chan_name] = {'messages': {}, 'next_message': 1}

  channel_list = list(workspaces[session['curr_ws']]['channels'].keys())

  # Send updated channel list to all users in the workspace:
  emit('channel_list amended', {'channel_list': channel_list}, room=session['curr_ws'])


@socketio.on('create workspace')
def create_workspace(data):
  """ Lets a user create a new workspace, with a unique name. The user then joins the new workspace """

  ws_name = sanitize_name(data['new_workspace'])

  # Check new workspace name not already in use:
  if ws_name in workspaces.keys():
    # This should send back some kind of error message
    return False

  timestamp = datetime.now(pytz.utc).timestamp()
  date = datetime.now().strftime('%d %b %Y')

  # Otherwise create a new workspace:
  workspaces[ws_name] = {'channels': {'Announcements': {'messages': {1 : {'message_text': f'Welcome to your new workspace - {ws_name}!', 'screen_name': 'Flack-Teams Help', 'message_timestamp': timestamp, 'message_date': date, 'message_id': 1, 'profile_img': 'admin.png', 'user_id': -1, 'edited': False, 'edit_text': None, 'edit_date': None, 'deleted' : False, 'private': False }}, 'next_message': 2}}, 'users_online': set()}

  # Broadcast new workspace creation:
  workspace_list = list(workspaces.keys())
  emit('workspace_list amended', {'workspace_list': workspace_list}, broadcast=True)

  # Join new workspace in Announcments channel:
  data = {'sign in': False, 'workspace': ws_name}
  join_workspace(data)


@socketio.on('create private channel')
def create_private_channel(data):
  """ Creates and joins a user to a private message channel between two users """

  print('TYRING TO CREATE PRIVATE CHANNEL ', data)

  # Determine the private channel name:
  target_id = int(data['target_id'])
  user_id = int(data['user_id'])

  private_chan = tuple(sorted([user_id, target_id]))

  # Check that client is the current session user:
  if session['user_id'] != user_id:
    # Return some sort of error message:
    return False

  # Check if private channel exists, if not then create it:
  if not private_channels['channels'].get(private_chan):
    private_channels['channels'][private_chan] = {'messages': {}, 'next_message': 1}

    # Create private channel list for target user if none:
    if not private_channels['user_private_list'].get(target_id):
      private_channels['user_private_list'][target_id] = {}

    private_channels['user_private_list'][target_id][private_chan] = {'name': session['screen_name']}

    # Get screenname of target user:
    target_screen_name = User.query.get(target_id).screen_name
    private_channels['user_private_list'][user_id][private_chan] = {'name': target_screen_name}

  # Send updated channel lists to both users:
  load_private(user_id)
  load_private(target_id)

  # Join the private message channel for requesting user:
  join_private({'user_1': private_chan[0], 'user_2': private_chan[1]})


@socketio.on('log out')
def socket_logout():

  print('USER LOGOUT RECEIVED')
  # Remove user from current workspace:
  workspaces[session['curr_ws']]['users_online'].remove(session['user_id'])
  update_ws_users(session['curr_ws'])

  leave_room(session['curr_ws'])
  leave_room(session['curr_ws_chan'])
  leave_room(f'{(session["user_id"],)}')

  # Forget any user session info
  session.clear()

  return redirect('/login')


if __name__ == '__main__':
  socketio.run(app)