# -*- coding: utf-8 -*-
# import urllib.request
import os
import requests
import random
# import sys
# import json
# from argparse import ArgumentParser

from flask import Flask, request, abort
from linebot import (LineBotApi, WebhookHandler)
from linebot.exceptions import (InvalidSignatureError)
from linebot.models import (
    MessageEvent, FollowEvent, UnfollowEvent, AccountLinkEvent, TextMessage, ImageMessage, AudioMessage,
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
    __tablename__ = "user"
    id = db.Column(db.Integer(), primary_key=True)
    line_id = db.Column(db.String(255), nullable=False)
    nonce = db.Column(db.String(255), default="")
    schedules = db.relationship('Schedule', backref='user')

    def __repr__(self):
        return "User<{}, {}, {}, {}>".format(
            self.id, self.line_id, self.nonce, self.schedules)


class Schedule(db.Model):
    __tablename__ = "schedule"
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
s1 = Schedule(user=u1)
"""


@app.route("/")
def hello():
    return "Hello, K-ON!"


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
    post = requests.post(url_items, headers=header)
    post_res = post.json()  # jsonに変換しなければいけない

    items = [URIAction(
        uri="http://k-on-schedule2.herokuapp.com/login/?linkToken=" + post_res["linkToken"], label="連携する"
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


@handler.add(UnfollowEvent)
def handle_unfollow(event):
    user = db.session.query(User).filter_by(line_id=event.source.user_id).first()
    # ここでアプリの方の認証情報を削除
    requests.post("http://k-on-schedule2.herokuapp.com/api/unfollow?nonce=" + user.nonce)

    db.session.delete(user)
    db.session.commit()


@handler.add(MessageEvent, message=(TextMessage, ImageMessage, AudioMessage))
def message_type(event):
    user = db.session.query(User).filter_by(line_id=event.source.user_id).first()
    if user.nonce == "":
        link_message(event)
    elif "予定" in event.message.text or "今週" in event.message.text or "練習" in event.message.text:
        schedule_message(event)
    elif "じゃんけん" in event.message.text or "うしけん" in event.message.text:
        rps_message(event)
    elif event.message.text in (chr(0x100030), chr(0x100031), chr(0x100032)):
        rps_result_message(event)
    else:
        quick_message(event)


def quick_message(event):
    # 1つのメッセージにクイックリプライボタンを13個まで設定できる
    menu_items = [QuickReplyButton(action=MessageAction(
        label=f"{menu}", text=f"{menu}"
    )) for menu in ["今週の予定", "うしけんじゃんけん"]]

    messages1 = TextSendMessage(
        text="何をするッスか？", quick_reply=QuickReply(items=menu_items)
    )

    line_bot_api.reply_message(event.reply_token, messages=messages1)


def link_message(event):
    user_id = event.source.user_id
    header = {'Authorization': 'Bearer {}'.format(YOUR_CHANNEL_ACCESS_TOKEN)}
    url_items = "https://api.line.me/v2/bot/user/" + user_id + "/linkToken"
    post = requests.post(url_items, headers=header)
    post_res = post.json()  # jsonに変換しなければいけない

    items = [URIAction(
        uri="http://localhost:5000/login/?linkToken=" + post_res["linkToken"], label="連携する"
    )]

    messages = TemplateSendMessage(alt_text="LINK", template=ButtonsTemplate(
        text="軽音スケジュールアプリと連携するッス！\nこのボタンの有効期限は10分ッス！", actions=items
    ))

    line_bot_api.reply_message(event.reply_token, messages=messages)


def schedule_message(event):
    exit()


def rps_message(event):
    message1 = TextSendMessage("うーしけーんじゃんけん、じゃんけん...")

    rps_items = [
        QuickReplyButton(action=MessageAction(
            label="グー！", text=chr(0x100032))),
        QuickReplyButton(action=MessageAction(
            label="チョキ！", text=chr(0x100030))),
        QuickReplyButton(action=MessageAction(
            label="パー！", text=chr(0x100031)))
    ]
    message2 = TemplateSendMessage(alt_text="RPS", template=ButtonsTemplate(actions=rps_items))

    line_bot_api.reply_message(event.reply_token, messages=[message1,message2])


def rps_result_message(event):
    x = random.randrange(1, 501)
    message1 = TextSendMessage("ポン！")

    # 相手がグー
    if event.message.text == chr(0x100032):
        if x == 1:
            message2 = TextSendMessage(chr(0x100030))
            message3 = TextSendMessage("自分の負けッス...\n完敗ッス。")
        else:
            message2 = TextSendMessage(chr(0x100031))
            message3 = TextSendMessage("自分の勝ちッス！\nいつでもかかってこいッス！")
    # 相手がチョキ
    elif event.message.text == chr(0x100030):
        if x == 1:
            message2 = TextSendMessage(chr(0x100031))
            message3 = TextSendMessage("自分の負けッス...\n完敗ッス。")
        else:
            message2 = TextSendMessage(chr(0x100032))
            message3 = TextSendMessage("自分の勝ちッス！\nいつでもかかってこいッス！")
    # 相手がパー
    else:
        if x == 1:
            message2 = TextSendMessage(chr(0x100032))
            message3 = TextSendMessage("自分の負けッス...\n完敗ッス。")
        else:
            message2 = TextSendMessage(chr(0x100030))
            message3 = TextSendMessage("自分の勝ちッス！\nいつでもかかってこいッス！")

    line_bot_api.reply_message(event.reply_token, messages=[message1, message2, message3])


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
        if u is None:
            continue
        for i in range(len(user["info"])):
            schedule = Schedule(user=u)
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
