import threading as _threading
import time as _time

from .cidr import CIDR as _CIDR
from .iproute import IPRoute as _IPRoute
from .tunnels import config as _config

def convertIp(rawIp):
	return '.'.join(map(str, (rawIp >> 24, rawIp >> 16 & 0xFF, rawIp >> 8 & 0xFF, rawIp & 0xFF)))

class _Mapper(_threading.Thread):
	def __init__(self):
		self._cidr = _CIDR(_config('privateAddresses'))
		self._domainsToIps = {}
		self._ipsToDomains = {}
		self._lastAccessTime = {}
		self._socketThreads = {}
		self._lock = _threading.RLock()
		self._alive = True
		self._cleanupTime = _config('addressCleanupTime')
		self._localRoute = _IPRoute(str(self._cidr) + u' dev lo')
		self._localRoute.enable()
		_threading.Thread.__init__(self, name='Tunnels mapper cleanup thread')
		self.daemon = True
		self.start()
	def getRawIp(self, domain):
		with self._lock:
			self._lastAccessTime[domain] = _time.time()
			if domain in self._domainsToIps:
				return self._domainsToIps[domain]
			newIp = self._cidr.getRandom()
			while newIp in self._ipsToDomains:
				newIp = self._cidr.getRandom()
			self._domainsToIps[domain] = newIp
			self._ipsToDomains[newIp] = domain
			return newIp
	def getIp(self, domain):
		return convertIp(self.getRawIp(domain))
	def getDomain(self, ip):
		with self._lock:
			return self._ipsToDomains.get(ip, None)
	def registerSocketThread(self, domain, socketThread):
		with self._lock:
			self._socketThreads[domain] = socketThread
	def hasSocketThread(self, domain):
		with self._lock:
			return domain in self._socketThreads
	def _cleanup(self):
		with self._lock:
			cleanupThreshold = _time.time() - self._cleanupTime
			toDelete = []
			for domain in self._lastAccessTime:
				if self._lastAccessTime[domain] < cleanupThreshold:
					toDelete.append(domain)
			for domain in toDelete:
				del self._lastAccessTime[domain]
				del self._ipsToDomains[self._domainsToIps[domain]]
				del self._domainsToIps[domain]
				if domain in self._socketThreads:
					self._socketThreads[domain].kill()
					del self._socketThreads[domain]
	def run(self):
		while self._alive:
			_time.sleep(self._cleanupTime / 4)
			self._cleanup()
	def kill(self):
		with self._lock:
			self._alive = False
			self._localRoute.disable()

_mapper = None
getRawIp = lambda x: None
getIp = lambda x: None
getDomain = lambda x: None
registerSocketThread = lambda x: None
hasSocketThread = lambda x: None
def init():
	global _mapper, getRawIp, getIp, getDomain, registerSocketThread, hasSocketThread
	_mapper = _Mapper()
	getRawIp = _mapper.getRawIp
	getIp = _mapper.getIp
	getDomain = _mapper.getDomain
	registerSocketThread = _mapper.registerSocketThread
	hasSocketThread = _mapper.hasSocketThread

def deinit():
	_mapper.kill()
