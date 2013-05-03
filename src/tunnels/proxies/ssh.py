import os as _os
import socket as _socket
import threading as _threading
import time as _time
from tunnels.parseutils import addressParse as _addressParse
from tunnels.proxy import MultiplexingProxy as _MultiplexingProxy
from tunnels.proxy import ForwarderProxyThread as _ForwarderProxyThread
from tunnels.socksipy import socksocket as _socksocket
from tunnels.socksipy import PROXY_TYPE_SOCKS5 as _PROXY_TYPE_SOCKS5
import paramiko as _paramiko

from tunnels.logger import mkInfoFunction as _mkInfoFunction
_sshInfo = _mkInfoFunction('SSH-Proxy')

class SSHProxyThread(_ForwarderProxyThread):
	def _mkOutgoingSocket(self):
		transport = self.getParentProxy().acquireSocket()
		try:
			self._sshChannel = transport.open_channel('direct-tcpip', self.getDestination(), ('', 0))
			return self._sshChannel
		except BaseException as e:
			_sshInfo('Could not connect to', self.getDestination(), '(perhaps server doesn\'t allow TCP channels, or destination is unreachable, or SSH link has gone down)', e)
	def _isBuffered(self):
		return False
	def close(self):
		try:
			self._sshChannel.shutdown_read()
			self._sshChannel.shutdown_write()
		except:
			pass
		_ForwarderProxyThread.close(self)

class _SSHProxyMonitor(_threading.Thread):
	def __init__(self, proxy, transport):
		self._proxy = proxy
		_threading.Thread.__init__(self, name='SSH monitor thread for ' + str(proxy))
		self.daemon = True
		self._alive = True
		self._timeout = self._proxy['timeout']
		self._channel = transport.open_channel('session')
		self._channel.settimeout(self._timeout)
		self._channel.invoke_shell()
		self.start()
	def run(self):
		while self._alive:
			try:
				self._channel.send('echo hi\n')
				if not len(self._channel.recv(4096)):
					raise Exception()
				_time.sleep(self._timeout)
			except:
				_sshInfo('Monitor thread detected broken connection for', self._proxy, '- Will reconnect in a while.')
				self._proxy.socketBroken()
				self._alive = False
	def kill(self):
		self._alive = False

