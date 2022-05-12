from textwrap import dedent
from typing import Union, Dict, Tuple, Any, List

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup, Update, LabeledPrice
)
from telegram.constants import ParseMode
from telegram.ext import CallbackContext
from telegram.helpers import escape_markdown

from moltin_api import (
    get_product_main_image_url, get_product_by_sku
)

DATA = ''


async def send_main_menu(context: CallbackContext.DEFAULT_TYPE,
                         chat_id: str, message_id: str, page: int) -> None:
    menu = context.bot_data['menu'].get(page)
    await context.bot.send_message(text='Пожалуйста, выберите товар:',
                                   chat_id=chat_id,
                                   reply_markup=menu)
    await context.bot.delete_message(chat_id=chat_id,
                                     message_id=message_id)


async def send_cart_description(context: CallbackContext.DEFAULT_TYPE,
                                cart_description: Dict[str, Any],
                                chat_id: str, message_id: str,
                                with_keyboard: bool = True) -> None:
    cart_items = cart_description['cart_description']
    if not cart_items:
        message = 'К сожалению, ваша корзина пуста :c'
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text='В меню', callback_data='menu')]]
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
                                   product_description: Dict[str, str],
                                   chat_id: str, message_id: str) -> None:
    if len(categories := product_description['categories']) > 1:
        categories = [category.replace("'", "") for category in categories]
        categories_description = f'*Категории:* {", ".join(categories)}'
    elif len(categories) == 0:
        categories_description = 'Товара нет ни в одной категории'
    else:
        category = categories[0].replace("'", "")
        categories_description = f'*Категория:* {category}'

    product_name = escape_markdown(product_description['name'], version=2)
    product_price = escape_markdown(product_description['price'], version=2)
    description = escape_markdown(product_description['description'],
                                  version=2)

    message = f'''\
    *{product_name}*

    *Стоимость:* {product_price} руб
    
    {categories_description}

    _{description}_
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
        img_url = await get_product_main_image_url(moltin_token, image_id)

        await context.bot.send_photo(chat_id=chat_id,
                                     photo=img_url,
                                     caption=dedent(message),
                                     reply_markup=reply_markup,
                                     parse_mode=ParseMode.MARKDOWN_V2)
        await context.bot.delete_message(chat_id=chat_id,
                                         message_id=message_id)
    else:
        await context.bot.edit_message_text(text=dedent(message),
                                            chat_id=chat_id,
                                            message_id=message_id,
                                            reply_markup=reply_markup,
                                            parse_mode=ParseMode.MARKDOWN_V2)


def get_promo_menu(products: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    parsed_products = {
        product['data'][0]['name']: product['data'][0]['id']
        for product in products
    }
    keyboard = []
    for product_name, product_id in parsed_products.items():
        keyboard.append(
            [InlineKeyboardButton(text=f'{product_name} 🍕',
                                  callback_data=f'product_{product_id}')]
        )
    keyboard.append(
        [
            InlineKeyboardButton(text='В меню', callback_data='promo'),
            InlineKeyboardButton(text='Корзина🛒', callback_data='cart')
        ]
    )
    return InlineKeyboardMarkup(keyboard)


async def send_promo_products(context: CallbackContext.DEFAULT_TYPE,
                              moltin_token: str,
                              chat_id: str, message_id: str,
                              promo: Dict[str, Any]) -> None:
    promo_description = promo['description']
    products_sku = promo['schema']['exclude']['targets']
    products = [await get_product_by_sku(moltin_token, product_sku) for
                product_sku in products_sku]
    menu = get_promo_menu(products)
    await context.bot.send_message(text=promo_description,
                                   chat_id=chat_id,
                                   reply_markup=menu)
    await context.bot.delete_message(chat_id=chat_id,
                                     message_id=message_id)


async def send_delivery_option(update: Update,
                               restaurant: Dict[str, Any]) -> None:
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


def parse_cart(cart: dict) -> Dict[str, Any]:
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


def clean_user_data(user_data: Dict[str, Any], keys: Tuple[str, ...]) -> None:
    for key in keys:
        if key in user_data:
            del user_data[key]
