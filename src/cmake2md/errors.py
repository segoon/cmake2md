"""Exception types raised by cmake2md."""


class Cmake2mdError(Exception):
    """Base class for every error cmake2md reports to the user.

    Carries an optional human-readable location so the CLI can point at the
    offending file/symbol instead of dumping a traceback.
    """

    def __init__(self, message: str, location: str = '') -> None:
        self.message = message
        self.location = location
        super().__init__(f'{location}: {message}' if location else message)

    def at(self, location: str) -> 'Cmake2mdError':
        """Return this error with `location` attached, if it has none yet."""
        if self.location:
            return self
        return type(self)(self.message, location)


class ParseError(Cmake2mdError):
    """The comment markup of a symbol could not be understood."""


class UsageError(Cmake2mdError):
    """The command line or the template/output arguments are inconsistent."""
