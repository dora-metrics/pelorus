class FailureProviderAuthenticationError(Exception):
    """
    Exception raised for authentication issues
    """

    auth_message = "Check the TOKEN: not authorized, invalid credentials"

    def __init__(self, message=auth_message):
        super().__init__(message)
