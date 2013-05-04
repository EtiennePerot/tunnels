import itertools as _itertools
import os as _os
import re as _re
import shutil as _shutil
import subprocess as _subprocess
import threading as _threading
import time as _time
import yaml as _yaml

from .confsys import Config as _Config
from .confsys import Configurable as _Configurable
from .parseutils import commaSeparatedSplit as _commaSeparatedSplit
from .parseutils import plusSeparatedSplit as _plusSeparatedSplit

from .logger import mkInfoFunction as _mkInfoFunction
_info = _mkInfoFunction('Main')

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
	def addRule(self, domain, port, rule):
		"""
		- domain: The domain or domain pattern to match
		- port: u'tXXXX' for TCP, u'uXXXX' for UDP
		- rule: The _TunnelRule instance
		"""
		if domain[0] == u'.':
			self.addRule(domain[1:], port, rule)
			self.addRule(u'*' + domain, port, rule)
			return
		if rule['proxy'] not in self._proxies:
			raise ValueError(u'Undefined proxy: "' + rule['proxy'] + u'"')
		proxyObject = self._proxies[rule['proxy']]
		rule.setProxy(proxyObject)
		d = None
		e = None
		if port[0] == u't':
			if not proxyObject.supportsTCP():
				raise ValueError(u'Proxy "' + rule['proxy'] + u'" does not support TCP.')
			d = self._tcpDomains
			e = self._tcpExtraMatches
		elif port[0] == u'u':
			if not proxyObject.supportsUDP():
				raise ValueError(u'Proxy "' + rule['proxy'] + u'" does not support UDP.')
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
			d[domain][port] = rule
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
	def _getConfigs(self, d, e, domain):
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
		return self.getTCPRules(domain) is not None or self.getUDPRules(domain) is not None
	def getTCPRules(self, domain):
		return self._getConfigs(self._tcpDomains, self._tcpExtraMatches, domain)
	def getUDPRules(self, domain):
		return self._getConfigs(self._udpDomains, self._udpExtraMatches, domain)

class _TunnelRule(_Configurable):
	_tunnelRuleConfig = {
		'forcedAddress': None,
		'resolution': None
	}
	_tunnelRuleRequired = ['proxy']
	def __init__(self, name, config):
		_Configurable.__init__(self, name, config, _TunnelRule._tunnelRuleConfig, _TunnelRule._tunnelRuleRequired)
		self._forcedAddresses = None
		if self['forcedAddress'] is not None:
			self._forcedAddresses = _commaSeparatedSplit(self['forcedAddress'])
		self._proxyObject = None
	def getForcedAddresses(self):
		return self._forcedAddresses
	def setProxy(self, proxyObject):
		self._proxyObject = proxyObject
	def getProxy(self):
		return self._proxyObject

class _PortsConfig(object):
	_numericalPort = _re.compile(u'[ut]\\d+')
	_allNumbers = _re.compile('\\d+')
	def __init__(self):
		self._ports = {}
	def add(self, name, value):
		if name in self._ports:
			raise ValueError(u'Cannot define port "' + name + u'" twice.')
		self._ports[name] = _plusSeparatedSplit(value)
	def get(self, ports):
		finalList = []
		for port in _plusSeparatedSplit(ports):
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

_terminationEvent = None
_tunnelsConfig = None
hasPolicy = lambda *args: None
getTCPRules = lambda *args: None
getUDPRules = lambda *args: None

_config = None
def config(key):
	return _config[key]

_defaultMainConfig = {
	'privateAddresses': u'10.42.0.0/16',
	'addressCleanupTime': 3600,
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
	'silentLog': '',
	'randomCredentialsLength': 16
}
_requiredMainConfig = ['upstreamDns']

