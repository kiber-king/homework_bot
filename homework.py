import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import exception

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']
    flag = True
    for token_name in tokens:
        if not globals()[token_name]:
            logger.critical(f'Отсутствует токен{token_name}')
            flag = False
    return flag


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        logger.debug(f'bot отправляет сообщение {message}')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError as error:
        raise telegram.error.TelegramError(error)


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.RequestException as error:
        raise ConnectionError(f'При запросе к эндпоинту: {ENDPOINT}'
                              f'с хэдерами {HEADERS} и параметрами {payload}'
                              f'возникла ошибка: {error}.')
    if response.status_code != HTTPStatus.OK:
        raise exception.HttpException(response)
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not response:
        raise KeyError('Пустой словарь')
    elif not isinstance(response, dict):
        raise TypeError('response не является словарём')
    elif 'homeworks' not in response:
        raise KeyError('Нет ожидаемого ключа')
    elif not isinstance(response.get('homeworks'), list):
        raise TypeError('Тип данных ответа не является списком')
    return response.get('homeworks')


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS.keys():
        raise KeyError('Неопределённый статус работы')
    elif not homework_name:
        raise KeyError('Нет имени дз')
    verdict = HOMEWORK_VERDICTS[homework_status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    send_info = {
        'error': None,
        'homework': None,
    }
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if len(homeworks) > 0:
                for homework in homeworks:
                    message = parse_status(homework)
                    if send_info['homework'] != message:
                        send_message(bot, message)
                        send_info['homework'] = message
            else:
                logger.debug('Новые статусы дз отсутствуют')
            timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if send_info['error'] != message:
                logger.error(message)
                send_message(bot, message)
                send_info['error'] = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname) - %(name) - %(message)',
        stream=sys.stdout
    )
