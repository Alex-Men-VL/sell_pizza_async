from typing import Dict, Union, List, Any

import aiohttp
from slugify import slugify


async def get_access_token(client_id: str,
                           client_secret: str) -> Dict[str, str]:
    url = 'https://api.moltin.com/oauth/access_token'
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }
    async with aiohttp.ClientSession(raise_for_status=True) as session:
        async with session.post(url, data=payload) as response:
            return await response.json()


async def get_products(access_token: str) -> Dict[str, str]:
    url = 'https://api.moltin.com/v2/products'
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.get(url) as response:
            return await response.json()


async def get_product(access_token: str,
                      product_id: Union[str, int]) -> Dict[str, Any]:
    url = f'https://api.moltin.com/v2/products/{product_id}'
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.get(url) as response:
            return await response.json()


async def get_product_by_sku(access_token: str,
                             product_sku: str) -> Dict[str, Any]:
    url = 'https://api.moltin.com/v2/products'
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    payload = {
        'filter': f'eq(sku, {product_sku})'
    }
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.get(url, params=payload) as response:
            return await response.json()


async def get_product_main_image_url(access_token: str,
                                     image_id: Union[str, int]) -> str:
    url = f'https://api.moltin.com/v2/files/{image_id}'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.get(url) as response:
            main_image = await response.json()
    return main_image['data']['link']['href']


async def create_product(access_token: str, product_id: Union[str, int],
                         name: str, description: str,
                         price: Union[str, int, float],
                         slug: str = None) -> Dict[str, str]:
    url = 'https://api.moltin.com/v2/products'
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    product_description = {
        'data': {
            'type': 'product',
            'name': name,
            'slug': slug if slug else slugify(name),
            'sku': f'sku-{product_id}',
            'description': description,
            'manage_stock': False,
            'price': [
                {
                    'amount': int(price) * 100,
                    'currency': 'RUB',
                    'includes_tax': True,
                },
            ],
            'status': 'live',
            'commodity_type': 'physical',
        },
    }
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.post(url, json=product_description) as response:
            return await response.json()


async def add_product_main_image(access_token: str,
                                 product_id: Union[str, int],
                                 image_id: Union[str, int]) -> Dict[str, str]:
    url = f'https://api.moltin.com/v2/products/{product_id}/relationships/main-image'
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    image_description = {
        'data': {
            'type': 'main_image',
            'id': image_id,
        },
    }
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.post(url, json=image_description) as response:
            return await response.json()


async def delete_product(access_token: str, product_id: str) -> bool:
    url = f'https://api.moltin.com/v2/products/{product_id}'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.delete(url) as response:
            return response.ok


async def get_or_create_cart(access_token: str, cart_id: Union[str, int],
                             currency: str = 'RUB') -> Dict[str, Any]:
    url = f'https://api.moltin.com/v2/carts/{cart_id}'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'X-MOLTIN-CURRENCY': currency
    }
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.get(url) as response:
            return await response.json()


async def get_cart_items(access_token: str,
                         cart_id: Union[str, int]) -> Dict[str, str]:
    url = f'https://api.moltin.com/v2/carts/{cart_id}/items'
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.get(url) as response:
            return await response.json()


async def add_cart_item(access_token: str, cart_id: Union[str, int],
                        item_id: Union[str, int],
                        item_quantity: Union[str, int],
                        currency: str = 'RUB') -> Dict[str, str]:
    url = f'https://api.moltin.com/v2/carts/{cart_id}/items'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'X-MOLTIN-CURRENCY': currency
    }

    cart_item = {
        'data': {
            'id': item_id,
            'type': 'cart_item',
            'quantity': item_quantity,
        },
    }
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.post(url, json=cart_item) as response:
            return await response.json()


async def remove_cart_item(access_token: str, cart_id: Union[str, int],
                           item_id: Union[str, int]) -> bool:
    url = f'https://api.moltin.com/v2/carts/{cart_id}/items/{item_id}'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.delete(url) as response:
            return response.ok


async def delete_cart(access_token: str, cart_id: Union[str, int]) -> bool:
    url = f'https://api.moltin.com/v2/carts/{cart_id}'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.delete(url) as response:
            return response.ok


