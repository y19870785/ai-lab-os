"""UserTask domain and persistence exceptions."""


class UserTaskError(Exception):
    pass


class UserTaskNotFoundError(UserTaskError):
    pass


class UserTaskConflictError(UserTaskError):
    pass


class UserTaskPersistenceError(UserTaskError):
    pass
