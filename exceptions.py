class BinanceAPIError(Exception):

    def __init__(self, status_code, data):
        self.status_code = status_code
        if data:
            self.code = data['code']
            self.msg = data['msg']
        else:
            self.code = None
            self.msg = None
        message = f"{status_code} [{self.code}] {self.msg}"
        if status_code == 429:
            raise StopBot("Limit exceeded - stop the bot.")
        super().__init__(message)


class BookTooSmall(Exception):
    pass

class StopBot(Exception):
    pass
