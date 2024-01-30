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
    """Raised when sql insert fails """
    pass

class DataExtractionFailed(Error):
    """ When data extraction could not be performed"""

class RoiAlreadyExists(Warning):
    """ When you try to add a roi that already exists ro a treatment """
    pass

class AugmentedStructureMissing(Warning):
    """When augmented structure not in collection"""
    pass

class ParamaterExtractionFailed(Warning):
    """parameter extraction fails"""
    pass