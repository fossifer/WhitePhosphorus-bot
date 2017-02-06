class Error(Exception):
    def __init__(self, arg):
        self.message = arg

    def __str__(self):
        return repr(self.message)
