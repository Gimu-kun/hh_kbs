"""Lỗi nghiệp vụ của cơ sở tri thức."""


class KnowledgeError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status
