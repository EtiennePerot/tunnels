import socket as _socket
from tunnels.proxy import Proxy as _Proxy
from tunnels.proxy import ForwarderProxyThread as _ForwarderProxyThread
from socks import socksocket as _socksocket
from socks import PROXY_TYPE_HTTP as _PROXY_TYPE_HTTP

class HTTPTCPProxyThread(_ForwarderProxyThread):
	def _mkOutgoingSocket(self):
		outgoingSocket = _socksocket(_socket.AF_INET, _socket.SOCK_STREAM)
		outgoingSocket.setproxy(_PROXY_TYPE_HTTP, self.getParentProxy().getProxyAddress(), self.getParentProxy().getProxyPort())
		outgoingSocket.connect(self.getDestination())
		return outgoingSocket

class HTTPProxy(_Proxy):
	def __init__(self, name, config):
		_Proxy.__init__(self, name, config)
		self._proxyAddress = self['address']
		self._proxyPort = self['port']
		# HTTP auth?
	def getProxyAddress(self):
		return self._proxyAddress
	def getProxyPort(self):
		return self._proxyPort
	def _getTCPThreadClass(self):
		return HTTPTCPProxyThread

proxyInfo = {
	'class': HTTPProxy,
	'config': {
		'address': {
			'description': u'The address of the HTTP proxy server.'
		},
		'port': {
			'default': 80,
			'description': u'Port number of the HTTP proxy server.'
		},
		'username': {
			'default': None,
			'description': u'Username used for HTTP auth.'
		},
		'password': {
			'default': None,
			'description': u'Password used for HTTP auth.'
		}
	}
}
