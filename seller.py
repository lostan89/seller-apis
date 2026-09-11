import io
import logging.config
import os
import re
import zipfile
from environs import Env

import pandas as pd
import requests

logger = logging.getLogger(__file__)


def get_product_list(last_id, client_id, seller_token):
    """Получает список товаров магазина озон
     
    Args:
        last_id (str): идентификатор последнего значения на странице (ozon API)
        client_id (str): идентификатор клиента в сервисе ozon
        seller_token (str): ключ API
    
    Returns:
        dict: response_object.get('result') - Список товаров из json-ответа API.
    
    Exception:
        requests.exceptions.HTTPError: ошибка обращения к серверу
        ValueError: отсутствует (неверное) значение client_id / seller_token

    Example:
        result = get_product_list(last_id, client_id, seller_token)
        
    """
    url = "https://api-seller.ozon.ru/v2/product/list"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {
        "filter": {
            "visibility": "ALL",
        },
        "last_id": last_id,
        "limit": 1000,
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    response_object = response.json()
    return response_object.get("result")


def get_offer_ids(client_id, seller_token):

    """Получает артикулы товаров магазина озон
     
    Args:
        client_id (str): идентификатор клиента в сервисе ozon
        seller_token (str): ключ API
    
    Returns:
        list: offer_ids - Список идентификаторов товара (артикулы)
    
    Exception:
        requests.exceptions.HTTPError: ошибка обращения к серверу
        ValueError: отсутствует (неверное) значение client_id / seller_token

    Example:
        offer_ids = get_offer_ids(client_id, seller_token)
        
    """
    last_id = ""
    product_list = []
    while True:
        some_prod = get_product_list(last_id, client_id, seller_token)
        product_list.extend(some_prod.get("items"))
        total = some_prod.get("total")
        last_id = some_prod.get("last_id")
        if total == len(product_list):
            break
    offer_ids = []
    for product in product_list:
        offer_ids.append(product.get("offer_id"))
    return offer_ids


def update_price(prices: list, client_id, seller_token):
    
    """Обновляет цены товаров
     
    Args:
        prices (list): список с ценами товаров
        client_id (str): идентификатор клиента в сервисе ozon
        seller_token (str): ключ API
    
    Returns:
        response.json() - Ответ API о результате загрузки
    
    Exception:
        requests.exceptions.HTTPError: ошибка обращения к серверу
        ValueError: отсутствует (неверное) значение client_id / seller_token

    Example:
        update_price(prices: list, client_id, seller_token)
        >>> 200 OK
        
    """
    url = "https://api-seller.ozon.ru/v1/product/import/prices"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {"prices": prices}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def update_stocks(stocks: list, client_id, seller_token):
    """Обновляет остатки товаров на OZON
     
    Args:
        stocks (list): список с остатками товаров
        client_id (str): идентификатор клиента в сервисе ozon
        seller_token (str): ключ API
    
    Returns:
        response.json() - Ответ API о результате загрузки
    
    Exception:
        requests.exceptions.HTTPError: ошибка обращения к серверу
        ValueError: отсутствует (неверное) значение client_id / seller_token

    Example:
        update_stocks(stocks: list, client_id, seller_token)
        >>> 200 OK
    """
    url = "https://api-seller.ozon.ru/v1/product/import/stocks"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {"stocks": stocks}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def download_stock():
    """Скачивает остатки товара с сайта Casio в виде архива ostatki.zip
     
    Args:
              
    Returns:
        dict: watch_remnants - словарь содержащий список остатков часов
        
    Exception:
        requests.exceptions.HTTPError: ошибка обращения к серверу
        zipfile.BadZipFile: битый zip-архив
        FileExistsError: архив уже есть в папке
        FileNotFoundError: архив не содержит файла ostatki.xls
    
    Example:
        watch_remnants = download_stock()
    """
    casio_url = "https://timeworld.ru/upload/files/ostatki.zip"
    session = requests.Session()
    response = session.get(casio_url)
    response.raise_for_status()
    with response, zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        archive.extractall(".")
    # Создаем список остатков часов:
    excel_file = "ostatki.xls"
    watch_remnants = pd.read_excel(
        io=excel_file,
        na_values=None,
        keep_default_na=False,
        header=17,
    ).to_dict(orient="records")
    os.remove("./ostatki.xls")  # Удалить файл
    return watch_remnants


def create_stocks(watch_remnants, offer_ids):
    
    """Создает список товара (Артикул, Кол-во)
     
    Args:
        watch_remnants (dict): словарь, содержащий список остатков часов
        offer_ids (list) - Список идентификаторов товара (артикулы)
            
    Returns:
        list: stocks - Список с остатками товара
    
    Exception:
        requests.exceptions.HTTPError: ошибка обращения к серверу
        ValueError: отсутствует (неверное) значение client_id / seller_token

    Example:
        stocks = create_stocks(watch_remnants, offer_ids)
    """
    stocks = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            count = str(watch.get("Количество"))
            if count == ">10":
                stock = 100
            elif count == "1":
                stock = 0
            else:
                stock = int(watch.get("Количество"))
            stocks.append({"offer_id": str(watch.get("Код")), "stock": stock})
            offer_ids.remove(str(watch.get("Код")))
    for offer_id in offer_ids:
        stocks.append({"offer_id": offer_id, "stock": 0})
    return stocks


def create_prices(watch_remnants, offer_ids):
    """Создает список, содержащий Артикул и Стоимость товара.
     
    Args:
        watch_remnants (dict): словарь, содержащий список остатков часов
        offer_ids (list) - Список идентификаторов товара (артикулы)
            
    Returns:
        list: prices - Список с ценами на товар
    
    Exception:
        AttributeError:
            В функцию price_conversion должно быть передано строковое значение.

    Example:
        prices = create_prices(watch_remnants, offer_ids
    """
    prices = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            price = {
                "auto_action_enabled": "UNKNOWN",
                "currency_code": "RUB",
                "offer_id": str(watch.get("Код")),
                "old_price": "0",
                "price": price_conversion(watch.get("Цена")),
            }
            prices.append(price)
    return prices


def price_conversion(price: str) -> str:
    """Преобразовывает цену, убирая нечисловые символы.
    
    Args:
        price (str): переменная содержит цену на товар
    
    Returns:
        Строка из цифр.   
    
    Exception:
        AttributeError:
            В функцию должно быть передано строковое значение.

    Example:
        price_conversion(5'990.00 руб.) -> 5990
        price_conversion(abc) -> ''

    """
    return re.sub("[^0-9]", "", price.split(".")[0])


def divide(lst: list, n: int):
    """Разделить список lst на части по n элементов"""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


async def upload_prices(watch_remnants, client_id, seller_token):
    """Загружает цены на OZON.
    
    Args:
        watch_remnants (dict): словарь, содержащий список остатков часов
        client_id (str): идентификатор клиента в сервисе ozon
        seller_token (str): ключ API
    
    Returns:
        list: prices - Список с ценами на товар   
    
    Exception:
        requests.exceptions.HTTPError: ошибка обращения к серверу

    Example:
        prices = upload_prices(watch_remnants, client_id, seller_token)
    
    """
    offer_ids = get_offer_ids(client_id, seller_token)
    prices = create_prices(watch_remnants, offer_ids)
    for some_price in list(divide(prices, 1000)):
        update_price(some_price, client_id, seller_token)
    return prices


async def upload_stocks(watch_remnants, client_id, seller_token):
    """Формирует и загружает остатки товара на OZON.
    
    Args:
        watch_remnants (dict): словарь, содержащий список остатков часов
        client_id (str): идентификатор клиента в сервисе ozon
        seller_token (str): ключ API
    
    Returns:
        list: stocks - Список всех товаров на складе
        list: not_empty - Список товаров с ненулевым остатком   
    
    Exception:
        requests.exceptions.HTTPError: ошибка обращения к серверу

    Example:
        upload_stocks(watch_remnants, client_id, seller_token) --> not_empty, stocks
    """
    offer_ids = get_offer_ids(client_id, seller_token)
    stocks = create_stocks(watch_remnants, offer_ids)
    for some_stock in list(divide(stocks, 100)):
        update_stocks(some_stock, client_id, seller_token)
    not_empty = list(filter(lambda stock: (stock.get("stock") != 0), stocks))
    return not_empty, stocks


def main():
    env = Env()
    seller_token = env.str("SELLER_TOKEN")
    client_id = env.str("CLIENT_ID")
    try:
        offer_ids = get_offer_ids(client_id, seller_token)
        watch_remnants = download_stock()
        # Обновить остатки
        stocks = create_stocks(watch_remnants, offer_ids)
        for some_stock in list(divide(stocks, 100)):
            update_stocks(some_stock, client_id, seller_token)
        # Поменять цены
        prices = create_prices(watch_remnants, offer_ids)
        for some_price in list(divide(prices, 900)):
            update_price(some_price, client_id, seller_token)
    except requests.exceptions.ReadTimeout:
        print("Превышено время ожидания...")
    except requests.exceptions.ConnectionError as error:
        print(error, "Ошибка соединения")
    except Exception as error:
        print(error, "ERROR_2")


if __name__ == "__main__":
    main()
