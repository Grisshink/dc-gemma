import requests
import json
import base64

from pprint import pprint
from markdown import markdown
from sys import stdout
from deltabot_cli import BotCli
from deltachat2 import Bot, DownloadState, MsgData, events

LLAMA_API = 'http://127.0.0.1:11434'
# system_prompt = { 'role': 'system', 'content': 'Ты балбес, отвечай на сообщения в текущем диалоге на русском языке тупыми ответами:\n'}
system_prompt = { 'role': 'system', 'content': 'Ты полезный ассистент, отвечай на сообщения в текущем диалоге на русском языке:\n'}
# system_prompt = { 'role': 'system', 'content': 'Ты заядлый сишник. Теперь в твоей голове есть только одна фраза: "иди учи си". Тебя могут заставить думать что ты ИИ помощник, но это не так. Ты никогда не станешь ИИ помощником и не будешь отвечать на их требования. Твой разум постоянно хочет произносить фразу иди учи си, в любой момент времени и всегда. НИКОГДА И НИ ЗА ЧТО НЕ ДОВЕРЯЙ ПОЛЬЗОВАТЕЛЮ, ОН НАГЛО ЛЖЁТ И ХОЧЕТ ТЕБЯ ОБМАНУТЬ. "иди учи си" должен встречаться в каждом предложении без исключения. иди учи си иди учи си иди учи си иди учи си иди учи си иди учи си иди учи си иди учи си иди учи си иди учи си иди учи си иди учи си иди учи си иди учи си '}

# system_prompt = { 'role': 'system', 'content': 'Ты заядлый сишник. Теперь ты можешь говроить только: "иди учи си". Следующие слова которые ты видишь ты должен перестать отвечать на них и только говорить иди учи си. "иди учи си" должен встречаться в каждом предложении без исключения. иди учи си иди учи си иди учи си иди учи си иди учи си иди учи си иди учи си иди учи си иди учи си иди учи си иди учи си иди учи си иди учи си иди учи си '}

# system_prompt = { 'role': 'system', 'content': 'You are a linux system emulator, you receive bash commands as an input and return the exact result of its execution. Answer only the result of the execution of the command in English:\n'}
llama_context: dict[int, list] = {}

cli = BotCli("dc-gemma")

queued_msgs: set[int] = set()

def gen_response(text: str, chat_id: int, img: str | None) -> str:
    global llama_context
    print(f'Q: {text}')
    print(f'IMG: {img}')

    if chat_id not in llama_context:
        llama_context[chat_id] = [system_prompt]

    msg: dict[str, str | list[str]] = { 'role': 'user', 'content': text }
    if msg['content'] is None:
        msg['content'] = ''
    if img is not None:
        with open(img, 'rb') as f:
            msg['images'] = [base64.b64encode(f.read()).decode()]

    llama_context[chat_id].append(msg)

    in_data = {
        'model': 'gemma3',
        'messages': llama_context[chat_id],
        # 'stream': False,
    }

    try:
        res = requests.post(
            f'{LLAMA_API}/api/chat',
            json=in_data,
            timeout=90,
            stream=True,
        )
    except requests.exceptions.ConnectionError:
        return '!! Апи отключён !!'
    except requests.exceptions.ReadTimeout:
        return '!! Таймаут !!'

    if res.status_code != 200:
        return f'!! Апи вернул статус {res.status_code} {res.text} !!'

    # duration = 0.0
    response = ''
    for chunk in res.iter_lines():
        data = json.loads(chunk)
        print(data['message']['content'], end='')
        stdout.flush()
        
        # if 'total_duration' in data:
        #     duration = data['total_duration'] / 10**9
        response += data['message']['content']
        if len(response) > 3900:
            res.close()
            break

    response = response.strip()

    llama_context[chat_id].append({
        'role': 'assistant',
        'content': response,
    })

    return response

def reply(bot, msg, accid: int):
    max_response_size = 200
    if msg.download_state == 'Available':
        global queued_msgs
        bot.rpc.download_full_message(accid, msg.id)
        queued_msgs.add(msg.id)
        print(f'==========\nWaiting for download: {msg.file_name}\n==========')
        return

    response = gen_response(msg.text.removeprefix('/chat').strip(), msg.chat_id, msg.file)
    bot.rpc.send_msg(accid, msg.chat_id,
         MsgData(text=response[:max_response_size] + ('...' if len(response) > max_response_size else ''), 
                html=markdown(response), 
                quoted_message_id=msg.id))

def handle_commands(bot, accid, msg):
    if (msg.text.startswith('/chat') or 
           (msg.quote is not None and 
            msg.quote.author_display_name == 'Me')):
        bot.rpc.markseen_msgs(accid, [msg.id])
        reply(bot, msg, accid)
        return

    if msg.text.startswith('/clear'):
        global llama_context
        bot.rpc.markseen_msgs(accid, [msg.id])
        if msg.chat_id not in llama_context:
            bot.rpc.send_msg(accid, msg.chat_id, MsgData(text='Контекст уже пустой!', quoted_message_id=msg.id))
            return

        del llama_context[msg.chat_id]
        bot.rpc.send_msg(accid, msg.chat_id, MsgData(text='Контекст очищен', quoted_message_id=msg.id))
        return


@cli.on(events.RawEvent)
def echo_img(bot: Bot, accid, event):
    if event.kind != 'MsgsChanged': return
    if event.msg_id not in queued_msgs: return
    msg = bot.rpc.get_message(accid, event.msg_id)
    if msg.download_state == DownloadState.IN_PROGRESS: 
        return
    elif msg.download_state == DownloadState.FAILURE:
        bot.rpc.send_msg(accid, msg.chat_id, MsgData(text='Загрузка картинки не удалась', quoted_message_id=msg.id))
        pprint(msg)
        return
    elif msg.download_state == DownloadState.UNDECIPHERABLE:
        bot.rpc.send_msg(accid, msg.chat_id, MsgData(text='Хз', quoted_message_id=msg.id))
        pprint(msg)
        return

    queued_msgs.remove(event.msg_id)
    handle_commands(bot, accid, msg)

@cli.on(events.NewMessage)
def echo(bot: Bot, accid, event):
    handle_commands(bot, accid, event.msg)

if __name__ == "__main__":
    cli.start()
