import random as _random
import select as _select
import socket as _socket
import threading as _threading
from .dnsquery import DNSQuery as _DNSQuery
from .mapper import getRawIp as _getRawIp
from .mapper import convertIp as _convertIp
from .serversocket import spawn as _spawnServer
from .tunnels import config as _config
from .tunnels import hasPolicy as _hasPolicy

from .logger import mkInfoFunction as _mkInfoFunction
_dnsInfo = _mkInfoFunction('DNS')

class _DNSServer(_threading.Thread):
	def __init__(self):
		self._socket = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
		self._socket.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
		bindAddress = _config('dnsBindAddress').split(u':')
		if len(bindAddress) == 1:
			bindAddress = (bindAddress[0], 53)
		self._socket.bind((bindAddress[0], int(bindAddress[1])))
		self._packetSize = int(_config('dnsPacketSize'))
		upstreamDns = _config('upstreamDns').split(u':')
		if len(upstreamDns) == 1:
			upstreamDns = (upstreamDns[0], 53)
		self._upstreamDns = (upstreamDns[0], int(upstreamDns[1]))
		self._upstreamDnsTimeout = int(_config('upstreamDnsTimeout'))
		self._ttl = int(_config('addressCleanupTime') / 4)
		_threading.Thread.__init__(self)
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
								_spawnServer(domain, _convertIp(matchingRawIp))
								socket.sendto(query.buildResponsePacket(matchingRawIp, ttl=self._ttl), address)
							# Otherwise, just don't answer
							continue
						# Otherwise, forward the request to the upstream DNS server
						dnsSocket = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
						while 8:
							tempPort = _random.randint(*_temporaryPortRange)
							try:
								dnsSocket.bind(('', tempPort))
							except _socket.error:
								continue
							break
						dnsSocket.sendto(data, self._upstreamDns)
						socketMap[dnsSocket] = address # Save return address
						socketList.append(dnsSocket) # Add to socket select() list
						_dnsInfo('DNS server got', query.getQueryType(), 'query for', domain, '- Forwarded to upstream DNS server', self._upstreamDns, 'from local port', tempPort)
					else:
						data, source = socket.recvfrom(self._packetSize)
						if source == self._upstreamDns: # Make sure the packet actually came from the upstream DNS server
							self._socket.sendto(data, socketMap[socket]) # Send it to the client from the socket that received the query originally
							socket.close() # Close the socket to the upstream DNS server
							socketList.remove(socket)
							del socketMap[socket]
						else:
							_dnsInfo('DNS server got packet on socket', dnsSocket.getsockname(), 'but it did not come from upstream DNS server; it came from', source)
			elif len(socketMap): # Timeout occurred and there is at least one upstream DNS request going on
				for socket in socketList[1:]: # Close all DNS sockets
					socket.close()
				socketList = [socketList[0]] # Reset socket list
				socketMap = {} # Reset socket map

_temporaryPortRange = None

def init():
	global _temporaryPortRange
	_DNSServer().start()
	_temporaryPortRange = tuple(map(int, _config('temporaryBindPortRange').split(u'-')))
