import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'kunci-rahasia-cafe'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:@localhost/cafe_order'
    SQLALCHEMY_TRACK_MODIFICATIONS = False