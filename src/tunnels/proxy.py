import asyncore as _asyncore
import random as _random
import threading as _threading
import time as _time

from .confsys import Configurable as _Configurable

from .logger import mkInfoFunction as _mkInfoFunction
from .logger import mkWarnFunction as _mkWarnFunction
_proxyInfo = _mkInfoFunction('Proxy')
_proxyWarn = _mkWarnFunction('Proxy')

_definedProxyClasses = {}
class _ProxyMetaclass(type):
	def __new__(*args, **kwargs):
		builtClass = type.__new__(*args, **kwargs)
		if builtClass.__name__ in _definedProxyClasses:
			raise SystemError('Cannot define two message classes with the same name.')
		_definedProxyClasses[builtClass.__name__] = builtClass
		return builtClass

class ProxyThread(_threading.Thread):
	def __init__(self, parentProxy, rule, domain, port, incomingSocket):
		self._parentProxy = parentProxy
		self._rule = rule
		self._domain = domain
		self._port = port
		self._incomingSocket = incomingSocket
		self._alive = True
		self._destinations = self._rule.getForcedAddresses()
		_threading.Thread.__init__(self)
		self.daemon = True
	def getParentProxy(self):
		return self._parentProxy
	def getRule(self):
		return self._rule
	def getDomain(self):
		if self._destinations is not None:
			if len(self._destinations) == 1:
				return self._destinations[0]
			destination = _random.choice(self._destinations)
			_proxyInfo(self, 'to', self._domain, 'picked final address', destination, 'out of the', len(self._destinations), 'choices')
			return destination
		return self._domain
	def getPort(self):
		return self._port
	def getDestination(self):
		return self.getDomain(), self.getPort()
	def getIncomingSocket(self):
		return self._incomingSocket
	def isAlive(self):
		return self._alive
	def close(self): # Overriddable
		self._alive = False
		self._parentProxy.notifyProxyClosed(self)
	def run(self): # Overriddable
		pass

class ForwarderProxyThread(ProxyThread):
	def __init__(self, *args, **kwargs):
		ProxyThread.__init__(self, *args, **kwargs)
		self._incomingBuffer = b''
		self._outgoingBuffer = b''
		self._asyncSockets = {}
		self._asyncIncoming = _asyncore.dispatcher(self.getIncomingSocket(), self._asyncSockets)
		self._asyncIncoming.handle_read = self._incomingRead
		self._asyncIncoming.handle_write = self._incomingWrite
		self._asyncIncoming.writable = self._incomingWritable
		self._asyncIncoming.handle_close = self._handleClose
		self._asyncOutgoing = _asyncore.dispatcher(self._mkOutgoingSocket(), self._asyncSockets)
		self._asyncOutgoing.handle_read = self._outgoingRead
		self._asyncOutgoing.handle_write = self._outgoingWrite
		self._asyncOutgoing.writable = self._outgoingWritable
		self._asyncOutgoing.handle_close = self._handleClose
		self._readSize = self._getReadSize()
		self._buffered = self._isBuffered()
	def _incomingRead(self):
		read = self._asyncIncoming.recv(self._readSize)
		if read:
			self._incomingBuffer += read
			if not self._buffered:
				while self._incomingBuffer:
					self._outgoingWrite()
	def _incomingWrite(self):
		sent = self._asyncIncoming.send(self._outgoingBuffer)
		if sent:
			self._outgoingBuffer = self._outgoingBuffer[sent:]
	def _incomingWritable(self):
		return self._outgoingBuffer
	def _outgoingRead(self):
		read = self._asyncOutgoing.recv(self._readSize)
		if read:
			self._outgoingBuffer += read
			if not self._buffered:
				while self._outgoingBuffer:
					self._incomingWrite()
	def _outgoingWrite(self):
		sent = self._asyncOutgoing.send(self._incomingBuffer)
		if sent:
			self._incomingBuffer = self._incomingBuffer[sent:]
	def _outgoingWritable(self):
		return self._incomingBuffer
	def _handleClose(self):
		try:
			self._asyncIncoming.close()
		except:
			pass
		try:
			self._asyncOutgoing.close()
		except:
			pass
		self.close()
	def run(self):
		_asyncore.loop(map=self._asyncSockets)
	def _getReadSize(self): # Overriddable
		return 655365
	def _isBuffered(self): # Overriddable
		return True
	def _mkOutgoingSocket(self): # Overriddable
		raise NotImplementedError()

