import os

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit

from datetime import datetime
import pytz

# Flask App Configuration
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
socketio = SocketIO(app)

# Server Message Channel Storage
channels = {'Home': {'messages': {}, 'next_message': 1 , 'subchannels':{}}}


@app.route("/")
def index():
  return render_template("index.html")


@socketio.on("send message")
def vote(data):

  # Get data from incoming message:
  message_text = data["message"]
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


if __name__ == '__main__':
  socketio.run(app)