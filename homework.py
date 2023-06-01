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
    """Проверяет доступность переменных окружения"""
    tokens = all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])
    if not tokens:
        logger.critical('Отсутствуют токены')
    return tokens



def send_message(bot, message):
    """Отправляет сообщение в Telegram чат"""
    try:
        logger.debug(f'bot отправляет сообщение {message}')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as error:
        logger.error(f'Не удалось отправить сообщение. Ошибка {error}')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса"""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except Exception as error:
        message = f'Ошибка при запросе к эндпоинту: {error}'
        logger.error(message)
        raise KeyError(message)
    if response.status_code != HTTPStatus.OK:
        error = f'API домашки возвращает код: {response.status_code}'
        logger.error(error)
        raise exception.HttpException(response)
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации из урока API сервиса Практикум Домашка"""
    if not response:
        error = 'Пустой словарь'
        logger.error(error)
        raise KeyError
    elif not isinstance(response, dict):
        error = 'response не является словарём'
        logger.error(error)
        raise TypeError
    elif 'homeworks' not in response:
        error = 'Нет ожидаемого ключа'
        logger.error(error)
        raise KeyError
    elif not isinstance(response.get('homeworks'), list):
        error = 'Тип данных ответа не является списком'
        logger.error(error)
        raise TypeError
    return response.get('homeworks')


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус этой работы"""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS.keys():
        error = 'Неопределённый статус работы'
        logger.error(error)
        raise KeyError(error)
    elif not homework_name:
        error = 'Нет имени дз'
        logger.error(error)
        raise KeyError(error)
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
                        send_info[homework] = message
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
    main()
