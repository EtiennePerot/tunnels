import os as _os
import socket as _socket
from tunnels.logger import info as _info
from tunnels.proxy import MultiplexingProxy as _MultiplexingProxy
from tunnels.proxy import ForwarderProxyThread as _ForwarderProxyThread
import paramiko as _paramiko

class SSHProxyThread(_ForwarderProxyThread):
	def _mkOutgoingSocket(self):
		transport = self.getParentProxy().acquireSocket()
		try:
			self._sshChannel = transport.open_channel('direct-tcpip', self.getDestination(), ('', 0))
			return self._sshChannel
		except BaseException as e:
			_info('Could not connect to', self.getDestination(), '(perhaps server doesn\'t allow TCP channels, or destination is unreachable)', e)
	def _isBuffered(self):
		return False
	def close(self):
		try:
			self._sshChannel.shutdown_read()
			self._sshChannel.shutdown_write()
		except:
			pass
		_ForwarderProxyThread.close(self)

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
		try:
			self._privateKey = _paramiko.ECDSAKey.from_private_key_file(self['privateKey'])
		except:
			try:
				self._privateKey = _paramiko.RSAKey.from_private_key_file(self['privateKey'])
			except:
				raise ValueError(u'Not a valid ECDSA or RSA private key file: "' + self['privateKey'] + u'"')
	def _getKeepalivePolicy(self):
		return self._keepAlive
	def _mkSocket(self):
		_info('Connecting to SSH server', (self._proxyAddress, self._proxyPort))
		socket = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
		try:
			socket.connect((self._proxyAddress, self._proxyPort))
		except BaseException as e:
			raise _MultiplexingProxy.Error('Could not connect to', (self._proxyAddress, self._proxyPort), e)
		transport = _paramiko.Transport(socket)
		transport.set_keepalive(True)
		transport.get_security_options().ciphers = (self._cipher,)
		transport.get_security_options().digests = (self._hmac,)
		try:
			transport.start_client()
		except BaseException as e:
			raise _MultiplexingProxy.Error('Could start an SSH client to', (self._proxyAddress, self._proxyPort), e)
		try:
			hostKey = transport.get_remote_server_key()
			if not self._publicKeyCompare(hostKey, self._serverFingerprintRSA) and not self._publicKeyCompare(hostKey, self._serverFingerprintECDSA):
				raise _MultiplexingProxy.Error('Host SSH fingerprint', self._prettyFingerprint(hostKey), 'did not match any of the fingerprints:', (self._serverFingerprintRSA, self._serverFingerprintECDSA))
			transport.auth_publickey(self._username, self._privateKey)
		except BaseException as e:
			raise _MultiplexingProxy.Error('Could not log in to the SSH server.', e)
		return transport
	def _disconnectSocket(self):
		_info('Disconnecting from SSH server', (self._proxyAddress, self._proxyPort))
		_MultiplexingProxy._disconnectSocket(self)
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
		'serverFingerprintRSA': {
			'default': None,
			'description': u'Fingerprint of the server\'s RSA key. If not provided and the server presents its RSA key, the connection will be closed.'
		},
		'serverFingerprintECDSA': {
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
		}
	}
}
