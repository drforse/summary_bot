import traceback
import time
import os
import logging


def cut_for_messages(message_text, limitation):
    try:
        n = 0
        parts_quantity = len(message_text) / limitation + 1 if len(message_text) % limitation == 0 else len(message_text) / limitation + 2
        parts_quantity = int(parts_quantity)
        for i in range(1, int(parts_quantity)):
            print(f'[{n}:{limitation * i}]')
            yield message_text[n:limitation * i]
            n += limitation
    except:
        print(traceback.format_exc())


def log_err(err, m=None, alert=None):
    chat = m.chat if 'chat' in m else {'id': None, 'username': None}
    logging.error(f'Error in {chat["id"]} ({chat["username"]}).\n{err}')
