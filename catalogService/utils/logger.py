#
# Copyright (c) SAS Institute Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


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
