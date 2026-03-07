class PVMError(Exception):
    """Base exception for the pvm library."""

    pass


class NotValidProjectError(PVMError):
    """Raised when a directory does not contain a valid `.pvm/` project."""

    pass


class AlreadyInitializedError(PVMError):
    """Raised when initializing a project where `.pvm/` already exists."""

    pass


class PromptNotFoundError(PVMError):
    """Raised when a prompt id cannot be resolved."""

    pass


class VersionNotFoundError(PVMError):
    """Raised when a prompt version cannot be resolved."""

    pass


class InvalidPromptTemplateError(PVMError):
    """Raised when a prompt YAML template fails validation."""

    pass


class InvalidVersionError(PVMError):
    """Raised when a version string is not a valid semantic version."""

    pass
