"""Excepsion classes"""

class Error(Exception):
    """Base class for other exceptions"""
    pass

class Warning(Exception):
    """Base class for other exceptions"""
    pass

class InitError(Error):
    """Raised when init fails"""
    pass

class SumDoseError(Error):
    """Raised when sum dose fails"""
    pass

class NoCtsError(Error):
    """Raised when treatment has no cts """
    pass

class SqlInsertFail(Error):
    """Raised when sql insert dail """
    pass

class RoiAlreadyExists(Warning):
    """Raised when sql insert dail """
    pass