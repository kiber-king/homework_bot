class HttpException(Exception):
    def __init__(self, response):
        message = (
            f'Код ответа API: {response.status_code}]'
        )
        super().__init__(message)


