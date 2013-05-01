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
_logQueue = _queue.Queue()
_silencedModules = []

class _logThread(_threading.Thread):
	def __init__(self):
		_threading.Thread.__init__(self, name='Logging thread')
		self.daemon = True
	def run(self):
		try:
			while True:
				level, message = _logQueue.get()
				_localLogger.log(level, message)
		except BaseException: # Weird errors may occur when shutting down the system and the logger is destroyed
			pass

def startLog(silencedModules=[]):
	global _silencedModules
	_silencedModules = silencedModules
	_logThread().start()

def _log(level, *msg, **kwargs):
	newMsg = []
	if 'module' in kwargs:
		if kwargs['module'] in _silencedModules:
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
	_logQueue.put((level, u' '.join(newMsg)))

def deinit():
	while not _logQueue.empty():
		_time.sleep(.05)

def info(*msg, **kwargs):
	return _log(_logging.INFO, *msg, **kwargs)

def warn(*msg, **kwargs):
	return _log(_logging.WARNING, *msg, **kwargs)

def error(*msg, **kwargs):
	return _log(_logging.ERROR, *msg, **kwargs)

def _mkLogFunction(baseFunction):
	def logCreationFunction(moduleName):
		moduleName = moduleName.upper()
		def infoFunction(*args, **kwargs):
			kwargs['module'] = moduleName
			return baseFunction(*args, **kwargs)
		return infoFunction
	return logCreationFunction

mkInfoFunction = _mkLogFunction(info)
mkWarnFunction = _mkLogFunction(warn)
mkErrorFunction = _mkLogFunction(error)
