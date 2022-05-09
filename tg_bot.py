import logging
import re
from datetime import datetime
from textwrap import dedent
from typing import Union

import requests
from environs import Env
from telegram import (
    Update,
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand
)
from telegram.constants import ParseMode
from telegram.ext import (
    filters,
    Application,
    CallbackContext,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    PicklePersistence,
    PreCheckoutQueryHandler
)
from validate_email import validate_email

from moltin_api import (
    get_access_token,
    get_product,
    get_or_create_cart,
    add_cart_item,
    get_cart_items,
    remove_cart_item,
    create_customer,
    delete_cart,
    get_available_entries,
    create_flow_entry, get_customer_by_email
)
from redis_persistence import RedisPersistence
from tg_lib import (
    send_cart_description,
    send_product_description,
    send_main_menu, parse_cart,
    send_delivery_option,
    send_order_reminder,
    send_payment_invoice,
    generate_payment_payload, clean_user_data,
)
from coordinate_utils import fetch_coordinates, get_nearest_restaurant

logger = logging.getLogger(__file__)


async def handle_start(update: Update,
                       context: CallbackContext.DEFAULT_TYPE) -> str:
    await context.application.bot.delete_my_commands()
    await context.application.bot.set_my_commands(
        language_code='ru',
        commands=[BotCommand('menu', 'Перейти в меню')]
    )

    chat_id = context.user_data['chat_id']
    message_id = context.user_data['message_id']
    moltin_token = context.bot_data['moltin_token']
    await send_main_menu(context, chat_id, message_id, moltin_token, page=1)
    context.user_data['current_page'] = 1
    return 'HANDLE_MENU'


async def handle_menu_request(update: Update,
                              context: CallbackContext.DEFAULT_TYPE) -> str:
    chat_id = context.user_data['chat_id']
    message_id = context.user_data['message_id']
    moltin_token = context.bot_data['moltin_token']
    current_page = context.user_data.get('current_page', 1)

    await send_main_menu(context, chat_id, message_id, moltin_token,
                         page=current_page)
    context.user_data['current_page'] = current_page
    return 'HANDLE_MENU'


async def handle_menu(update: Update,
                      context: CallbackContext.DEFAULT_TYPE) -> str:
    chat_id = context.user_data['chat_id']
    message_id = context.user_data['message_id']
    user_reply = context.user_data['user_reply']
    moltin_token = context.bot_data['moltin_token']

    if user_reply == 'cart':
        user_cart = get_cart_items(moltin_token, chat_id)
        cart_description = parse_cart(user_cart)
        await send_cart_description(context, cart_description,
                                    chat_id, message_id)
        return 'HANDLE_CART'
    elif user_reply.startswith('page_'):
        page = int(user_reply.replace('page_', ''))
        context.user_data['current_page'] = page
        await send_main_menu(context, chat_id, message_id, moltin_token,
                             page=page)
    elif user_reply.startswith('product_'):
        product_id = user_reply.replace('product_', '')
        product = get_product(moltin_token, product_id)['data']
        product_main_image = product['relationships'].get('main_image')
        product_description = {
            'id': product['id'],
            'name': product['name'],
            'description': product['description'],
            'price': product['meta']['display_price']['with_tax']['formatted'],
            'image_id': product_main_image['data']['id'] if product_main_image
            else ''
        }

        await send_product_description(context, product_description,
                                       chat_id, message_id)
        return 'HANDLE_DESCRIPTION'

    return 'HANDLE_MENU'


