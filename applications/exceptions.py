"""Application Exceptions。"""
class ApplicationError(Exception): pass
class ApplicationNotFoundError(ApplicationError):
    def __init__(self, aid): super().__init__(f"Application '{aid}' not found")
class ApplicationInitError(ApplicationError):
    def __init__(self, name, reason): super().__init__(f"Failed to init '{name}': {reason}")
class ApplicationExecutionError(ApplicationError):
    def __init__(self, name, reason): super().__init__(f"Execution failed for '{name}': {reason}")
class ManifestValidationError(ApplicationError):
    def __init__(self, errors): super().__init__(f"Manifest errors: {errors}")
