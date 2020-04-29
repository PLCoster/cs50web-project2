from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, nullable=False, unique=True)
    screen_name = db.Column(db.String, nullable=False)
    pass_hash = db.Column(db.String, nullable=False)
    workspaces = db.Column(db.Text, nullable=False, default='{}')
    profile_img = db.Column(db.String, nullable=False)
    curr_ws = db.Column(db.String, nullable=False, default='Welcome!')
    curr_chan = db.Column(db.String, nullable=False, default='Getting Started')