async def handle_description(update: Update,
                             context: CallbackContext.DEFAULT_TYPE) -> str:
    chat_id = context.user_data['chat_id']
    message_id = context.user_data['message_id']
    moltin_token = context.bot_data['moltin_token']
    user_reply = context.user_data['user_reply']

    if user_reply == 'menu':
        current_page = context.user_data['current_page']
        await send_main_menu(context, chat_id, message_id, moltin_token,
                             page=current_page)
        return 'HANDLE_MENU'
    elif user_reply.startswith('add_'):
        product_id = user_reply.replace('add_', '')
        user_cart = get_or_create_cart(moltin_token, chat_id)
        try:
            add_cart_item(moltin_token, user_cart['data']['id'],
                          product_id, item_quantity=1)
        except requests.exceptions.HTTPError:
            await context.bot.answer_callback_query(
                callback_query_id=update.callback_query.id,
                text='Не удалось добавить товар в корзину'
            )
        else:
            await context.bot.answer_callback_query(
                callback_query_id=update.callback_query.id,
                text='Товар добавлен в корзину'
            )
    return 'HANDLE_DESCRIPTION'


async def handle_cart(update: Update,
                      context: CallbackContext.DEFAULT_TYPE) -> str:
    chat_id = context.user_data['chat_id']
    message_id = context.user_data['message_id']
    user_reply = context.user_data['user_reply']
    moltin_token = context.bot_data['moltin_token']

    if user_reply == 'menu':
        current_page = context.user_data['current_page']
        await send_main_menu(context, chat_id, message_id, moltin_token,
                             page=current_page)
        return 'HANDLE_MENU'
    elif user_reply == 'pay':
        customer = get_customer_by_email(moltin_token,
                                         context.user_data.get('email'))
        if customer['data']:
            message = 'Пришлите нам ваш адрес текстом или геолокацию.'
            await context.bot.send_message(text=message,
                                           chat_id=chat_id)
            await context.bot.delete_message(chat_id=chat_id,
                                             message_id=message_id)
            return 'HANDLE_LOCATION'

        message = 'Пожалуйста, напишите свою почту для связи с вами'
        await context.bot.send_message(text=message,
                                       chat_id=chat_id)
        await context.bot.delete_message(chat_id=chat_id,
                                         message_id=message_id)
        return 'WAITING_EMAIL'
    elif user_reply.startswith('remove_'):
        product_id = user_reply.replace('remove_', '')
        item_removed = remove_cart_item(moltin_token, chat_id, product_id)
        if item_removed:
            await context.bot.answer_callback_query(
                callback_query_id=update.callback_query.id,
                text='Товар удален из корзины'
            )
            user_cart = get_cart_items(moltin_token, chat_id)
            cart_description = parse_cart(user_cart)
            await send_cart_description(context, cart_description,
                                        chat_id, message_id)
        else:
            await context.bot.answer_callback_query(
                callback_query_id=update.callback_query.id,
                text='Товар не может быть удален из корзины'
            )
    return 'HANDLE_CART'


async def handle_email(update: Update,
                       context: CallbackContext.DEFAULT_TYPE) -> str:
    chat_id = context.user_data['chat_id']
    user_email = context.user_data['user_reply']
    moltin_token = context.bot_data['moltin_token']

    if not validate_email(user_email):
        message = 'Почта указана не верно. Отправьте почту еще раз.'
        await update.message.reply_text(text=message)
        return 'WAITING_EMAIL'

    context.user_data['email'] = user_email
    customer = get_customer_by_email(moltin_token, user_email)
    if not customer['data']:
        customer = create_customer(moltin_token, user_email)

    message = f'''
    Вы ввели эту почту: {user_email}

    Пришлите нам ваш адрес текстом или геолокацию.'''
    await update.message.reply_text(text=dedent(message))
    return 'HANDLE_LOCATION'


