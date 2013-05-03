import random as _random
import select as _select
import threading as _threading
from .iptables import addRedirect as _addRedirect
from .iptables import removeRedirect as _removeRedirect
from .mapper import hasSocketThread as _hasSocketThread
from .mapper import registerSocketThread as _registerSocketThread
from .parseutils import portRangeParse as _portRangeParse
from .tunnels import config as _config
from .tunnels import getTCPRules as _getTCPRules
from .tunnels import getUDPRules as _getUDPRules

from .logger import mkInfoFunction as _mkInfoFunction
_srvInfo = _mkInfoFunction('SRV')

import socket as _socket
try: # Monkeypatch _socket.IP_TRANSPARENT
	_socket.IP_TRANSPARENT
except AttributeError:
	_socket.IP_TRANSPARENT = 19 # http://bugs.python.org/issue12809

class _SocketThread(_threading.Thread):
	def __init__(self, domain, bindAddress, tcpRules={}, udpRules={}, packetSize=65535, tcpListenQueue=16, timeout=60):
		self._bindAddress = bindAddress
		self._sockets = []
		self._tcpRules = tcpRules
		self._udpRules = udpRules
		self._tcpActualPorts = {}
		self._udpActualPorts = {}
		self._domain = domain
		self._timeout = timeout
		self._dead = False
		for tcpPort in tcpRules:
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
			_srvInfo('Bound TCP socket to', (bindAddress, tempPort), 'for', domain, 'port', tcpPort)
			socket.listen(tcpListenQueue)
			self._sockets.append(socket)
		_threading.Thread.__init__(self, name='Tunnels socket management thread')
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
				rule = self._tcpRules[tcpPort]
				_srvInfo('Spawning proxy', rule.getProxy(), 'towards', self._domain, 'port', tcpPort, 'for peer', connection.getpeername())
				rule.getProxy().spawnTCP(rule, self._domain, tcpPort, connection)
		_srvInfo('Closing proxies for', self._domain, 'for TCP ports', self._tcpActualPorts.values(), 'and UDP ports', self._udpActualPorts.values(), '- Existing TCP connections will keep working.')
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
	if not _hasSocketThread(domain):
		tcpRules = _getTCPRules(domain)
		udpRules = _getUDPRules(domain)
		if tcpRules is not None or udpRules is not None:
			_srvInfo('Spawning server on', bindAddress, 'for', domain)
			_SocketThread(domain, bindAddress, tcpRules, udpRules)

_temporaryPortRange = None

def init():
	global _temporaryPortRange
	_temporaryPortRange = _portRangeParse(_config('temporaryBindPortRange'))
