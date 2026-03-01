# Гемморой

Сетап:
```
python -m venv env
source env/bin/activate
pip install -r requirements.txt

python main.py init dcaccount:https://tarpit.fun/new
```

Кастомизация:
```
python main.py config displayname "Гемморой 2.0"
python main.py config selfstatus "Онет"
python main.py config selfavatar "./avatar.png"

# Удалять сообщения с акка бота через час, чтобы не засорять его сообщениями
python main.py config delete_device_after 3600
```

Получить ссыль на бота:
```
python main.py link
```

Запуск (ollama должен работать на порту 11434, чтобы бот отвечал без ошибок):
```
python ./echobot.py serve
```
