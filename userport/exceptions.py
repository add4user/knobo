class APIException(Exception):
    """
    Class to convert API errors to JSON messages with appropriate formats.
    """

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__()
        self.status_code = status_code
        self.message = message

    def to_dict(self):
        return {'error_code': self.status_code, 'message': self.message}

    def get_status_code(self):
        return self.status_code
