import random as _random
import re as _re
import select as _select
import socket as _socket
import threading as _threading
from .dnsquery import DNSQuery as _DNSQuery
from .mapper import getRawIp as _getRawIp
from .mapper import convertIp as _convertIp
from .parseutils import addressParse as _addressParse
from .parseutils import multiAddressParse as _multiAddressParse
from .parseutils import portRangeParse as _portRangeParse
from .serversocket import spawn as _spawnServer
from .tunnels import config as _config
from .tunnels import hasPolicy as _hasPolicy

from .logger import mkInfoFunction as _mkInfoFunction
_dnsInfo = _mkInfoFunction('DNS')

class _DNSServer(_threading.Thread):
	nullroutedDomain = u'tunnels:null'
	def __init__(self):
		self._socket = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
		self._socket.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
		self._socket.bind(_addressParse(_config('dnsBindAddress'), defaultPort=53, asTuple=True))
		self._packetSize = int(_config('dnsPacketSize'))
		self._upstreamDns = _multiAddressParse(_config('upstreamDns'), defaultPort=53, asTuple=True)
		self._upstreamDnsTimeout = int(_config('upstreamDnsTimeout'))
		self._ttl = int(_config('addressCleanupTime') / 4)
		self._blockUndefinedDomains = _config('blockUndefinedDomains')
		_threading.Thread.__init__(self, name='Tunnels DNS server thread')
		self.daemon = True
	def run(self):
		readList = []
		writeList = []
		exceptionList = []
		socketList = [self._socket]
		socketMap = {}
		while 8:
			readList, writeList, exceptionList = _select.select(socketList, [], [], self._upstreamDnsTimeout)
			if len(readList):
				for socket in readList:
					if socket is self._socket:
						data, address = socket.recvfrom(self._packetSize)
						query = _DNSQuery(data)
						domain = query.getDomain()
						if domain is not None and _hasPolicy(domain):
							if query.isIPv6():
								continue # TODO
							matchingRawIp = _getRawIp(domain)
							if matchingRawIp is not None:
								prettyIp = _convertIp(matchingRawIp)
								_dnsInfo('DNS server got', query.getQueryType(), 'query for', domain, '- There are rules for this domain. Returning fake IP address', prettyIp)
								_spawnServer(domain, prettyIp)
								socket.sendto(query.buildResponsePacket(matchingRawIp, ttl=self._ttl), address)
							# Otherwise, just don't answer
							continue
						elif domain is not None and self._blockUndefinedDomains:
							if query.isIPv6():
								continue # TODO
							matchingRawIp = _getRawIp(_DNSServer.nullroutedDomain)
							_dnsInfo('DNS server got', query.getQueryType(), 'query for', domain, '- No rules for this domain, default policy is to block. Returning fake IP address', _convertIp(matchingRawIp))
							socket.sendto(query.buildResponsePacket(matchingRawIp, ttl=self._ttl), address)
						else:
							# Otherwise, forward the request to an upstream DNS server
							dnsSocket = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
							while 8:
								tempPort = _random.randint(*_temporaryPortRange)
								try:
									dnsSocket.bind(('', tempPort))
								except _socket.error:
									continue
								break
							upstreamDns = _random.choice(self._upstreamDns)
							dnsSocket.sendto(data, upstreamDns)
							socketMap[dnsSocket] = (upstreamDns, address) # Save upstream DNS and return address
							socketList.append(dnsSocket) # Add to socket select() list
							_dnsInfo('DNS server got', query.getQueryType(), 'query for', domain, '- Forwarded to upstream DNS server', upstreamDns, 'from local port', tempPort)
					else:
						data, source = socket.recvfrom(self._packetSize)
						if source == socketMap[socket][0]: # Make sure the packet actually came from the upstream DNS server
							self._socket.sendto(data, socketMap[socket][1]) # Send it to the client from the socket that received the query originally
							socket.close() # Close the socket to the upstream DNS server
							socketList.remove(socket)
							del socketMap[socket]
						else:
							_dnsInfo('DNS server got packet on socket', dnsSocket.getsockname(), 'but it did not come from upstream DNS server', socketMap[socket][0],'- it came from', source)
			elif len(socketMap): # Timeout occurred and there is at least one upstream DNS request going on
				for socket in socketList[1:]: # Close all DNS sockets
					socket.close()
				socketList = [socketList[0]] # Reset socket list
				socketMap = {} # Reset socket map

_temporaryPortRange = None

def init():
	global _temporaryPortRange
	_DNSServer().start()
	_temporaryPortRange = _portRangeParse(_config('temporaryBindPortRange'))
