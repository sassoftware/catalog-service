import logging

class LogRecord(logging.LogRecord):
    """
    Custom log record that can handle client addresses
    """
    def __init__(self, address, *args, **kwargs):
        logging.LogRecord.__init__(self, *args[:8], **kwargs)
        self.address = address

class Logger(logging.Logger):
    """
    Custom logger that can handle client addresses
    """
    def setAddress(self, address):
        self.address = address

    def makeRecord(self, *args, **kwargs):
        # Strip out the 'extra' argument of makeRecord (python 2.6)
        kwargs.pop('extra', None)
        args = args[:8]
        address = getattr(self, 'address', '')
        return LogRecord(address, *args, **kwargs)

class ExtendedTracebackFromatter(logging.Formatter):
    """
    Formatter displaying extended tracebacks
    """
    _fmt = "%(asctime)s %(pathname)s(%(lineno)s) %(levelname)s - %(message)s"

    def __init__(self):
        logging.Formatter.__init__(self, self.__class__._fmt)

    def formatException(self, ei):
        from conary.lib import util
        import StringIO
        excType, excValue, tb = ei
        sio = StringIO.StringIO()
        util.formatTrace(excType, excValue, tb, stream = sio,
            withLocals = False)
        util.formatTrace(excType, excValue, tb, stream = sio,
            withLocals = True)
        return sio.getvalue().rstrip()

class Formatter(ExtendedTracebackFromatter):
    """
    Custom formatter with client address support
    """
    _fmt = "%(address)s " + ExtendedTracebackFromatter._fmt

def getLogger(name, logFile, formatterClass = Formatter, loggerClass = Logger):
    if logFile is None:
        handler = logging.StreamHandler()
    else:
        handler = logging.FileHandler(logFile)

    formatter = formatterClass()
    handler.setFormatter(formatter)
    logger = loggerClass(name)
    logger.addHandler(handler)
    return logger

class LoggerCallback(object):
    logger = None

    def processRequest(self, request):
        request.logger = self.logger
        # This is a filter, it does not process the request
        return None
