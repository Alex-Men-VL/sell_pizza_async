# Асинхронный Telegram бот

Бот написан для тестирования новой версии библиотеки
[python-telegram-bot](https://python-telegram-bot.readthedocs.io/en/latest/index.html), которая стала поддерживать
асинхронный код.

Это переделанная версия бота для пиццерии. Код оригинального бота, в которой используется версия 13.11 библиотеки
`python-telegram-bot`, доступен по [ссылке](https://github.com/Alex-Men-VL/sell_pizza).

## Изменения

#### 1. Взаимодействия с API Moltin и с базой данных Redis реализованы с помощью асинхронных библиотек

Для этого используется библиотека `aiohttp` и `aioredis`.

#### 2. Реализован кастомный persistence

Реализован persistence через `Redis` для более эффективной работы бота.

#### 3. Реализован скрипт для автоматического кеширования меню пиццерии

Меню сохраняется в `Redis` в словарь `bot_data`, таким образом оно доступно в боте благодаря кастомному persistence.


## Как запустить

Скачайте код:
```shell
$ git clone https://github.com/Alex-Men-VL/sell_pizza.git
$ cd sell_pizza
```

Установите зависимости:
```shell
$ pip install -r requirements.txt
```
Запустите бота:
```shell
$ python3 tg_bot.py
```

## Переменные окружения

Часть данных берется из переменных окружения. Чтобы их определить, создайте файл `.env` в корне проекта и запишите 
туда данные в таком формате: `ПЕРЕМЕННАЯ=значение`

Доступно `6` обязательных переменных:

- `TG_BOT_TOKEN` - токен телеграм бота. Чтобы его получить, напишите в Telegram специальному боту: `BotFather`;
- `PAYMENT_PROVIDER_TOKEN` - токен провайдера платежей. [Как получить](https://yookassa.ru/docs/support/payments/onboarding/integration/cms-module/telegram) на примере `ЮKassa`.
- `YANDEX_API_KEY` - API ключ Яндекс-геокодера. [Как получить](https://developer.tech.yandex.ru/services/).
- `REDIS_URL` - URL базы данных Redis. Пример: `redis://[[username]:[password]]@localhost:6379/0`
- Настройки для [ElasticPath](https://euwest.cm.elasticpath.com/):
  - `CLIENT_ID` - id клиента;
  - `CLIENT_SECRET` - секретный ключ клиента;

Также доступно `6` необязательных настроек, меняющих ключи записей в Redis:

- `DB_MAIN_KEY` - главный ключ от Redis. Через него можно получить все данные бота в кодированном виде.
По умолчанию - `tg`;
- `DB_BOT_DATA_KEY` - ключ для хранения данных из словаря `context.bot_data`. По умолчанию - `_bot_data`;
- `DB_USER_DATA_KEY` - ключ для хранения данных из словаря `context.user_data`. По умолчанию - `_user_data`;
- `DB_CHAT_DATA_KEY` - ключ для хранения данных из словаря `context.chat_data`. По умолчанию - `_chat_data`;
- `DB_CALLBACK_DATA_KEY` - ключ для хранения данных `callback_data`. По умолчанию - `_callback_data`;
- `DB_CONVERSATIONS_KEY` - ключ для хранения данных `conversations`. По умолчанию - `_conversations`;