async def handle_location(update: Update,
                          context: CallbackContext.DEFAULT_TYPE) -> str:
    user_location = context.user_data['user_reply']
    moltin_token = context.bot_data['moltin_token']

    try:
        coordinates = user_location.longitude, user_location.latitude
    except AttributeError:
        yandex_api_key = context.bot_data['yandex_api_key']
        coordinates = fetch_coordinates(user_location, yandex_api_key)
    if not coordinates:
        await update.message.reply_text(
            text='Не могу распознать этот адрес, повторите попытку.'
        )
        return 'HANDLE_LOCATION'

    available_restaurants = get_available_entries(moltin_token,
                                                  flow_slug='Pizzeria')
    nearest_restaurant = get_nearest_restaurant(coordinates,
                                                available_restaurants)
    context.user_data.update(
        {
            'nearest_restaurant': nearest_restaurant,
            'delivery_coordinates': coordinates
        }
    )
    lon, lat = coordinates
    create_flow_entry(moltin_token, 'Customer-Address',
                      {'Lon': lon, 'Lat': lat})
    await send_delivery_option(update, nearest_restaurant)
    return 'HANDLE_DELIVERY'


async def handle_delivery(update: Update,
                          context: CallbackContext.DEFAULT_TYPE) -> str:
    chat_id = context.user_data['chat_id']
    message_id = context.user_data['message_id']
    user_reply = context.user_data['user_reply']
    moltin_token = context.bot_data['moltin_token']

    user_cart = get_cart_items(moltin_token, chat_id)
    cart_description = parse_cart(user_cart)
    context.user_data['cart_price'] = cart_description['total_price']
    nearest_restaurant = context.user_data['nearest_restaurant']

    if user_reply == 'pickup':
        message = '''
        Вы выбрали самовывоз.

        Ваш заказ:'''
        await context.bot.send_message(
            chat_id=chat_id,
            text=dedent(message)
        )
        await send_cart_description(context, cart_description, chat_id,
                                    message_id, with_keyboard=False)
        await context.bot.send_message(
            chat_id=chat_id,
            text='Адрес пиццерии:'
        )
        await context.bot.send_location(chat_id,
                                        latitude=nearest_restaurant['lat'],
                                        longitude=nearest_restaurant['lon'])
    elif user_reply == 'delivery':
        lon, lat = context.user_data['delivery_coordinates']
        courier_id = nearest_restaurant['courier_id']
        message = f'''
            Новый заказ!

            Из ресторана по адресу: {nearest_restaurant['address']}

            Содержимое заказа:'''
        await context.bot.send_message(chat_id=courier_id,
                                       text=dedent(message))
        await send_cart_description(context, cart_description,
                                    chat_id, message_id,
                                    with_keyboard=False)
        await context.bot.send_message(
            chat_id=courier_id,
            text='Адрес заказа:'
        )
        await context.bot.send_location(chat_id=courier_id,
                                        latitude=lat,
                                        longitude=lon)

        await context.bot.send_message(
            chat_id=chat_id,
            text='Спасибо за заказ! Ожидайте доставки'
        )
        context.job_queue.run_once(send_order_reminder, when=3600,
                                   context=chat_id)
    else:
        return 'HANDLE_DELIVERY'

    button = [
        [InlineKeyboardButton(text='Оплатить', callback_data='pay_now')]
    ]
    await context.bot.send_message(
        chat_id=chat_id,
        text='Для оплаты нажмите кнопку *Оплатить*',
        reply_markup=InlineKeyboardMarkup(button),
        parse_mode=ParseMode.MARKDOWN_V2
    )

    return 'HANDLE_PAYMENT'


async def handle_payment(
        update: Update,
        context: CallbackContext.DEFAULT_TYPE
) -> Union[str, None]:
    chat_id = context.user_data['chat_id']
    message_id = context.user_data['message_id']
    user_reply = context.user_data['user_reply']

    if user_reply != 'pay_now':
        return 'HANDLE_PAYMENT'

    provider_token = context.bot_data['provider_token']
    cart_price = context.user_data['cart_price']
    payload = generate_payment_payload(update)
    await send_payment_invoice(context, chat_id, provider_token, cart_price,
                               payload=payload)
    context.user_data['payload'] = payload
    await context.bot.delete_message(chat_id=chat_id,
                                     message_id=message_id)


