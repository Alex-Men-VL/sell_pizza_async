from textwrap import dedent
from typing import Union, Dict, Tuple

from more_itertools import chunked
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup, Update, LabeledPrice
)
from telegram.constants import ParseMode
from telegram.ext import CallbackContext
from telegram.helpers import escape_markdown

from moltin_api import (
    get_product_main_image_url,
    get_products
)


async def send_main_menu(context: CallbackContext.DEFAULT_TYPE,
                         chat_id: str, message_id: str, moltin_token: str,
                         page: int, quantity_per_page: int = 8) -> None:
    products = get_products(moltin_token)['data']
    products_per_page = list(chunked(products, quantity_per_page))

    reply_markup = get_products_menu(products_per_page, page)
    await context.bot.send_message(text='Пожалуйста, выберите товар:',
                                   chat_id=chat_id,
                                   reply_markup=reply_markup)
    await context.bot.delete_message(chat_id=chat_id,
                                     message_id=message_id)


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
        [
            InlineKeyboardButton(text='◀',
                                 callback_data=f'page_{previous_page_number}'),
            InlineKeyboardButton(text='Корзина', callback_data='cart'),
            InlineKeyboardButton(text='▶',
                                 callback_data=f'page_{next_page_number}')
        ]
    )
    return InlineKeyboardMarkup(keyboard)


async def send_cart_description(context: CallbackContext.DEFAULT_TYPE,
                                cart_description: dict,
                                chat_id: str, message_id: str,
                                with_keyboard: bool = True) -> None:
    cart_items = cart_description['cart_description']
    if not cart_items:
        message = 'К сожалению, ваша корзина пуста :c'
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text='Назад', callback_data='menu')]]
        )
    else:
        message = ''
        buttons = []
        for item in cart_items:
            name = escape_markdown(item['name'], version=2)
            description = escape_markdown(item['description'], version=2)
            value_price = escape_markdown(item['value_price'], version=2)

            message += f'''
            *{name}*
            _{description}_
            {item['quantity']} пицц в корзине на сумму {value_price}

            '''
            buttons.append([
                InlineKeyboardButton(
                    text=f'Убрать из корзины {item["name"]}',
                    callback_data=f'remove_{item["id"]}'
                )
            ])
        total_price = escape_markdown(cart_description["total_price"],
                                      version=2)
        message += f'*К оплате: {total_price}*'
        buttons.append(
            [InlineKeyboardButton(text='Оплатить', callback_data='pay')]
        )
        buttons.append(
            [InlineKeyboardButton(text='В меню', callback_data='menu')]
        )
        reply_markup = InlineKeyboardMarkup(buttons)

    reply_markup = reply_markup if with_keyboard else None
    await context.bot.send_message(chat_id=chat_id,
                                   text=dedent(message),
                                   reply_markup=reply_markup,
                                   parse_mode=ParseMode.MARKDOWN_V2)
    await context.bot.delete_message(chat_id=chat_id,
                                     message_id=message_id)


async def send_product_description(context: CallbackContext.DEFAULT_TYPE,
                                   product_description: dict,
                                   chat_id: str, message_id: str) -> None:
    message = f'''\
    {product_description['name']}

    Стоимость: {product_description['price']} руб.

    {product_description['description']}
    '''

    reply_markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                text='Положить в корзину',
                callback_data=f'add_{product_description["id"]}'
            )],

            [InlineKeyboardButton(text='В меню', callback_data='menu')]
        ]
    )

    if image_id := product_description['image_id']:
        await context.bot.send_chat_action(chat_id=chat_id,
                                           action='typing')

        moltin_token = context.bot_data['moltin_token']
        img_url = get_product_main_image_url(moltin_token, image_id)

        await context.bot.send_photo(chat_id=chat_id,
                                     photo=img_url,
                                     caption=dedent(message),
                                     reply_markup=reply_markup)
        await context.bot.delete_message(chat_id=chat_id,
                                         message_id=message_id)
    else:
        await context.bot.edit_message_text(text=dedent(message),
                                            chat_id=chat_id,
                                            message_id=message_id,
                                            reply_markup=reply_markup)


async def send_delivery_option(update: Update, restaurant: dict) -> None:
    distance = restaurant["distance_km"]
    if distance < 0.5:
        delivery = True
        message = f'''
        Может, заберете пиццу из нашей пиццерии неподалеку?
        Она всего в {'{:.0f}'.format(restaurant['distance_m'])} метрах от вас!
        Вот ее адрес: {restaurant['address']}.

        А можем и бесплатно доставить, нам не сложно c:'''
    elif distance < 5:
        delivery = True
        message = '''
        Похоже, придется ехать  к вам на самокате.
        Доставка будет стоить 100 руб.
        Доставляем или самовывоз?'''
    elif distance < 20:
        delivery = True
        message = '''
        Ближайшая пиццерия довольно далеко от вас.
        Доставка будет стоить 200 руб.
        Доставляем или самовывоз?'''
    else:
        delivery = False
        message = f'''
        Простите, но так далеко мы пиццу не доставим.
        Ближайшая пиццерия аж в {'{:.1f}'.format(distance)} километрах от вас!
        Будете заказывать самовывоз?'''

    buttons = [
        [InlineKeyboardButton(text='Самовывоз', callback_data='pickup')]
    ]

    if delivery:
        buttons.append(
            [InlineKeyboardButton(text='Доставка', callback_data='delivery')]
        )

    await update.message.reply_text(text=dedent(message),
                                    reply_markup=InlineKeyboardMarkup(buttons))


async def send_order_reminder(context: CallbackContext.DEFAULT_TYPE) -> None:
    message = '''
    *место для рекламы*
    *сообщение что делать если пицца не пришла*'''
    await context.bot.send_message(chat_id=context.job.context,
                                   text=dedent(message))


def generate_payment_payload(update: Update) -> str:
    query = update.callback_query.message
    first_name = query.chat.first_name
    last_name = query.chat.last_name
    message_id = query.message_id
    return f'{first_name}-{last_name}-{message_id}'


async def send_payment_invoice(context: CallbackContext.DEFAULT_TYPE,
                               chat_id: str, provider_token: str,
                               price: Union[str, int, float],
                               currency: str = 'RUB',
                               payload: str = 'Custom-Payload',
                               description: str = None) -> None:
    title = 'Оплата пиццы'
    description = description or 'Здесь должно быть описание заказа'
    prices = [LabeledPrice('Pizza', int(float(price)) * 100)]

    await context.bot.send_invoice(
        chat_id, title, description, payload, provider_token, currency, prices
    )


def parse_cart(cart: dict) -> dict:
    total_price = cart['meta']['display_price']['with_tax']['formatted']
    cart_description = []

    for cart_item in cart['data']:
        item_id = cart_item['id']
        item_name = cart_item['name']
        item_description = cart_item['description']
        item_quantity = cart_item['quantity']
        item_price = cart_item['meta']['display_price']['with_tax']
        item_unit_price = item_price['unit']['formatted']
        item_value_price = item_price['value']['formatted']

        cart_item_description = {
            'id': item_id,
            'name': item_name,
            'description': item_description,
            'quantity': item_quantity,
            'unit_price': item_unit_price,
            'value_price': item_value_price
        }
        cart_description.append(cart_item_description)
    return {
        'total_price': total_price,
        'cart_description': cart_description
    }


def clean_user_data(user_data: Dict, keys: Tuple[str, ...]) -> None:
    for key in keys:
        if key in user_data:
            del user_data[key]