class Proxy(_Configurable):
	__metaclass__ = _ProxyMetaclass
	def __init__(self, name, providedConfig):
		_Configurable.__init__(self, self.__class__.__name__ + u'<' + name + '>', providedConfig, self.__class__._proxyConfig, self.__class__._proxyConfigRequired)
	def supportsTCP(self): # Overriddable
		return True
	def supportsUDP(self): # Overriddable
		return False
	def spawnTCP(self, rule, domain, tcpPort, incomingSocket):
		if not self.supportsTCP():
			raise SystemError(u'Cannot create a TCP connection; ' + str(self) + u' does not support TCP.')
		return self._doSpawnTCP(rule, domain, tcpPort, incomingSocket)
	def spawnUDP(self, rule, domain, udpPort, incomingSocket):
		if not self.supportsUDP():
			raise SystemError(u'Cannot create a UDP connection; ' + str(self) + u' does not support UDP.')
		return self._doSpawnUDP(rule, domain, tcpPort, incomingSocket)
	def _doSpawnTCP(self, rule, domain, tcpPort, incomingSocket): # Overriddable
		self._getTCPThreadClass()(self, rule, domain, tcpPort, incomingSocket).start()
		return True
	def _doSpawnUDP(self, rule, domain, udpPort, incomingSocket): # Overriddable
		self._getUDPThreadClass()(self, rule, domain, udpPort, incomingSocket).start()
		return True
	def _getTCPThreadClass(self): # Overriddable
		raise NotImplementedError()
	def _getUDPThreadClass(self): # Overriddable
		raise NotImplementedError()
	def onRegister(self): # Overriddable
		pass
	def notifyProxyClosed(self, proxyThread): # Overriddable
		pass

class MultiplexingProxy(Proxy):
	class Error(Exception):
		pass
	def __init__(self, *args, **kwargs):
		Proxy.__init__(self, *args, **kwargs)
		self._lock = _threading.RLock()
		self._socket = None
		self._activeCount = 0
	def onRegister(self):
		Proxy.onRegister(self)
		with self._lock:
			if self._getKeepalivePolicy(): # Connect right away
				self._socket = self._mkSocket()
				if self._socket is None:
					raise SystemError('Could not establish connection.')
	def _getKeepalivePolicy(self): # Overriddable
		raise NotImplementedError()
	def _mkSocket(self): # Overriddable
		raise NotImplementedError()
	def _disconnectSocket(self): # Overriddable
		self._socket.close()
	def _autoReconnectSleep(self): # Overriddable
		return 5
	def _mkSocketLoop(self):
		socket = None
		while socket is None:
			try:
				socket = self._mkSocket()
			except MultiplexingProxy.Error as e:
				_proxyWarn(e)
			if socket is None:
				_time.sleep(self._autoReconnectSleep())
		return socket
	def acquireSocket(self, countAsActive=True):
		with self._lock:
			if self._socket is None:
				self._activeCount = 0
				self._socket = self._mkSocketLoop()
			if countAsActive:
				self._activeCount += 1
			return self._socket
	def socketBroken(self):
		with self._lock:
			try:
				self._disconnectSocket()
			except:
				pass
			self._socket = None
			self._activeCount = 0
			if self._getKeepalivePolicy():
				_time.sleep(self._autoReconnectSleep())
				self._socket = self._mkSocketLoop()
	def notifyProxyClosed(self, proxyThread):
		Proxy.notifyProxyClosed(self, proxyThread)
		with self._lock:
			self._activeCount -= 1
			if self._activeCount < 1 and not self._getKeepalivePolicy():
				self._disconnectSocket()
				self._socket = None
				self._activeCount = 0
