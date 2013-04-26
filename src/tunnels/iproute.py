import re as _re
import subprocess as _subprocess
from .cidr import CIDR as _CIDR

class IPRoute(object):
	_whiteSpace = _re.compile(u'\\s+')
	def __init__(self, line=None, cidr=None, via=None, dev=None, proto=None, scope=None, src=None):
		if line is not None:
			components = IPRoute._whiteSpace.split(line)
			self.cidr = _CIDR(components[0])
			self.via = self.dev = self.proto = self.scope = self.src = None
			for key, value in zip(components[1::2], components[2::2]):
				if key == u'via':
					self.via = _CIDR(value)
				elif key == u'dev':
					self.dev = value
				elif key == u'scope':
					self.scope = value
				elif key == u'proto':
					self.proto = value
				elif key == u'src':
					self.src = value
		else:
			self.cidr = _CIDR(cidr)
			self.via = _CIDR(via)
			self.dev = dev
			self.proto = proto
			self.scope = scope
			self.src = src
	def isEnabled(self):
		return self in getRoutes()
	def enable(self): # Note: Prone to race conditions
		if self.isEnabled():
			return
		_subprocess.check_output(['ip', 'route', 'replace'] + str(self).split(u' '))
	def disable(self): # Note: Prone to race conditions
		if not self.isEnabled():
			return
		_subprocess.check_output(['ip', 'route', 'delete', str(self.cidr)])
	def __eq__(self, other):
		if isinstance(other, self.__class__):
			return (
				     self.cidr == other.cidr
				and (self.via is None or other.via is None or self.via == other.via)
				and (self.dev is None or other.dev is None or self.dev == other.dev)
				and (self.scope is None or other.scope is None or self.scope == other.scope)
				and (self.proto is None or other.proto is None or self.proto == other.proto)
				and (self.src is None or other.src is None or self.src == other.src)
			)
		return False
	def __str__(self):
		s = u'{}'.format(self.cidr)
		for key in (u'via', u'dev', u'proto', u'scope', u'src'):
			if getattr(self, key) is not None:
				s += u' ' + key + u' ' + str(getattr(self, key))
		return s
	def __repr__(self):
		return str(self)

def getRoutes():
	routesOutput = _subprocess.check_output(['ip', 'route', 'show']).decode('ascii')
	routes = []
	for line in routesOutput.split(u'\n'):
		if line.strip():
			routes.append(IPRoute(line=line.strip()))
	return routes

def getRouteTo(ip):
	bestRoute = None
	bestSubnetBits = -1
	for route in self.getRoutes():
		if ip in route.cidr and route.cidr.getSubnetBits() > bestSubnetBits:
			bestRoute = route
			bestSubnetBits = route.cidr.getSubnetBits()
	return bestRoute
