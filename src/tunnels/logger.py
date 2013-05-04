import logging as _logging
import time as _time
import traceback as _traceback
import threading as _threading
try:
	import queue as _queue
except ImportError:
	import Queue as _queue

_logging.basicConfig()
_localLogger = _logging.getLogger(u'tunnels')
_localLogger.setLevel(_logging.INFO)
_silencedModules = []

class _logThread(_threading.Thread):
	def __init__(self):
		self._queue = _queue.Queue()
		_threading.Thread.__init__(self, name='Logging thread')
		self.daemon = True
	def run(self):
		try:
			while self.processOne():
				pass
		except BaseException: # Weird errors may occur when shutting down the system and the logger is destroyed
			pass
	def processOne(self):
		message = self._queue.get()
		if message is None:
			return False
		_localLogger.log(message[0], message[1])
		return True
	def kill(self):
		self.log(None)
	def log(self, item):
		self._queue.put(item)
	def empty(self):
		return self._queue.empty()

_loggingThread = None

def startLog(silencedModules=[]):
	global _silencedModules, _loggingThread
	if silencedModules is not None:
		_silencedModules = [x.lower() for x in silencedModules]
	_loggingThread = _logThread()
	_loggingThread.start()

def flushLog(thisThread=False):
	while _loggingThread is not None and not _loggingThread.empty():
		if thisThread:
			_loggingThread.processOne()
		else:
			_time.sleep(.05)

def stopLog():
	global _loggingThread
	flushLog()
	if _loggingThread is not None:
		_loggingThread.kill()
		_loggingThread = None

def _log(level, *msg, **kwargs):
	if _loggingThread is None:
		return
	newMsg = []
	if 'module' in kwargs:
		if kwargs['module'].lower() in _silencedModules:
			return
		newMsg.append(u'[' + kwargs['module'] + u']')
	for m in msg:
		if type(m) is type(u''):
			newMsg.append(m)
		elif isinstance(m, Exception):
			if 'printTraceback' not in kwargs or kwargs['printTraceback']:
				try:
					trace = _traceback.print_exc()
					newMsg.append(u'; Exception: ' + str(m) + u' - Traceback:\n' + trace)
				except:
					newMsg.append(u'; Exception: ' + str(m) + u' - Traceback unavailable.')
			else:
				newMsg.append(u'; Exception: ' + str(m) + u'.')
		else:
			newMsg.append(str(m))
	_loggingThread.log((level, u' '.join(newMsg)))

def info(*msg, **kwargs):
	return _log(_logging.INFO, *msg, **kwargs)

def warn(*msg, **kwargs):
	return _log(_logging.WARNING, *msg, **kwargs)

def error(*msg, **kwargs):
	return _log(_logging.ERROR, *msg, **kwargs)

def _mkLogFunction(baseFunction):
	def logCreationFunction(moduleName):
		moduleName = moduleName
		def infoFunction(*args, **kwargs):
			kwargs['module'] = moduleName
			return baseFunction(*args, **kwargs)
		return infoFunction
	return logCreationFunction

mkInfoFunction = _mkLogFunction(info)
mkWarnFunction = _mkLogFunction(warn)
mkErrorFunction = _mkLogFunction(error)