def init(configEntries):
	global _terminationEvent, _config, _tunnelsConfig, hasPolicy, getTCPRules, getUDPRules
	# Basic init
	_config = {}
	_tunnelsConfig = _TunnelsConfig()
	hasPolicy = _tunnelsConfig.hasPolicy
	getTCPRules = _tunnelsConfig.getTCPRules
	getUDPRules = _tunnelsConfig.getUDPRules
	# Take care of the config
	from .proxies import mkProxy
	# Gather all config dictionaries
	allConfigs = []
	def gatherConfigs(f):
		if _os.path.isdir(f):
			for sub in _os.listdir(f):
				gatherConfigs(_os.path.join(f, sub))
		elif _os.path.isfile(f):
			allConfigs.append(_yaml.load(open(f)))
	for configEntry in configEntries:
		if not _os.path.exists(configEntry):
			raise ValueError(u'"' + configEntry + u'" does not exist.')
		gatherConfigs(configEntry)
	# Start populating the config structures
	portsConfig = _PortsConfig()
	allRules = []
	allProxies = []
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
					allProxies.append((proxyName, proxyConfig))
			elif key == u'rules':
				for ruleHosts, ruleConfig in value.items():
					allRules.append((ruleHosts, ruleConfig))
			else:
				if key in _config:
					raise ValueError(u'Duplicate configuration entry for "' + key + u'"')
				_config[key] = value
	# Wrap config object
	_config = _Configurable(u'main config', _config, _defaultMainConfig, _requiredMainConfig)
	# Expand ports
	portsConfig.expandAll()
	# Create proxies
	for proxyName, proxyConfig in allProxies:
		_tunnelsConfig.addProxy(proxyName, mkProxy(proxyName, proxyConfig))
	# Process rules
	for ruleHosts, ruleConfig in allRules:
		if type(ruleConfig) is not type({}):
			ruleConfig = {
				'proxy': ruleConfig
			}
		rule = _TunnelRule(ruleHosts, ruleConfig)
		for ruleHost in _commaSeparatedSplit(ruleHosts):
			if u'@' not in ruleHost:
				raise ValueError(u'The rule for domain "' + ruleHost + u'" does not specify a port.')
			ruleHost, rulePorts = ruleHost.split(u'@')
			for rulePort in portsConfig.get(rulePorts):
				_tunnelsConfig.addRule(ruleHost, rulePort, rule)
	# If we get here without an exception, then the config is probably fine. Launch the torpedoes or something.
	from .logger import startLog, stopLog
	startLog(silencedModules=_commaSeparatedSplit(config('silentLog')))
	from .mapper import init as mapperInit
	mapperInit()
	from .dnsserver import init as dnsServerInit
	dnsServerInit()
	from .serversocket import init as serversocketInit
	serversocketInit()
	from .iptables import init as iptablesInit
	iptablesInit()
	if config('overwriteResolvconf'):
		if not _os.path.isfile(config('resolvconfPath')):
			raise ValueError(u'No resolv.conf file found at "' + config('resolvconfPath') + u'", but overwriteResolvconf is enabled.')
		_shutil.copy2(config('resolvconfPath'), config('resolvconfBackupPath'))
		f = open(config('resolvconfPath'), 'w')
		f.write('nameserver ' + config('dnsBindAddress'))
		f.close()
		_info(u'Your resolv.conf file', config('resolvconfPath'), u'has been modified to point to Tunnels.')
		if config('makeResolvconfImmutable'):
			_subprocess.check_output(['chattr', '+i', config('resolvconfPath')])
			_info(u'It has also been made immutable (chattr +i).')
		if config('restoreResolvConf'):
			_info(u'The old file has been backed up to', config('resolvconfBackupPath'), u'and will be restored on exit.')
		else:
			_info(u'The old file has been backed up to', config('resolvconfBackupPath'), u'but will NOT be restored on exit.')
	_terminationEvent = _threading.Event()
	_info(u'Tunnels setup work done; ready to start.')
	stopLog()

def run():
	from .logger import startLog, flushLog
	startLog(None)
	from .mapper import run as mapperRun
	mapperRun()
	from .dnsserver import run as dnsServerRun
	dnsServerRun()
	_info(u'Tunnels operational.')
	_info(u'Make sure to point your DNS settings to it.')
	_info(u'Remember that data lingering in the DNS cache may make some domains not go through Tunnels until the TTL expires.')
	try:
		while not _terminationEvent.is_set():
			_terminationEvent.wait(3600)
	except KeyboardInterrupt:
		print('\rInterrupted, shutting down.')
	flushLog()

def terminate():
	from .logger import flushLog
	from .mapper import deinit as mapperDeinit
	from .iptables import deinit as iptablesDeinit
	mapperDeinit()
	iptablesDeinit()
	if config('overwriteResolvconf') and config('restoreResolvConf'):
		if config('makeResolvconfImmutable'):
			_subprocess.check_output(['chattr', '-i', config('resolvconfPath')])
		_shutil.copy2(config('resolvconfBackupPath'), config('resolvconfPath'))
		_os.remove(config('resolvconfBackupPath'))
		_info(u'Your resolv.conf file', config('resolvconfPath'), u'has been restored from the backup at', config('resolvconfBackupPath'))
	flushLog(thisThread=True)
	_terminationEvent.set()

def main(configEntries):
	init(configEntries)
	run()
	terminate()
