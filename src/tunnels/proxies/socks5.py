import socket as _socket
from tunnels.parseutils import addressParse as _addressParse
from tunnels.proxy import Proxy as _Proxy
from tunnels.proxy import ForwarderProxyThread as _ForwarderProxyThread
from tunnels.socksipy import socksocket as _socksocket
from tunnels.socksipy import PROXY_TYPE_SOCKS5 as _PROXY_TYPE_SOCKS5

class Socks5TCPProxyThread(_ForwarderProxyThread):
	def _mkOutgoingSocket(self):
		outgoingSocket = _socksocket(_socket.AF_INET, _socket.SOCK_STREAM)
		proxyAddress = self.getParentProxy().getProxyAddress()
		outgoingSocket.setproxy(_PROXY_TYPE_SOCKS5, proxyAddress['address'], proxyAddress['port'], username=proxyAddress['username'], password=proxyAddress['password'])
		outgoingSocket.connect(self.getDestination())
		return outgoingSocket

class Socks5Proxy(_Proxy):
	def __init__(self, name, config):
		_Proxy.__init__(self, name, config)
		self._proxyAddress = _addressParse(self['address'], defaultPort=1080)
	def getProxyAddress(self):
		return self._proxyAddress
	def _getTCPThreadClass(self):
		return Socks5TCPProxyThread

proxyInfo = {
	'class': Socks5Proxy,
	'config': {
		'address': {
			'description': u'The address of the SOCKS server, in "[username:password@]serverName:portNumber" form.'
		}
	}
}
