#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ssl
from aiohttp import web
import telebot
import json
import datetime
import pytz
import re
import os
import logging
from funcs import cut_for_messages

logging.basicConfig(level=logging.INFO)

API_TOKEN = ''  # put your token here

WEBHOOK_HOST = ''  # hostname
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
with open('base.json', 'r', encoding='utf-8') as history:
    data = json.load(history)


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
    bot.reply_to(message, 'Напишите всамару в начале сообщения или в ответ на сообщение чтобы сохранить\n'
                          'Напишите самара за 200 чтобы получить самару за 200')


@bot.message_handler(func=lambda m: m.text.lower().startswith('всамару'))
def add_to_samara(m):
    m.text = m.text.replace('>', '&gt;').replace('<', '&lt;')
    local_data = data.get(str(m.chat.id))
    if not data:
        local_data = {'saved': {},
                      'ids': []}
    if not m.reply_to_message:
        save_text = m.text.split(maxsplit=1)[1]
        source_id = m.message_id
    else:
        if m.reply_to_message.from_user.is_bot:
            bot.send_message(m.chat.id, 'Я собратьев-ботов в себя не добавляю, извращенцы!')
            return
        source_id = m.reply_to_message.message_id
        if m.reply_to_message.from_user.username:
            name = m.reply_to_message.from_user.username
        else:
            name = m.reply_to_message.from_user.first_name
        save_text = f'{name}: {m.reply_to_message.text}'
    if source_id in local_data.get('ids'):
        bot.send_message(m.chat.id, 'Это уже есть в самаре')
        return
    local_data['ids'].append(source_id)
    local_data['saved'][str(source_id)] = {'date': m.date,
                                           'text': save_text.replace('@', '@ ')}
    data[str(m.chat.id)] = local_data
    with open('base.json', 'w', encoding='utf-8') as history:
        json.dump(data, history)


@bot.message_handler(func=lambda m: re.compile(r'САМАР[АУ] ЗА ([0-9]+)').match(m.text.upper()))
def get_from_samara(m):
    local_data = data.get(str(m.chat.id))
    print(local_data)
    sum = int(m.text.split()[-1])
    message_parts = []
    if sum < 100:
        reply = 'Лентяи! Столько-то могли бы и прочитать'
    else:
        start = m.message_id - sum
        reply = 'Самара за %s:' % sum
        if not local_data:
            local_data = {'saved': {}}
        for i in sorted([int(key) for key in local_data['saved'].keys()]):
            if i <= start:
                continue
            time = datetime.datetime.fromtimestamp(local_data['saved'][str(i)]['date'])
            time = pytz.timezone(LOCAL_TIMEZONE).localize(time).astimezone(pytz.timezone(CHAT_TIMEZONE))
            link = f't.me/{m.chat.username}/{i}' if m.chat.username else f't.me/c/{m.chat.id}/{i}'.replace('-100', '')
            add_to_reply = f'\n<a href="{link}">{time.strftime("%d.%m %H:%M:%S: ")}</a>{local_data["saved"][str(i)]["text"]}'
            if len(reply+add_to_reply) > 4096:
                message_parts.append(reply)
                reply = ''
            reply += add_to_reply
            if len(reply) > 4096:
                parts = [i for i in cut_for_messages(reply, 4096)]
                message_parts += list(filter(lambda p: len(p) == 4096, parts))
                reply = parts[-1] if len(parts[-1]) < 4096 else ''
    message_parts.append(reply)
    n = 1
    for part in message_parts:
        try:
            if n != len(message_parts):
                bot.send_message(m.chat.id, part, parse_mode='html')
            else:
                bot.reply_to(m, part, parse_mode='html')
        except Exception as e:
            print(e)
            print(len(part))
        n += 1


@bot.message_handler(func=lambda m: m.text.lower().startswith('изподсамары'))
def delete_from_samara(m):
    m.text = m.text.replace('>', '&gt;').replace('<', '&lt;')
    local_data = data.get(str(m.chat.id))
    if not data:
        local_data = {'saved': {},
                      'ids': []}
    if not m.reply_to_message:
        remove_text = m.text.split(maxsplit=1)[1]
        all_chat_texts = []
        for i in local_data['ids']:
            msg = local_data['saved'].get(str(i))
            if msg:
                all_chat_texts.append(msg.get('text'))
        print(all_chat_texts)
        print(remove_text)
        if remove_text not in all_chat_texts:
            bot.send_message(m.chat.id, 'Этого и так нет в самаре!')
            return
        for i in local_data['saved']:
            if local_data['saved'][i]['text'] == remove_text:
                del local_data['saved'][i]
                del local_data['ids'][local_data['ids'].index(int(i))]
                break  # убрать чтобы удалялись все идентичные запросу, а не только один
    else:
        if m.reply_to_message.from_user.is_bot:
            bot.send_message(m.chat.id, 'Я собратьев-ботов из объятий не отпускаю, извращенцы!')
            return
        source_id = m.reply_to_message.message_id
        if source_id not in local_data.get('ids'):
            bot.send_message(m.chat.id, 'Этого и так нет в самаре!')
            return
        del local_data['ids'][local_data['ids'].index(source_id)]
        del local_data['saved'][str(source_id)]
    data[str(m.chat.id)] = local_data
    with open('base.json', 'w', encoding='utf-8') as history:
        json.dump(data, history)


# Remove webhook, it fails sometimes the set if there is a previous webhook
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH, certificate=open(WEBHOOK_SSL_CERT, 'r'))
context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
context.load_cert_chain(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV)
web.run_app(app, host=WEBHOOK_LISTEN, port=WEBHOOK_PORT, ssl_context=context)


# bot.polling(none_stop=True)
