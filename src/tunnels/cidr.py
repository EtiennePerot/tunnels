import random as _random

class CIDR(object):
	def __init__(self, cidr=u'0.0.0.0/0'):
		if cidr == u'default':
			cidr = u'0.0.0.0/0'
		if u'/' not in cidr:
			cidr += u'/32'
		self._cidr = cidr
		self._ipPart, self._subnetPart = cidr.split(u'/', 2)
		ipParts = map(int, self._ipPart.split(u'.', 4))
		ipBits = (ipParts[0] << 24) | (ipParts[1] << 16) | (ipParts[2] << 8) | ipParts[3]
		keepBits = int(self._subnetPart)
		self._subnetBits = 32 - keepBits
		self._ipBits = ((2**keepBits - 1) << self._subnetBits)
		self._ipBase = ipBits & self._ipBits
		self._fullSubnetBits = 2**self._subnetBits - 1
	def getRandom(self):
		randomEnding = _random.getrandbits(self._subnetBits)
		while randomEnding == 0 or randomEnding == self._fullSubnetBits:
			randomEnding = _random.getrandbits(self._subnetBits)
		return self._ipBase | randomEnding
	def getSubnetBits(self):
		return int(self._subnetPart)
	def __contains__(self, ip):
		if type(ip) is not int:
			ipParts = map(int, ip.split(u'.', 4))
			ip = (ipParts[0] << 24) | (ipParts[1] << 16) | (ipParts[2] << 8) | ipParts[3]
		return ip & self._ipBits == self._ipBase
	def __str__(self):
		if self._subnetBits == 32:
			return u'default'
		if self._subnetBits == 0:
			return self._ipPart
		return self._ipPart + u'/' + self._subnetPart
	def __repr__(self):
		return str(self)
	def __eq__(self, other):
		if isinstance(other, self.__class__):
			return str(self) == str(other)
		return False
