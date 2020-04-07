import os

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
socketio = SocketIO(app)


@app.route("/")
def index():
    return render_template("index.html")

@socketio.on("send message")
def vote(data):
    message = data["message"]
    screen_name = data["screen_name"]
    emit("announce vote", {"message": message, "screen_name": screen_name}, broadcast=True)


if __name__ == '__main__':
    socketio.run(app)