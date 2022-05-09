from typing import Tuple, List, Union, Dict

import aiohttp
from geopy import distance


async def fetch_coordinates(
        address: str,
        yandex_api_key: str) -> Union[None, Tuple[str, str]]:
    url = 'https://geocode-maps.yandex.ru/1.x'
    params = {
        'geocode': address,
        'apikey': yandex_api_key,
        'format': 'json',
    }
    async with aiohttp.ClientSession(raise_for_status=True) as session:
        async with session.get(url, params=params) as response:
            places = await response.json()

    found_places = places['response'][
        'GeoObjectCollection'
    ]['featureMember']

    if not found_places:
        return

    most_relevant_place = found_places[0]
    lon, lat = most_relevant_place['GeoObject']['Point']['pos'].split(" ")
    return lon, lat


def get_nearest_restaurant(
        order_coordinates: Tuple[str, str],
        restaurants: List[Dict[str, str]]) -> Dict[str, str]:
    distances = []
    order_lon, order_lat = order_coordinates
    for restaurant in restaurants:
        order_distance = distance.distance(
            (order_lat, order_lon),
            (restaurant['Latitude'], restaurant['Longitude'])
        )
        distances.append(
            {
                'address': restaurant['Address'],
                'lon': restaurant['Longitude'],
                'lat': restaurant['Latitude'],
                'id': restaurant['id'],
                'distance_km': order_distance.kilometers,
                'distance_m': order_distance.meters,
                'courier_id': restaurant['Tg-id']
            }
        )
    nearest_restaurant = min(distances,
                             key=lambda rest: rest['distance_km'])
    return nearest_restaurant
