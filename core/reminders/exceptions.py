"""Reminder domain errors."""


class ReminderError(Exception):
    """Base Reminder error."""


class ReminderNotFoundError(ReminderError):
    """Reminder does not exist."""


class ReminderConflictError(ReminderError):
    """Reminder state or revision conflicts with the requested operation."""


class ReminderPersistenceError(ReminderError):
    """Reminder state could not be stored or decoded."""


class ReminderUnavailableError(ReminderError):
    """Reminder scheduling dependency is unavailable."""
