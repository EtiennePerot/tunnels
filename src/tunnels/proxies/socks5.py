import asyncore as _asyncore
import socket as _socket
from tunnels.proxy import Proxy as _Proxy
from tunnels.proxy import ForwarderProxyThread as _ForwarderProxyThread
from tunnels.proxies.socksipy import socksocket as _socksocket
from tunnels.proxies.socksipy import PROXY_TYPE_SOCKS5 as _PROXY_TYPE_SOCKS5

class Socks5TCPProxyThread(_ForwarderProxyThread):
	def _mkOutgoingSocket(self):
		outgoingSocket = _socksocket(_socket.AF_INET, _socket.SOCK_STREAM)
		outgoingSocket.setproxy(_PROXY_TYPE_SOCKS5, self.getParentProxy().getProxyAddress(), self.getParentProxy().getProxyPort())
		outgoingSocket.connect(self.getDestination())
		return outgoingSocket

class Socks5Proxy(_Proxy):
	def __init__(self, name, config):
		_Proxy.__init__(self, name, config)
		self._proxyAddress = self['address']
		self._proxyPort = self['port']
		# TODO Socks auth
	def getProxyAddress(self):
		return self._proxyAddress
	def getProxyPort(self):
		return self._proxyPort
	def _getTCPThreadClass(self): # Overriddable
		return Socks5TCPProxyThread

proxyInfo = {
	'class': Socks5Proxy,
	'config': {
		'address': {
			'description': 'The address of the SOCKS server.'
		},
		'port': {
			'default': 1080,
			'description': 'Port number of the SOCKS server.'
		},
		'username': {
			'default': None,
			'description': 'Username to log in to the SOCKS server.'
		},
		'password': {
			'default': None,
			'description': 'Password to log in to the SOCKS server.'
		}
	}
}
