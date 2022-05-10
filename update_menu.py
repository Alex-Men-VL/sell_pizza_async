import asyncio
import logging
import pickle
from collections import defaultdict
from typing import Dict, Any

import aioredis
import aioschedule
from environs import Env
from more_itertools import chunked
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from moltin_api import get_access_token, get_products

logger = logging.getLogger(__file__)


def get_products_menu(products: list, page: int) -> InlineKeyboardMarkup:
    parsed_products = {
        product['name']: product['id'] for product in products[page - 1]
    }
    keyboard = []
    for button_name, button_id in parsed_products.items():
        keyboard.append(
            [InlineKeyboardButton(text=button_name,
                                  callback_data=f'product_{button_id}')]
        )
    max_page_number = len(products)
    previous_page_number = page - 1
    next_page_number = page + 1
    if page == 1:
        previous_page_number = max_page_number
    elif page == max_page_number:
        next_page_number = 1

    keyboard.append(
        [InlineKeyboardButton(text='Акции🔥', callback_data='promo')]
    )
    keyboard.append(
        [
            InlineKeyboardButton(text='◀',
                                 callback_data=f'page_{previous_page_number}'),
            InlineKeyboardButton(text='Корзина🛒', callback_data='cart'),
            InlineKeyboardButton(text='▶',
                                 callback_data=f'page_{next_page_number}')
        ]
    )
    return InlineKeyboardMarkup(keyboard)


async def create_menu(moltin_token: str,
                      products_per_page: int) -> Dict[int, Any]:
    products = await get_products(moltin_token)
    products_per_page = list(chunked(products['data'], products_per_page))
    menu = {}
    for page in range(1, len(products_per_page) + 1):
        menu_per_page = get_products_menu(products_per_page, page)
        menu[page] = menu_per_page
    return menu


async def cache_menu(moltin_token: str, redis_url: str,
                     db_keys: Dict[str, str],
                     products_per_page: int = 8) -> None:
    redis_connection = aioredis.from_url(redis_url)
    menu = await create_menu(moltin_token, products_per_page)

    db_contents_bytes = await redis_connection.get(db_keys['main_key'])
    if db_contents_bytes:
        db_contents = pickle.loads(db_contents_bytes)
    else:
        db_contents = {
            db_keys['bot_data_key']: {},
            db_keys['callback_data_key']: ([], {}),
            db_keys['chat_data_key']: defaultdict(dict, {}),
            db_keys['conversations_key']: {},
            db_keys['user_data_key']: defaultdict(dict, {})
        }
    db_contents[db_keys['bot_data_key']].update({
        'menu': menu
    })
    db_contents_bytes = pickle.dumps(db_contents)
    menu_updated = await redis_connection.set(db_keys['main_key'],
                                              db_contents_bytes)
    if menu_updated:
        logger.info('Меню успешно обновлено')


async def job(moltin_token, redis_uri, db_main_key, bot_data_key):
    await cache_menu(moltin_token, redis_uri, db_main_key, bot_data_key)


async def main():
    env = Env()
    env.read_env()
    logging.basicConfig(level=logging.INFO)

    redis_uri = env.str('REDIS_URL')
    client_id = env.str('CLIENT_ID')
    client_secret = env.str('CLIENT_SECRET')

    db_keys = {
        'db_main_key': env.str('DB_MAIN_KEY', 'tg'),
        'bot_data_key': env.str('DB_BOT_DATA_KEY', '_bot_data'),
        'user_data_key': env.str('DB_USER_DATA_KEY', '_user_data'),
        'chat_data_key': env.str('_chat_data', '_chat_data'),
        'callback_data_key': env.str('DB_CALLBACK_DATA_KEY', '_callback_data'),
        'conversations_key': env.str('DB_CONVERSATIONS_KEY', '_conversations'),
    }

    moltin_access_token = await get_access_token(client_id, client_secret)
    moltin_token = moltin_access_token['access_token']

    prefix = 'redis://'
    if not redis_uri.startswith(prefix):
        redis_uri = f'{prefix}{redis_uri}'

    await cache_menu(moltin_token, redis_uri, db_keys)

    aioschedule.every(10).seconds.do(job, moltin_token, redis_uri, db_keys)

    while True:
        await aioschedule.run_pending()
        await asyncio.sleep(1)


if __name__ == '__main__':
    asyncio.run(main())