async def get_customer_by_email(access_token: str,
                                email: str) -> Dict[str, str]:
    url = f'https://api.moltin.com/v2/customers'
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    payload = {
        'filter': f'eq(email, {email})'
    }
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.get(url, params=payload) as response:
            return await response.json()


async def create_customer(access_token: str, email: str,
                          name: str = None) -> Dict[str, str]:
    url = 'https://api.moltin.com/v2/customers'
    headers = {
        'Authorization': f'Bearer {access_token}',
    }

    customer = {
        'data': {
            'type': 'customer',
            'name': name if name else email.split('@')[0],
            'email': email,
        },
    }
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.post(url, json=customer) as response:
            return await response.json()


async def get_or_create_customer_by_email(access_token: str, email: str,
                                          name: str = None) -> Dict[str, str]:
    customer = await get_customer_by_email(access_token, email)
    if not customer['data']:
        customer = await create_customer(access_token, email, name)
    return customer


async def create_file(access_token: str, file_url: str) -> Dict[str, str]:
    url = 'https://api.moltin.com/v2/files'
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    files = {
        'file_location': (None, file_url),
    }
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.post(url, json=files) as response:
            return await response.json()


async def create_flow(access_token: str, name: str, description: str,
                      slug: str = None,
                      enabled: bool = True) -> Dict[str, str]:
    url = 'https://api.moltin.com/v2/flows'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    flow_description = {
        'data': {
            'type': 'flow',
            'name': name,
            'slug': slug if slug else slugify(name),
            'description': description,
            'enabled': enabled,
        },
    }
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.post(url, json=flow_description) as response:
            return await response.json()


async def create_flow_field(
        access_token: str, flow_id: Union[str, int], name: str,
        field_type: str, description: str, slug: str = None,
        required: bool = True, enabled: bool = True,
        default: Union[str, int] = None) -> Dict[str, str]:
    url = 'https://api.moltin.com/v2/fields'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    field_description = {
        'data': {
            'type': 'field',
            'name': name,
            'slug': slug if slug else slugify(name),
            'field_type': field_type,
            'description': description,
            'required': required,
            'enabled': enabled,
            'relationships': {
                'flow': {
                    'data': {
                        'type': 'flow',
                        'id': flow_id,
                    },
                },
            },
        },
    }
    if default:
        field_description['data'].update({'default': default})
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.post(url, json=field_description) as response:
            return await response.json()


async def create_flow_entry(
        access_token: str, flow_slug: str,
        fields_slug_per_value: Dict[str, str]) -> Dict[str, str]:
    url = f'https://api.moltin.com/v2/flows/{flow_slug}/entries'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    entry_description = {
        'data': {
            'type': 'entry',
            **fields_slug_per_value
        }
    }
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.post(url, json=entry_description) as response:
            return await response.json()


async def get_entries(access_token: str, flow_slug: str,
                      next_page_url: str = None) -> Dict[str, Any]:
    url = next_page_url or f'https://api.moltin.com/v2/flows/{flow_slug}/entries'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    payload = {
        'page[limit]': 100,
    }
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.get(url, params=payload) as response:
            return await response.json()


async def get_available_entries(access_token: str,
                                flow_slug: str) -> List[Dict[str, Any]]:
    available_entries = []
    entries = await get_entries(access_token, flow_slug=flow_slug)
    available_entries += entries['data']
    while next_page_url := entries['links']['next']:
        entries = await get_entries(access_token, flow_slug=flow_slug,
                                    next_page_url=next_page_url)
        available_entries += entries['data']
    return available_entries


async def get_categories(access_token: str) -> Dict[str, Any]:
    url = 'https://api.moltin.com/v2/categories'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.get(url) as response:
            return await response.json()


async def get_category(access_token: str,
                       category_id: Union[str, int]) -> Dict[str, Any]:
    url = f'https://api.moltin.com/v2/categories/{category_id}'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.get(url) as response:
            return await response.json()


async def get_promotions(access_token: str) -> Dict[str, Any]:
    url = 'https://api.moltin.com/v2/promotions'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    async with aiohttp.ClientSession(raise_for_status=True,
                                     headers=headers) as session:
        async with session.get(url) as response:
            return await response.json()