async def precheckout_callback(update: Update,
                               context: CallbackContext.DEFAULT_TYPE) -> None:
    query = update.pre_checkout_query
    payload = context.user_data['payload']
    if query.invoice_payload != payload:
        await query.answer(ok=False, error_message="Что-то пошло не так...")
    else:
        await query.answer(ok=True)


async def successful_payment_callback(
        update: Update,
        context: CallbackContext.DEFAULT_TYPE
) -> None:
    chat_id = update.message.chat_id
    moltin_token = context.bot_data['moltin_token']

    await update.message.reply_text('Оплата прошла успешно')
    delete_cart(moltin_token, chat_id)

    unnecessary_data = ('nearest_restaurant', 'delivery_coordinates',
                        'cart_price', 'payload')
    clean_user_data(context.user_data, unnecessary_data)


async def handle_users_reply(update: Update,
                             context: CallbackContext.DEFAULT_TYPE) -> None:
    if message := update.message:
        user_reply = message.text if message.text else message.location
        chat_id = message.chat_id
        message_id = message.message_id
    elif query := update.callback_query:
        user_reply = query.data
        chat_id = query.message.chat_id
        message_id = query.message.message_id
    else:
        return

    context.user_data.update(
        {
            'user_reply': user_reply,
            'chat_id': chat_id,
            'message_id': message_id
        }
    )

    if (not (token_expiration := context.bot_data.get('token_expiration')) or
            token_expiration <= datetime.timestamp(datetime.now())):
        moltin_access_token = get_access_token(
            context.bot_data['client_id'],
            context.bot_data['client_secret']
        )
        context.bot_data.update(
            {
                'moltin_token': moltin_access_token['access_token'],
                'token_expiration': moltin_access_token['expires'],
            }
        )

    if user_reply == '/start':
        user_state = 'START'
    elif user_reply == '/menu':
        user_state = 'MENU'
    else:
        user_state = context.user_data['state']

    states_functions = {
        'START': handle_start,
        'MENU': handle_menu_request,
        'HANDLE_MENU': handle_menu,
        'HANDLE_DESCRIPTION': handle_description,
        'HANDLE_CART': handle_cart,
        'WAITING_EMAIL': handle_email,
        'HANDLE_LOCATION': handle_location,
        'HANDLE_DELIVERY': handle_delivery,
        'HANDLE_PAYMENT': handle_payment
    }
    state_handler = states_functions[user_state]

    try:
        next_state = await state_handler(update, context)
        context.user_data['state'] = next_state
    except Exception as err:
        logger.error(err)


def main() -> None:
    env = Env()
    env.read_env()

    logging.basicConfig(level=logging.INFO)

    bot_token = env.str('TG_BOT_TOKEN')

    client_id = env.str('CLIENT_ID')
    client_secret = env.str('CLIENT_SECRET')
    yandex_api_key = env.str('YANDEX_API_KEY')
    provider_token = env.str('PAYMENT_PROVIDER_TOKEN')

    redis_uri = env.str('REDIS_URL')

    initial_db_data = {
        'bot_data': {
            'client_id': client_id,
            'client_secret': client_secret,
            'yandex_api_key': yandex_api_key,
            'provider_token': provider_token
        }
    }
    persistence = RedisPersistence(url=redis_uri, redis_key='tg',
                                   initial_data=initial_db_data)
    application = Application.builder().token(bot_token).persistence(
        persistence
    ).build()

    logger.info('Бот запущен')  # TODO: Отправлять логи в спец бот.

    application.add_handler(
        CallbackQueryHandler(handle_users_reply)
    )
    application.add_handler(
        MessageHandler(filters.TEXT | filters.LOCATION, handle_users_reply)
    )
    application.add_handler(
        PreCheckoutQueryHandler(precheckout_callback)
    )
    application.add_handler(
        MessageHandler(filters.SUCCESSFUL_PAYMENT,
                       successful_payment_callback))

    try:
        application.run_polling()
    except Exception as err:
        logger.error(err)


if __name__ == '__main__':
    main()
