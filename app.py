# -*- coding: utf-8 -*-
# import urllib.request
import os
import requests
# import sys
# import json
# from argparse import ArgumentParser

from flask import Flask, request, abort
from linebot import (LineBotApi, WebhookHandler)
from linebot.exceptions import (InvalidSignatureError)
from linebot.models import (
    MessageEvent, FollowEvent, AccountLinkEvent, TextMessage, ImageMessage, AudioMessage,
    TextSendMessage, QuickReplyButton,
    MessageAction, QuickReply,
    URIAction,  # ボタンを押すと指定したURLに飛べるアクション
    TemplateSendMessage, ButtonsTemplate
)
from werkzeug.security import *

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy import or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

app = Flask(__name__)

YOUR_CHANNEL_SECRET = os.environ["YOUR_CHANNEL_SECRET"]
YOUR_CHANNEL_ACCESS_TOKEN = os.environ["YOUR_CHANNEL_ACCESS_TOKEN"]

handler = WebhookHandler(YOUR_CHANNEL_SECRET)
line_bot_api = LineBotApi(YOUR_CHANNEL_ACCESS_TOKEN)

app.config['JSON_AS_ASCII'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL') or 'sqlite:///k-on.db'  # or 'postgresql://localhost/k-on"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = "User"
    id = db.Column(db.Integer(), primary_key=True)
    line_id = db.Column(db.String(255), nullable=False)
    nonce = db.Column(db.String(255))
    schedules = db.relationship('Schedule', backref='user_id')

    def __repr__(self):
        return "User<{}, {}, {}, {}>".format(
            self.id, self.line_id, self.nonce, self.schedules)


class Schedule(db.Model):
    __tablename__ = "Schedule"
    id = db.Column(db.Integer(), primary_key=True)
    info = db.Column(db.String(255), nullable=False)
    date = db.Column(db.Integer(), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return "Schedule<{}, {}, {}, {}>".format(
            self.id, self.info, self.date, self.user_id)


db.create_all()

"""
1対多のリレーションの説明

u1 = User(line_id="1234tanaka")
s1 = Schedule(user_id=u1)
"""


# Webhookからのリクエストをチェックする
@app.route("/callback", methods=['POST'])
def callback():
    # リクエストヘッダーからの値を取得
    signature = request.headers['X-Line-Signature']

    # リクエストボディを取得
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # 署名を検証し、handleに定義されている関数を呼び出す
    try:
        handler.handle(body, signature)

    # 失敗した場合、エラーを吐く
    except InvalidSignatureError:
        abort(400)

    return 'OK'


# 友達追加時イベント
@handler.add(FollowEvent)
def handle_follow(event):
    user = User()
    user.line_id = generate_password_hash(event.source.user_id)
    db.session.add(user)
    db.session.commit()

    header = {'Authorization': 'Bearer {}'.format(YOUR_CHANNEL_ACCESS_TOKEN)}
    url_items = "https://api.line.me/v2/bot/user/" + event.source.user_id + "/linkToken"
    post_res = requests.post(url_items, headers=header)

    items = [URIAction(
        uri="http://localhost:5000/login/?linkToken=" + post_res["linkToken"], label="連携する"
    )]

    reply_text = [
        TextSendMessage(text="浜キャン軽音リマインダーbotッス！友達追加ありがとッス！"),
        TextSendMessage(text="まずはスケジュールアプリとの連携をして欲しいッス！"),
        TemplateSendMessage(alt_text="LINK", template=ButtonsTemplate(
            text="軽音スケジュールアプリと連携するッス！\nこのボタンの有効期限は10分ッス！", actions=items
        ))
    ]

    line_bot_api.reply_message(
        event.reply_token, reply_text
    )


@handler.add(MessageEvent, message=(TextMessage, ImageMessage, AudioMessage))
def message_type(event):
    if event.message.text == "BBS":
        bbs_message(event)
    elif event.message.text == "MOVIE":
        movie_message(event)
    else:
        quick_message(event)


def quick_message(event):
    menu_list = ["BBS", "MOVIE"]

    menu_items = [QuickReplyButton(action=MessageAction(
        label=f"{menu}", text=f"{menu}"
    )) for menu in menu_list]

    messages1 = TextSendMessage(
        text="どれを参照しますか？", quick_reply=QuickReply(items=menu_items)
    )

    line_bot_api.reply_message(event.reply_token, messages=messages1)


def bbs_message(event):
    year_list = ["16", "17", "18"]  # 2019年度はURLが違うため後に追加

    bbs_items = [URIAction(
        uri=f"https://shkeion{year}.jimdo.com/bbs/", label=f"20{year}"
    ) for year in year_list]

    bbs_items.append(URIAction(
        uri=f"https://shkeion19.jimdofree.com/bbs/", label=f"2019"
    ))

    messages2 = TemplateSendMessage(alt_text="BBS", template=ButtonsTemplate(
        text="どの年度を参照しますか？", actions=bbs_items
    ))

    line_bot_api.reply_message(event.reply_token, messages=messages2)


def movie_message(event):
    year_list = ["16", "17", "18"]  # 2019年度はURLが違うため後に追加

    movie_items = [URIAction(
        uri=f"https://shkeion{year}.jimdo.com/movie/", label=f"20{year}"
    ) for year in year_list]

    movie_items.append(URIAction(
        uri=f"https://shkeion19.jimdofree.com/movie/", label=f"2019"
    ))

    messages2 = TemplateSendMessage(alt_text="MOVIE", template=ButtonsTemplate(
        text="どの年度を参照しますか？", actions=movie_items
    ))

    line_bot_api.reply_message(event.reply_token, messages=messages2)


def start_link(event):
    user_id = event.source.user_id
    header = {'Authorization': 'Bearer {}'.format(YOUR_CHANNEL_ACCESS_TOKEN)}
    url_items = "https://api.line.me/v2/bot/user/" + str(user_id) + "/linkToken"
    post_res = requests.post(url_items, headers=header)

    items = [URIAction(
        uri="http://localhost:5000/login/?linkToken=" + post_res["linkToken"], label="連携する"
    )]

    messages = TemplateSendMessage(alt_text="LINK", template=ButtonsTemplate(
        text="軽音スケジュールアプリと連携するッス！\nこのボタンの有効期限は10分ッス！", actions=items
    ))

    line_bot_api.reply_message(event.reply_token, messages=messages)


@handler.add(AccountLinkEvent)
def account_link(event):
    if event.link.result == "ok":
        user = db.session.query(User).filter_by(line_id=event.source.user_id).first()
        user.nonce = event.link.nonce
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='認証が成功したッス！')
        )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='認証失敗ッス...もう一度試して欲しいッス。')
        )


