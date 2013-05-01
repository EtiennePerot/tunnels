import itertools as _itertools
import os as _os
import re as _re
from .confsys import Config as _Config
from .confsys import Configurable as _Configurable

class _TunnelsConfig(object):
	def __init__(self):
		self._proxies = {}
		self._tcpDomains = {}
		self._udpDomains = {}
		self._tcpExtraMatches = {}
		self._udpExtraMatches = {}
		self._regexDomainCounter = _itertools.count()
	def addProxy(self, name, proxy):
		if name in self._proxies:
			raise ValueError(u'Duplicate proxy name: "' + name + u'"')
		self._proxies[name] = proxy
	def addRule(self, domain, port, proxy):
		"""
		- domain: The domain or domain pattern to match
		- port: u'tXXXX' for TCP, u'uXXXX' for UDP
		- proxy: Name of the proxy to use
		"""
		if domain[0] == u'.':
			self.addRule(domain[1:], port, proxy)
			self.addRule(u'*' + domain, port, proxy)
			return
		if proxy not in self._proxies:
			raise ValueError(u'Undefined proxy: "' + proxy + u'"')
		proxyObject = self._proxies[proxy]
		d = None
		e = None
		if port[0] == u't':
			if not proxyObject.supportsTCP():
				raise ValueError(u'Proxy "' + proxy + u'" does not support TCP.')
			d = self._tcpDomains
			e = self._tcpExtraMatches
		elif port[0] == u'u':
			if not proxyObject.supportsUDP():
				raise ValueError(u'Proxy "' + proxy + u'" does not support UDP.')
			d = self._udpDomains
			e = self._udpExtraMatches
		else:
			raise ValueError(u'Invalid port identifier: "' + str(port) + u'"')
		port = int(port[1:])
		if domain[0] == u'*':
			domain = domain[1:]
		if u'*' in domain: # If there are other wildcards
			domain = self._addRegexDomain(e, domain)
		if domain not in d:
			d[domain] = {}
		if port not in d[domain]:
			d[domain][port] = proxyObject
		else:
			raise ValueError(u'Duplicate configuration for "' + domain + u':' + str(port) + u'"')
	def _addRegexDomain(self, extraMatches, domain):
		domainKey = u'regex:' + str(self._regexDomainCounter.next())
		regex = domain.replace(u'.', u'\\.').replace(u'*', u'[^.]+')
		if regex[0] == u'.':
			regex = u'(?:.+\\.)?' + regex[1:]
		regex = _re.compile(regex)
		extraMatches[domainKey] = regex
		return domainKey
	def _getProxies(self, d, e, domain):
		if domain not in d:
			originalDomain = domain
			while u'.' in domain[1:] and domain not in d:
				domain = domain[1 + domain[1:].find(u'.'):]
			if domain not in d: # Still not found
				for domainKey in e: # Try the regex ones
					if e[domainKey].match(originalDomain):
						return d[domainKey]
				return d.get(u'', None) # Everything failed, so return default if it is defined, otherwise return empty
		return d[domain]
	def hasPolicy(self, domain):
		return self.getTCPProxies(domain) is not None or self.getUDPProxies(domain) is not None
	def getTCPProxies(self, domain):
		return self._getProxies(self._tcpDomains, self._tcpExtraMatches, domain)
	def getUDPProxies(self, domain):
		return self._getProxies(self._udpDomains, self._udpExtraMatches, domain)

class _PortsConfig(object):
	_plusSeparatedSplit = _re.compile(u'\\s*\\+[+\\s]*')
	_numericalPort = _re.compile(u'[ut]\\d+')
	_allNumbers = _re.compile('\\d+')
	def __init__(self):
		self._ports = {}
	def add(self, name, value):
		if name in self._ports:
			raise ValueError(u'Cannot define port "' + name + u'" twice.')
		self._ports[name] = _PortsConfig._plusSeparatedSplit.split(value)
	def get(self, ports):
		finalList = []
		for port in _PortsConfig._plusSeparatedSplit.split(ports):
			if _PortsConfig._numericalPort.match(port):
				finalList.append(port)
			elif port in self._ports:
				finalList.extend(self._ports[port])
			elif _PortsConfig._allNumbers.match(port):
				raise ValueError(u'Invalid port number "' + port + u'"; did you mean "t' + port + u'" (TCP port ' + port + u') or "u' + port + u'" (UDP port ' + port + u')?')
			else:
				raise ValueError(u'Invalid port name "' + port + u'".')
		return finalList
	def expandAll(self):
		for portName in self._ports:
			keepExpanding = True
			while keepExpanding:
				keepExpanding = False
				newList = []
				for port in self._ports[portName]:
					if _PortsConfig._numericalPort.match(port):
						newList.append(port)
					else:
						if port not in self._ports:
							raise SystemError(u'Undefined port name: "' + port + u'"')
						keepExpanding = True
						newList.extend(self._ports[port])
				self._ports[portName] = newList

_tunnelsConfig = None
hasPolicy = lambda *args: None
getTCPProxies = lambda *args: None
getUDPProxies = lambda *args: None

_config = None
def config(key):
	return _config[key]

