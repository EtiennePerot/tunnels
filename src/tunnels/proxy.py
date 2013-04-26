import asyncore as _asyncore
import threading as _threading

from .confsys import Configurable as _Configurable

_definedProxyClasses = {}
class _ProxyMetaclass(type):
	def __new__(*args, **kwargs):
		builtClass = type.__new__(*args, **kwargs)
		if builtClass.__name__ in _definedProxyClasses:
			raise SystemError('Cannot define two message classes with the same name.')
		_definedProxyClasses[builtClass.__name__] = builtClass
		return builtClass

class ProxyThread(_threading.Thread):
	def __init__(self, parentProxy, domain, port, incomingSocket):
		self._parentProxy = parentProxy
		self._domain = domain
		self._port = port
		self._incomingSocket = incomingSocket
		self._alive = True
		_threading.Thread.__init__(self)
		self.daemon = True
	def getParentProxy(self):
		return self._parentProxy
	def getDomain(self):
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
	def _incomingRead(self):
		read = self._asyncIncoming.recv(self._readSize)
		if read:
			self._incomingBuffer += read
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
	def spawnTCP(self, domain, tcpPort, incomingSocket):
		if not self.supportsTCP():
			raise SystemError(u'Cannot create a TCP connection; ' + str(self) + u' does not support TCP.')
		return self._doSpawnTCP(domain, tcpPort, incomingSocket)
	def spawnUDP(self, domain, udpPort, incomingSocket):
		if not self.supportsUDP():
			raise SystemError(u'Cannot create a UDP connection; ' + str(self) + u' does not support UDP.')
		return self._doSpawnUDP(domain, tcpPort, incomingSocket)
	def _doSpawnTCP(self, domain, tcpPort, incomingSocket): # Overriddable
		self._getTCPThreadClass()(self, domain, tcpPort, incomingSocket).start()
		return True
	def _doSpawnUDP(self, domain, udpPort, incomingSocket): # Overriddable
		self._getUDPThreadClass()(self, domain, udpPort, incomingSocket).start()
		return True
	def _getTCPThreadClass(self): # Overriddable
		raise NotImplementedError()
	def _getUDPThreadClass(self): # Overriddable
		raise NotImplementedError()
