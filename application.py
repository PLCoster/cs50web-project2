import os

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room

from datetime import datetime
import pytz

# Flask App Configuration
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
socketio = SocketIO(app)

# Server Message Channel Storage
channels = {'Home': {'messages': {}, 'next_message': 1 , 'subchannels':{}}}


def sanitize_message(message):
  """ Helper function that takes a user's message string and replaces special HTML chars with their HTML entities to keep the chars and prevent adding HTML to the message board

  Returns the sanitized message string
  """

  return message.replace('&', '&amp;').replace('"', '&quot;').replace('\'', '&apos;').replace('<', '&lt;').replace('>', '&gt;')


@app.route("/")
def index():
  return render_template("index.html")


@socketio.on("send message")
def send_message(data):
  """ Sends a message to all users in the same room, and stores the message on the server """

  print('Server has received a message, Sending message to users in room')

  # Get data from incoming message:
  message_text = sanitize_message(data["message"])
  screen_name = data["screen_name"]

  # Date and Timestamp the message:
  timestamp = datetime.now(pytz.utc).timestamp()
  date = datetime.now().strftime("%d %b %Y")

  # Save message data to channel log:
  next = channels['Home']['next_message']
  message = [message_text, screen_name, timestamp, date, next]
  channels['Home']['messages'][next] = message

  print('Message received by server:', message)

  # Store up to 100 messages, then overwrite the first message
  channels['Home']['next_message'] += 1
  if channels['Home']['next_message'] > 100:
    channels['Home']['next_message'] = 1

  emit("announce vote", {"message": message}, broadcast=True)


@socketio.on("join channel")
def join_channel(data):
  """ Lets a user join a specific channel, relays last 100 messages from the channel to that specific user """
  room = data['channel']
  join_room(room)
  user = request.sid

  # Send sorted channel history back to user who has just joined:
  message_history = sorted(list(channels[room]['messages'].values()), key = lambda x : x[2])

  print(sorted(list(channels[room]['messages'].values()), key = lambda x : x[2]))
  print('Channel status:', channels)
  print('Sending message history:', message_history)

  if message_history:
    emit("channel logon", {"message_history" : message_history}, room=user)


if __name__ == '__main__':
  socketio.run(app)