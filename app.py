# -*- coding: utf-8 -*-
#import urllib.request
import os
#import sys
#import json
#from argparse import ArgumentParser

from flask import Flask, request, abort
from linebot import (LineBotApi, WebhookHandler)
from linebot.exceptions import (InvalidSignatureError)
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, AudioMessage,
    TextSendMessage, QuickReplyButton,
    MessageAction, QuickReply,
    URIAction, #ボタンを押すと指定したURLに飛べるアクション
    TemplateSendMessage, ButtonsTemplate
)

app = Flask(__name__)

YOUR_CHANNEL_SECRET = os.environ["YOUR_CHANNEL_SECRET"]
YOUR_CHANNEL_ACCESS_TOKEN = os.environ["YOUR_CHANNEL_ACCESS_TOKEN"]

handler = WebhookHandler(YOUR_CHANNEL_SECRET)
line_bot_api = LineBotApi(YOUR_CHANNEL_ACCESS_TOKEN)

#Webhookからのリクエストをチェックする
@app.route("/callback", methods=['POST'])
def callback():
    #リクエストヘッダーからの値を取得
    signature = request.headers['X-Line-Signature']

    #リクエストボディを取得
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    #署名を検証し、handleに定義されている関数を呼び出す
    try:
        handler.handle(body, signature)

    #失敗した場合、エラーを吐く
    except InvalidSignatureError:
        abort(400)

    return 'OK'

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
    year_list = ["16", "17", "18"] #2019年度はURLが違うため後に追加

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
    year_list = ["16", "17", "18"] #2019年度はURLが違うため後に追加

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

### ボタンを押すとそのメッセージが送信され、URLが返信されるバージョン ###
#items1 = [QuickReplyButton(action=MessageAction(label=f"{menu}", text=f"{menu}")) for menu in menu_list]
#items2 = [QuickReplyButton(action=MessageAction(label=f"{year}", text=f"{year}")) for year in year_list]

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