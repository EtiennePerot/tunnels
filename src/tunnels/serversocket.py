import random as _random
import select as _select
import threading as _threading
from .iptables import addRedirect as _addRedirect
from .iptables import removeRedirect as _removeRedirect
from .mapper import registerSocketThread as _registerSocketThread
from .tunnels import config as _config
from .tunnels import getTCPProxies as _getTCPProxies
from .tunnels import getUDPProxies as _getUDPProxies
from .logger import *

import socket as _socket
try:
	_socket.IP_TRANSPARENT
except AttributeError:
	_socket.IP_TRANSPARENT = 19 # http://bugs.python.org/issue12809

class _SocketThread(_threading.Thread):
	def __init__(self, domain, bindAddress, tcpProxies={}, udpProxies={}, packetSize=65535, tcpListenQueue=16, timeout=60):
		self._bindAddress = bindAddress
		self._sockets = []
		self._tcpProxies = tcpProxies
		self._udpProxies = udpProxies
		self._tcpActualPorts = {}
		self._udpActualPorts = {}
		self._domain = domain
		self._timeout = timeout
		self._dead = False
		for tcpPort, tcpProxy in tcpProxies.items():
			socket = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
			socket.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
			socket.setsockopt(_socket.SOL_IP, _socket.IP_TRANSPARENT, 1)
			tempPort = -1
			while 8:
				tempPort = _random.randint(*_temporaryPortRange)
				if tempPort in self._tcpActualPorts:
					continue
				try:
					socket.bind(('', tempPort))
				except _socket.error:
					continue
				if not _addRedirect(bindAddress, 'tcp', tcpPort, tempPort):
					try:
						socket.close()
					except:
						pass
					del socket
					socket = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
					socket.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
					socket.setsockopt(_socket.SOL_IP, _socket.IP_TRANSPARENT, 1)
					continue
				break
			self._tcpActualPorts[tempPort] = tcpPort
			info('Bound TCP socket to', (bindAddress, tempPort), 'for', domain, 'port', tcpPort)
			socket.listen(tcpListenQueue)
			self._sockets.append(socket)
		_threading.Thread.__init__(self)
		self.daemon = True
		_registerSocketThread(domain, self)
		self.start()
	def run(self):
		readList = []
		writeList = []
		exceptionList = []
		while not self._dead:
			readList, writeList, exceptionList = _select.select(self._sockets, [], [], self._timeout)
			for socket in readList:
				# TODO Don't assume 'socket' is a TCP socket
				connection = socket.accept()[0]
				tcpPort = self._tcpActualPorts[connection.getsockname()[1]]
				proxy = self._tcpProxies[tcpPort]
				info('Spawning proxy', proxy, 'towards', self._domain, 'port', tcpPort, 'for peer', connection.getpeername())
				proxy.spawnTCP(self._domain, tcpPort, connection)
		for socket in self._sockets:
			try:
				socket.close()
			except:
				pass
		for tcpTempPort, tcpPort in self._tcpActualPorts.items():
			_removeRedirect(self._bindAddress, 'tcp', tcpPort, tcpTempPort)
		for udpTempPort, udpPort in self._udpActualPorts.items():
			_removeRedirect(self._bindAddress, 'udp', udpPort, udpTempPort)
	def kill(self):
		self._dead = True

def spawn(domain, bindAddress):
	tcpProxies = _getTCPProxies(domain)
	udpProxies = _getUDPProxies(domain)
	if tcpProxies is not None or udpProxies is not None:
		info('Spawning server on', bindAddress, 'for', domain)
		_SocketThread(domain, bindAddress, tcpProxies, udpProxies)

_temporaryPortRange = None

def init():
	global _temporaryPortRange
	_temporaryPortRange = tuple(map(int, _config('temporaryBindPortRange').split(u'-')))
