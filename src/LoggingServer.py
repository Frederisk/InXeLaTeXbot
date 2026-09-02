import logging
from logging import Formatter
from logging.handlers import TimedRotatingFileHandler
from multiprocessing import Queue
from threading import Thread
from pathlib import Path


class LoggingServer():
    logFile = Path('log/inlatexbot.log')
    logFile.parent.mkdir(parents=True, exist_ok=True)
    logFile.touch(exist_ok=True)
    loggingHandler = TimedRotatingFileHandler(
        logFile, when="midnight", backupCount=100)
    loggingFormat = '%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s'
    loggingFormatter = Formatter(fmt=loggingFormat, datefmt='%I:%M:%S')
    loggingHandler.setFormatter(loggingFormatter)
    logger = logging.getLogger('inlatexbot')
    logger.setLevel("DEBUG")
    logger.addHandler(loggingHandler)

    INSTANCE = None

    def getInstance():
        if LoggingServer.INSTANCE is None:
            LoggingServer.INSTANCE = LoggingServer()
            return LoggingServer.INSTANCE
        else:
            return LoggingServer.INSTANCE

    def __init__(self):
        self._messageQueue = Queue()
        t = Thread(target=self.run)
        t.setDaemon(True)
        t.start()

    def debug(self, *args):
        self._messageQueue.put(("debug", args))

    def warn(self, *args):
        self._messageQueue.put(("warn", args))

    def run(self):
        while True:
            msg = self._messageQueue.get()
            if msg[0] == "debug":
                self.logger.debug(*msg[1])
            elif msg[0] == "warn":
                self.logger.warning(*msg[1])