@app.route("/api/create_schedule", methods=['POST'])
def create_schedule():
    for user in request.json["users"]:
        u = db.session.query(User).filter_by(nonce=user["nonce"]).first()
        for i in range(len(user["info"])):
            schedule = Schedule(user_id=u.id)
            schedule.info = user["info"][i]
            schedule.date = int(user["date"][i])
            db.session.add(schedule)
            db.session.commit()


### ボタンを押すとそのメッセージが送信され、URLが返信されるバージョン ###
# items1 = [QuickReplyButton(action=MessageAction(label=f"{menu}", text=f"{menu}")) for menu in menu_list]
# items2 = [QuickReplyButton(action=MessageAction(label=f"{year}", text=f"{year}")) for year in year_list]

### 愚直にappendするバージョン。後で見てわかるように。 ###
"""
bbs_items = []
movie_items = []
### BBSの設定 ###
bbs_items.append(QuickReplyButton(action=URIAction(
    uri="https://shkeion16.jimdo.com/bbs/", label="2016"
)))
bbs_items.append(QuickReplyButton(action=URIAction(
    uri="https://shkeion17.jimdo.com/bbs/", label="2017"
)))
bbs_items.append(QuickReplyButton(action=URIAction(
    uri="https://shkeion18.jimdo.com/bbs/", label="2018"
)))
bbs_items.append(QuickReplyButton(action=URIAction(
    uri="https://shkeion19.jimdofree.com/bbs/", label="2019"
)))
### MOVIEの設定 ###
movie_items.append(QuickReplyButton(action=URIAction(
    uri="https://shkeion16.jimdo.com/movie/", label="2016"
)))
movie_items.append(QuickReplyButton(action=URIAction(
    uri="https://shkeion17.jimdo.com/movie/", label="2017"
)))
movie_items.append(QuickReplyButton(action=URIAction(
    uri="https://shkeion18.jimdo.com/movie/", label="2018"
)))
movie_items.append(QuickReplyButton(action=URIAction(
    uri="https://shkeion19.jimdofree.com/movie/", label="2019"
)))
"""

if __name__ == "__main__":
    port = int(os.getenv("PORT"))
    app.run(host="0.0.0.0", port=port)
