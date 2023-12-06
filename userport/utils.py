"""
Helper methods for the application.
"""


def get_domain_from_email(email: str):
    _, domain = email.split('@')
    return domain