class SSHProxy(_MultiplexingProxy):
	def __init__(self, name, config):
		_MultiplexingProxy.__init__(self, name, config)
		self._proxyAddress = self['address']
		self._proxyPort = self['port']
		self._username = self['username']
		self._keepAlive = self['keepalive']
		self._serverFingerprintRSA = self['rsaFingerprint']
		self._serverFingerprintECDSA = self['ecdsaFingerprint']
		self._cipher = self['cipher']
		self._hmac = self['hmac']
		self._timeout = self['timeout']
		self._parentSocks5Proxy = self['parentSocks5Proxy']
		if self._parentSocks5Proxy is not None:
			self._parentSocks5Proxy = _addressParse(self._parentSocks5Proxy, defaultPort=1080)
		try:
			self._privateKey = _paramiko.ECDSAKey.from_private_key_file(self['privateKey'])
		except:
			try:
				self._privateKey = _paramiko.RSAKey.from_private_key_file(self['privateKey'])
			except:
				raise ValueError(u'Not a valid ECDSA or RSA private key file: "' + self['privateKey'] + u'"')
		self._monitorThread = None
	def _getKeepalivePolicy(self):
		return self._keepAlive
	def _mkSocket(self):
		if self._parentSocks5Proxy is not None:
			_sshInfo('Connecting to SSH server', (self._proxyAddress, self._proxyPort), 'over SOCKSv5 proxy', self['parentSocks5Proxy'])
			socket = _socksocket(_socket.AF_INET, _socket.SOCK_STREAM)
			socket.setproxy(_PROXY_TYPE_SOCKS5, self._parentSocks5Proxy['address'], self._parentSocks5Proxy['port'], username=self._parentSocks5Proxy['username'], password=self._parentSocks5Proxy['password'])
		else:
			_sshInfo('Connecting to SSH server', (self._proxyAddress, self._proxyPort))
			socket = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
		try:
			socket.connect((self._proxyAddress, self._proxyPort))
		except BaseException as e:
			if self._parentSocks5Proxy is not None:
				raise _MultiplexingProxy.Error('Could not connect to', (self._proxyAddress, self._proxyPort), 'over SOCKSv5 proxy', self['parentSocks5Proxy'], e)
			raise _MultiplexingProxy.Error('Could not connect to', (self._proxyAddress, self._proxyPort), e)
		transport = _paramiko.Transport(socket)
		transport.set_keepalive(self._timeout / 4)
		transport.get_security_options().ciphers = (self._cipher,)
		transport.get_security_options().digests = (self._hmac,)
		try:
			transport.start_client()
		except BaseException as e:
			raise _MultiplexingProxy.Error('Could not start an SSH client to', (self._proxyAddress, self._proxyPort), e)
		try:
			hostKey = transport.get_remote_server_key()
			if not self._publicKeyCompare(hostKey, self._serverFingerprintRSA) and not self._publicKeyCompare(hostKey, self._serverFingerprintECDSA):
				raise _MultiplexingProxy.Error('Host SSH fingerprint', self._prettyFingerprint(hostKey), 'did not match any of the fingerprints:', (self._serverFingerprintRSA, self._serverFingerprintECDSA))
			transport.auth_publickey(self._username, self._privateKey)
		except BaseException as e:
			raise _MultiplexingProxy.Error('Could not log in to the SSH server.', e)
		try:
			self._monitorThread = _SSHProxyMonitor(self, transport)
		except BaseException as e:
			raise _MultiplexingProxy.Error('Could not spawn a shell on the SSH server.', e)
		return transport
	def _disconnectSocket(self):
		_sshInfo('Disconnecting from SSH server', (self._proxyAddress, self._proxyPort))
		_MultiplexingProxy._disconnectSocket(self)
		if self._monitorThread is not None:
			self._monitorThread.kill()
	def _prettyFingerprint(self, fingerprint):
		if fingerprint is None:
			return u'None'
		if isinstance(fingerprint, _paramiko.PKey):
			fingerprint = fingerprint.get_fingerprint().encode('hex')
		fingerprint = fingerprint.lower().replace(':', '')
		return u':'.join(fingerprint[i:i + 2] for i in range(0, len(fingerprint), 2))
	def _publicKeyCompare(self, key1, key2):
		return self._prettyFingerprint(key1) == self._prettyFingerprint(key2)
	def _getTCPThreadClass(self):
		return SSHProxyThread

proxyInfo = {
	'class': SSHProxy,
	'config': {
		'address': {
			'description': u'The address of the SSH server.'
		},
		'port': {
			'default': 22,
			'description': u'Port number of the SSH server.'
		},
		'username': {
			'description': u'Username used to log in.'
		},
		'privateKey': {
			'description': u'Full path to the private key file used to log in. Supports ECDSA and RSA keys only. Do not use "~" in the path.'
		},
		'rsaFingerprint': {
			'default': None,
			'description': u'Fingerprint of the server\'s RSA key. If not provided and the server presents its RSA key, the connection will be closed.'
		},
		'ecdsaFingerprint': {
			'default': None,
			'description': u'Fingerprint of the server\'s ECDSA key. If not provided and the server presents its ECDSA key, the connection will be closed.'
		},
		'keepAlive': {
			'default': False,
			'description': u'If true, the SSH connection to the server will be kept all the time. Otherwise, the connection will only be made when necessary, and will be dropped after inactivity.'
		},
		'cipher': {
			'default': 'aes256-ctr',
			'description': u'The cipher to use for encryption.'
		},
		'hmac': {
			'default': 'hmac-sha1',
			'description': u'The HMAC scheme to use for authentication.'
		},
		'timeout': {
			'default': 30,
			'description': u'Timeout (in seconds) of control packets to check if the connection is still active.'
		},
		'parentSocks5Proxy': {
			'default': None,
			'description': u'If specified, should be a "[username:password@]serverName:portNumber" string pointing to a SOCKSv5 server. The SSH connection will be established through this SOCKSv5 server. Resolution of the SSH server name will be done on the remote end of this SOCKSv5 proxy.'
		}
	}
}
