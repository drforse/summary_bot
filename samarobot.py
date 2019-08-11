#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ssl
from aiohttp import web
import telebot
import json
import datetime
import pytz
import re

API_TOKEN = '' #put your token here

WEBHOOK_HOST = '' #hostname
WEBHOOK_PORT = 88  # 443, 80, 88 or 8443 (port need to be 'open')
WEBHOOK_LISTEN = '0.0.0.0'  # In some VPS you may need to put here the IP addr

WEBHOOK_SSL_CERT = './webhook_cert.pem'  # Path to the ssl certificate
WEBHOOK_SSL_PRIV = './webhook_pkey.pem'  # Path to the ssl private key

WEBHOOK_URL_BASE = "https://{}:{}".format(WEBHOOK_HOST, WEBHOOK_PORT)
WEBHOOK_URL_PATH = "/{}/".format(API_TOKEN)

CHAT_TIMEZONE = 'Europe/Moscow'
try:
    tzfile = open('/etc/timezone', 'r')
    LOCAL_TIMEZONE = tzfile.read().strip()
    tzfile.close()
except FileNotFoundError:
    LOCAL_TIMEZONE = CHAT_TIMEZONE

bot = telebot.TeleBot(API_TOKEN)
app = web.Application()
history = open('base.txt', 'r')
data = json.load(history)
history.close()

# Process webhook calls
async def handle(request):
    if request.match_info.get('token') == bot.token:
        request_body_dict = await request.json()
        update = telebot.types.Update.de_json(request_body_dict)
        bot.process_new_updates([update])
        return web.Response()
    else:
        return web.Response(status=403)

app.router.add_post('/{token}/', handle)

# Handle '/start' and '/help'
@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):
    bot.reply_to(message, ("Напишите всамару в начале сообщения или в ответ на сообщение чтобы сохранить\nНапишите самара за 200 чтобы получить самару за 200"))

# Handle all other messages
@bot.message_handler(func=lambda message: True, content_types=['text'])
def process_msg(message):
    if str(message.text).upper().startswith('ВСАМАРУ'):
        if not str(message.chat.id) in data.keys():
            data[str(message.chat.id)] = {"saved": {}}
        if message.reply_to_message == None:
            saveText = message.text[message.text.find(' ')+1:]
            sourceId = message.message_id
        else:
            if message.reply_to_message.from_user.is_bot:
                bot.send_message(message.chat.id, "Я собратьев-ботов в себя не добавляю, извращенцы!")
                return
            sourceId = message.reply_to_message.message_id
            if message.reply_to_message.from_user.username:
                name = message.reply_to_message.from_user.username
            else:
                name = message.reply_to_message.from_user.first_name
            saveText = name + ": " + message.reply_to_message.text
        if type(saveText) == type("str"):
            if not "ids" in data[str(message.chat.id)].keys():
                data[str(message.chat.id)]["ids"] = []
            if sourceId in data[str(message.chat.id)]["ids"]:
                bot.send_message(message.chat.id, "Это уже есть в самаре")
                return
            data[str(message.chat.id)]["ids"].append(sourceId)
            data[str(message.chat.id)]["saved"][str(message.message_id)] = {'date': message.date, 'text': saveText.replace('@', '@ ')}
            history = open('base.txt', 'w')
            json.dump(data, history, ensure_ascii=False)
            history.close()
        return
    regexp = re.compile(r"САМАР[АУ] ЗА ([0-9]+)")
    match = regexp.match(str(message.text).upper())
    if match != None:
        sum = int(match.group(1))
        if sum < 100:
            reply = 'Лентяи! Столько-то могли бы и прочитать'
        else:
            start = message.message_id - sum
            reply = 'Самара за %s:'%sum
            if not str(message.chat.id) in data.keys():
                data[str(message.chat.id)] = {"saved": {}}
            for i in sorted([int(key) for key in data[str(message.chat.id)]["saved"].keys()]):
                if i > start:
                    time = datetime.datetime.fromtimestamp(data[str(message.chat.id)]["saved"][str(i)]['date'])
                    time = pytz.timezone(LOCAL_TIMEZONE).localize(time).astimezone(pytz.timezone(CHAT_TIMEZONE))
                    reply += "\n" + time.strftime('%d.%m %H:%M:%S: ') + data[str(message.chat.id)]["saved"][str(i)]["text"]
        bot.send_message(message.chat.id, reply)

# Remove webhook, it fails sometimes the set if there is a previous webhook
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH, certificate=open(WEBHOOK_SSL_CERT, 'r'))
context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
context.load_cert_chain(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV)
web.run_app(app, host=WEBHOOK_LISTEN, port=WEBHOOK_PORT, ssl_context=context)
