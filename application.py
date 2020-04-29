import os
import pytz

from flask import Flask, session, flash, jsonify, redirect, render_template, request
from flask_session import Session
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from datetime import datetime

from models import *
from helpers import sanitize_message, sanitize_name, is_whitespace, validate_pass,\
  load_user, load_hist, load_private, update_ws_users, update_profile, check_img_upload,\
  save_user_img, allowed_file

if not os.getenv('DATABASE_URL'):
  raise RuntimeError('DATABASE_URL is not set')

if not os.getenv('SECRET_KEY'):
  raise RuntimeError('SECRET_KEY is not set')

if not os.getenv('UPLOAD_FOLDER'):
  raise RuntimeError('UPLOAD_FOLDER is not set')

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
        load_user(user_info, session)

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

      # If any input is just whitespace chars, ask for new input:
      if is_whitespace(username) or is_whitespace(screen_name) or is_whitespace(password):
        flash('Please fill in all fields to register!')
        return render_template('register.html')

      # Check that file is uploaded if own profile img selected:
      if profile_img == 'user_upload':

        result = check_img_upload()

        if not result[0]:
          flash(result[1])
          return render_template('register.html')
        else :
          file = result[1]

      # Otherwise information from registration is complete
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
      load_user(user_info, session)

      # If user uploaded a custom image file, add its path to DB, and save in Images folder:
      if file:
        save_user_img(file, app)
        user_info.profile_img = session['profile_img']
        db.session.commit()

      # Go to main chat page
      return redirect('/')

    # If User reaches Route via GET (e.g. clicking registration link):
    else:
      return render_template('register.html')


@app.route('/account', methods=['GET', 'POST'])
def account():
  """ Show user Account Settings Page, To Change Password, Screen-name or Icon """

  # If user not logged in return to login screen:
  if session.get('user_id') == None:
    return redirect('/login')

  # User reached route via POST (by submitting password change form):
  if request.method == "POST":

    # Get input from form:
    curr_pass = request.form.get("curr-pass")
    new_pass = request.form.get("new-pass")
    confirm = request.form.get("check-pass")

    # Check input fields are correct:
    if not curr_pass or not new_pass or new_pass != confirm or is_whitespace(new_pass):
      flash("Please fill in all password fields!")
      return render_template("account.html")

    # Get current password hash to check it matches:
    user_info = User.query.get(session['user_id'])
    logged_pass = user_info.pass_hash

    if not check_password_hash(logged_pass, curr_pass):
      flash("Incorrect current password entered, please try again!")
      return render_template("account.html")

    # Ensure password meets password requirements
    elif not validate_pass(new_pass):
      flash("New password does not meet requirements - must be at least eight chars long including one number and one letter!")
      return render_template("account.html")

    # Otherwise generate new password hash and update the password hash in DBfor this user:
    new_pass_hash = generate_password_hash(new_pass)
    user_info.pass_hash = new_pass_hash
    db.session.commit()

    flash('Password successfully updated!')
    return redirect('/account')

  # User reached route via GET (as by clicking acount link)
  else:
    return render_template('account.html')


@app.route('/screen_name', methods=['POST'])
def screen_name():
  """ Update a user's screen name in the database and all chat messages """

  # If user not logged in return to login screen:
  if session.get('user_id') == None:
    return redirect('/login')

  # Get input from form and check screen-name exists:
  new_screen_name = request.form.get("new-screen-name")

  if not new_screen_name or is_whitespace(new_screen_name):
    flash('Please enter your new Screen Name to update it!')
    return redirect('/account')

  # Update screen_name in database and session:
  user_info = User.query.get(session['user_id'])
  user_info.screen_name = new_screen_name
  db.session.commit()
  session['screen_name'] = new_screen_name

  update_profile(session['screen_name'], 'screen_name', workspaces, private_channels)

  flash('Your Screen Name has been changed to: ' + session['screen_name'])
  return redirect('/account')


@app.route('/profile_img', methods=['POST'])
def profile_img():
  """ Update a user's profile image to a new one """

  # If user not logged in return to login screen:
  if session.get('user_id') == None:
    return redirect('/login')

  profile_img = request.form.get('profile')

  # If none selected, prompt user for selection:
  if not profile_img:
    flash('Please select a default or custom Profile Icon!')
    return redirect('/account')

  # If choice is the same as current, do nothing:
  if profile_img == session['profile_img']:
    flash('The icon you selected is currently your Profile Icon!')
    return redirect('/account')

  # If profile_img is a custom image, get and check the custom image:
  if profile_img == 'user_upload':

    result = check_img_upload()

    if not result[0]:
      flash(result[1])
      return redirect('/account')
    else :
      file = result[1]

    # If user uploaded a custom image file,  save in Images folder:
    if file:
      save_user_img(file, app)

  # Otherwise set user_profile img to default img:
  else:
    session['profile_img'] = profile_img

  # Update profile_img in database:
  user_info = User.query.get(session['user_id'])
  user_info.profile_img = session['profile_img']
  db.session.commit()

  update_profile(session['profile_img'], 'profile_img', workspaces, private_channels)

  flash('Profile Image Successfully Changed! You may need to refresh the browser.')
  return redirect('/account')


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
  load_hist(user_info, session)
  load_private(session['user_id'], private_channels)

  # Set up local storage for client
  user_sid = request.sid
  emit('local storage setup', {'user_id' : session['user_id'], 'channel' : session['curr_chan'], 'private' : session['curr_private']}, room=user_sid)


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
    update_ws_users(session['curr_ws'], workspaces)

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
  update_ws_users(session['curr_ws'], workspaces)

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

  # If message text is all whitespace, do nothing:
  if is_whitespace(message_text):
    return False

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
    emit('channel alert', {'channel': channel, 'private': False}, room=workspace)

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

    # Get correct room and channel name to emit alert to target user:
    for target_id in session['curr_private']:
      if target_id != session['user_id']:
        channel = private_channels['user_private_list'][target_id][session['curr_private']]['name']
        target_room = f'{(target_id,)}'

    emit('channel alert', {'channel': channel, 'private': True}, room=target_room)


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

  # If message text is all whitespace, do nothing:
  if is_whitespace(text):
    return False

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

  # If name is all whitespace, do nothing:
  if is_whitespace(chan_name):
    return False

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

  # If name is all whitespace, do nothing:
  if is_whitespace(ws_name):
    return False

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

  print('TRYING TO CREATE PRIVATE CHANNEL ', data)

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
  load_private(user_id, private_channels)
  load_private(target_id, private_channels)

  # Join the private message channel for requesting user:
  join_private({'user_1': private_chan[0], 'user_2': private_chan[1]})


@socketio.on('log out')
def socket_logout():

  print('USER LOGOUT RECEIVED')
  # Remove user from current workspace:
  workspaces[session['curr_ws']]['users_online'].remove(session['user_id'])
  update_ws_users(session['curr_ws'], workspaces)

  leave_room(session['curr_ws'])
  leave_room(session['curr_ws_chan'])
  leave_room(session['curr_private'])

  # Forget any user session info
  session.clear()


if __name__ == '__main__':
  socketio.run(app)