"""Excepsion classes"""

class Error(Exception):
    """Base class for other exceptions"""
    pass

class InitError(Error):
    """Raised when init fails"""
    pass

class SumDoseError(Error):
    """Raised when sum dose fails"""
    pass