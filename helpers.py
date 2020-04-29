import re
import pytz
import os
from flask import session, request
from flask_socketio import emit
from werkzeug.utils import secure_filename
from datetime import datetime
from models import *

def sanitize_message(message):
  """ Helper function that takes a user's message string and replaces special HTML chars with their HTML entities to keep the chars and prevent adding HTML to the message board

  Returns the sanitized message string
  """

  return message.replace('&', '&#38;').replace('"', '&#34;').replace('\'', '&#39;').replace('<', '&#60;').replace('>', '&#62;').replace('`', '&#96;').replace('=', '&#61;')


def sanitize_name(name):
  """ Helper function to remove non-permitted characters from a channel or workspace name
  Non-permitted characters are HTML special chars &, ", ', <, >, `, = and (, ), ~.

  Returns the sanitize channel/ws name
  """

  return name.replace('&', '').replace('"', '').replace('\'', '').replace('<', '').replace('>', '').replace('(', '').replace(')', '').replace('~', '').replace('`', '').replace('=', '')


def is_whitespace(string):
  """ Helper function to test if a string is all whitespace characters """

  ws = re.compile('^\s+$')
  return ws.match(string)


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


def load_user(user, session):
  """ Loads a user's personal information from DB into the session """

  session['user_id'] = user.id
  session['username'] = user.username
  session['screen_name'] = user.screen_name
  session['profile_img'] = user.profile_img


def load_hist(user, session):
  """ Loads a user's ws and channel hist from DB into the session """

  session['curr_ws'] = user.curr_ws
  session['curr_chan'] = user.curr_chan
  session['curr_ws_chan'] = f'{session["curr_ws"]}~{session["curr_chan"]}'
  session['curr_private'] = (session['user_id'], session['user_id'])


def load_private(user_id, private_channels):
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


def update_ws_users(ws_name, workspaces):
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


def update_profile(update_val, update_key, workspaces, private_channels):
  """ Helper function to update a user's screen name or profile icon """

  # Update screen_name in all channels:
  for workspace in workspaces:
    for channel in workspaces[workspace]['channels']:
      for message in workspaces[workspace]['channels'][channel]['messages']:
        if workspaces[workspace]['channels'][channel]['messages'][message]['user_id'] == session['user_id']:
          workspaces[workspace]['channels'][channel]['messages'][message][update_key] = update_val

  # Update screen_name in private chats:
  for channel in private_channels['channels']:
    if session['user_id'] in channel:
      for message in private_channels['channels'][channel]['messages']:
        if private_channels['channels'][channel]['messages'][message]['user_id'] == session['user_id']:
          private_channels['channels'][channel]['messages'][message][update_key] = update_val

  if update_key == 'screen_name':
    # Update screen_name for private chat links:
    for user_id in private_channels['user_private_list']:
      if user_id != session['user_id']:
        for private_id in private_channels['user_private_list'][user_id]:
          if session['user_id'] in private_id:
            private_channels['user_private_list'][user_id][private_id]['name'] = update_val


def check_img_upload():
  """ Helper Function to check if a custom profile icon has been uploaded successfully
  """
  # See https://flask.palletsprojects.com/en/1.1.x/patterns/fileuploads/
  if 'user_profile_img' not in request.files:
    return (False, 'No profile image uploaded for custom icon!')

  file = request.files['user_profile_img']
  print('FILE FOUND: ', file)
  # If no filename:
  if file.filename == '':
    return (False, 'No custom profile image selected!')
  if not file or not allowed_file(file.filename):
    return (False, 'File type not supported! Please try again.')

  return (True, file)


def save_user_img(file, app):
  """ Helper Function to save user profile image to the directory
  file is an image file object
  """
  filename = secure_filename(str(session['user_id']) + '.' + file.filename.split('.')[-1])
  file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
  session['profile_img'] = filename


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
  """ Helper Function to check if file upload type is permitted """
  return '.' in filename and \
    filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS