import struct as _struct

class DNSQuery(object):
	def __init__(self, data):
		self._data = data
		self._domain = None
		self._ipv6 = None
		if (ord(data[2]) >> 3) & 0xF == 0:
			position = 12
			domainPartLength = ord(data[position])
			self._domain = b''
			while domainPartLength != 0:
				self._domain += data[position + 1:position + domainPartLength + 1] + b'.'
				position += domainPartLength + 1
				domainPartLength = ord(data[position])
			recordType = self._data[position + 1:position + 3]
			if recordType == b'\x00\x01':
				self._ipv6 = False
			elif recordType == b'\x00\x1c':
				self._ipv6 = True
			self._data = self._data[:position + 5] # Truncate extra records and stuff
			if self._domain[-1] == b'.':
				self._domain = self._domain[:-1]
	def getDomain(self):
		return self._domain
	def isIPv6(self):
		return self._ipv6
	def buildResponsePacket(self, ip, ttl):
		if self._ipv6 is None or self._domain is None:
			return b''
		packet = self._data[:2] + b'\x81\x80' + self._data[4:6] + self._data[4:6] + b'\x00\x00\x00\x00' + self._data[12:] + b'\xc0\x0c'
		if self._ipv6:
			packet += b'\x00\x1c'
		else:
			packet += b'\x00\x01'
		packet += b'\x00\x01' + _struct.pack(b'>I', ttl)
		if self._ipv6:
			packet += b'\x00\x16'
			raise NotImplementedError() # TODO Pack IPv6 address
		else:
			packet += b'\x00\x04'
			packet += _struct.pack(b'>I', ip) # The actual IP address
		return packet