_defaultMainConfig = {
	'privateAddresses': u'10.42.0.0/16',
	'addressCleanupTime': 60,
	'dnsBindAddress': u'127.0.0.1',
	'dnsPort': 53,
	'overwriteResolvconf': True,
	'restoreResolvConf': True,
	'makeResolvconfImmutable': True,
	'resolvconfPath': u'/etc/resolv.conf',
	'resolvconfBackupPath': u'/etc/resolv.conf.tunnels-backup',
	'dnsPacketSize': 65535,
	'upstreamDnsTimeout': 300,
	'temporaryBindPortRange': u'30000-55000',
	'iptablesChain': u'tunnels_redirects',
	'blockUndefinedDomains': False,
	'silentLog': ''
}
_requiredMainConfig = ['upstreamDns']

def main(confDir):
	global _config, _tunnelsConfig, hasPolicy, getTCPProxies, getUDPProxies
	# Basic init
	_config = {}
	_tunnelsConfig = _TunnelsConfig()
	hasPolicy = _tunnelsConfig.hasPolicy
	getTCPProxies = _tunnelsConfig.getTCPProxies
	getUDPProxies = _tunnelsConfig.getUDPProxies
	# Take care of the config
	import os
	import shutil
	import subprocess
	import sys
	import time
	import yaml
	from .proxies import mkProxy
	if not os.path.isdir(confDir):
		raise ValueError(confDir + u' is not a valid directory.')
	# Gather all config dictionaries
	allConfigs = []
	def gatherConfigs(f):
		if os.path.isdir(f):
			for sub in os.listdir(f):
				gatherConfigs(os.path.join(f, sub))
		elif os.path.isfile(f):
			allConfigs.append(yaml.load(open(f)))
	gatherConfigs(confDir)
	# Start populating the config structures
	portsConfig = _PortsConfig()
	allRules = []
	for conf in allConfigs:
		if type(conf) is not type({}):
			continue
		for key, value in conf.items():
			if value is None:
				continue
			if key == u'ports':
				for portName, portValue in value.items():
					portsConfig.add(portName, portValue)
			elif key == u'proxies':
				for proxyName, proxyConfig in value.items():
					_tunnelsConfig.addProxy(proxyName, mkProxy(proxyName, proxyConfig))
			elif key == u'rules':
				for ruleHosts, ruleProxy in value.items():
					allRules.append((ruleHosts, ruleProxy))
			else:
				if key in _config:
					raise ValueError('Duplicate configuration entry for "' + key + '"')
				_config[key] = value
	# Expand ports
	portsConfig.expandAll()
	# Process rules
	commaSeparatedSplit = _re.compile(u'\\s*,[,\\s]*')
	for ruleHosts, ruleProxy in allRules:
		for ruleHost in commaSeparatedSplit.split(ruleHosts):
			if u'@' not in ruleHost:
				raise ValueError('The rule for domain "' + ruleHost + u'" does not specify a port.')
			ruleHost, rulePorts = ruleHost.split(u'@')
			for rulePort in portsConfig.get(rulePorts):
				_tunnelsConfig.addRule(ruleHost, rulePort, ruleProxy)
	# Wrap config object
	_config = _Configurable(u'main config', _config, _defaultMainConfig, _requiredMainConfig)
	# If we get here without an exception, then the config is probably fine. Launch the torpedoes or something.
	from .mapper import init as mapperInit
	from .mapper import deinit as mapperDeinit
	mapperInit()
	from .dnsserver import init as dnsServerInit
	dnsServerInit()
	from .serversocket import init as serversocketInit
	serversocketInit()
	from .iptables import init as iptablesInit
	from .iptables import deinit as iptablesDeinit
	iptablesInit()
	from .logger import startLog, info
	from .logger import deinit as logDeinit
	startLog(silencedModules=commaSeparatedSplit.split(config('silentLog').upper()))
	if config('overwriteResolvconf'):
		shutil.copy2(config('resolvconfPath'), config('resolvconfBackupPath'))
		f = open(config('resolvconfPath'), 'w')
		f.write('nameserver ' + config('dnsBindAddress'))
		f.close()
		info(u'Your resolv.conf file', config('resolvconfPath'), u'has been modified to point to Tunnels.')
		if config('makeResolvconfImmutable'):
			subprocess.check_output(['chattr', '+i', config('resolvconfPath')])
			info(u'It has also been made immutable (chattr +i).')
		if config('restoreResolvConf'):
			info(u'The old file has been backed up to', config('resolvconfBackupPath'), u'and will be restored on exit.')
		else:
			info(u'The old file has been backed up to', config('resolvconfBackupPath'), u'but will NOT be restored on exit.')
	info(u'Tunnels operational.')
	info(u'Make sure to point your DNS settings to it.')
	info(u'Remember that data lingering in the DNS cache may make some domains not go through Tunnels until the TTL expires.')
	try:
		while 8:
			time.sleep(3600)
	except KeyboardInterrupt:
		print('\rInterrupted, shutting down.')
	mapperDeinit()
	iptablesDeinit()
	if config('overwriteResolvconf') and config('restoreResolvConf'):
		if config('makeResolvconfImmutable'):
			subprocess.check_output(['chattr', '-i', config('resolvconfPath')])
		shutil.copy2(config('resolvconfBackupPath'), config('resolvconfPath'))
		os.remove(config('resolvconfBackupPath'))
		info(u'Your resolv.conf file', config('resolvconfPath'), u'has been restored from the backup at', config('resolvconfBackupPath'))
	logDeinit()
