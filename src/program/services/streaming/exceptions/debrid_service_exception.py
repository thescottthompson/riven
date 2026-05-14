class DebridServiceException(Exception):
    """Base exception for debrid service errors."""

    def __init__(self, message: str, *, provider: str) -> None:
        super().__init__(f"{provider}: {message}")

        self.provider = provider


class DebridServiceHTTPException(DebridServiceException):
    """Raised when there is a network error with the debrid service."""

    pass


class DebridServiceRefusedRangeRequestException(DebridServiceHTTPException):
    """Raised when the debrid service refuses a range request."""

    def __init__(self, provider: str) -> None:
        super().__init__("Refused range request", provider=provider)


class DebridServiceRangeNotSatisfiableException(DebridServiceHTTPException):
    """Raised when the debrid service reports that the requested range is not satisfiable."""

    def __init__(self, provider: str) -> None:
        super().__init__("Requested range not satisfiable", provider=provider)


class DebridServiceForbiddenException(DebridServiceHTTPException):
    """Raised when access to the debrid service is forbidden."""

    def __init__(self, provider: str) -> None:
        super().__init__("Access is forbidden", provider=provider)


class DebridServiceRateLimitedException(DebridServiceHTTPException):
    """Raised when the debrid service rate limits requests."""

    def __init__(self, provider: str) -> None:
        super().__init__("Rate limit exceeded", provider=provider)


class DebridServiceUnableToConnectException(DebridServiceException):
    """Raised when unable to establish a connection to the debrid service."""

    def __init__(self, provider: str) -> None:
        super().__init__("Unable to connect", provider=provider)


class DebridServiceServiceUnavailableException(DebridServiceException):
    """Raised when the debrid service reports that the service is unavailable."""

    def __init__(self, provider: str) -> None:
        super().__init__("Service is unavailable", provider=provider)


class DebridServiceLinkUnavailable(DebridServiceException):
    """Raised when a link is unavailable on the debrid service.

    `infringing=True` indicates the debrid service rejected the link as
    DMCA-takedown'd (e.g. Real-Debrid error_code 35 / "infringing_file").
    The caller can use this to record the underlying infohash on the
    global infringing blacklist instead of just retrying.
    """

    def __init__(
        self,
        provider: str,
        link: str,
        infringing: bool = False,
        error_code: int | None = None,
    ) -> None:
        super().__init__(f"Link {link} is unavailable or invalid", provider=provider)

        self.link = link
        self.infringing = infringing
        self.error_code = error_code


class DebridServiceClosedConnectionException(DebridServiceException):
    """Raised when the debrid service closes the connection prematurely."""

    def __init__(self, provider: str) -> None:
        super().__init__("Connection closed prematurely", provider=provider)
