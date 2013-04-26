import imp as _imp
import os as _os

def _importFile(file, namePrefix='tunnels_proxy_'):
	moduleName = namePrefix + _os.path.basename(file)
	if moduleName.lower().endswith('.py'):
		moduleName = moduleName[:-3]
	_imp.acquire_lock()
	newModule = _imp.load_source(moduleName, file)
	_imp.release_lock()
	return newModule

_proxies = {}
def mkProxy(proxyName, proxyConfig):
	global _proxies
	if u'type' not in proxyConfig:
		raise ValueError(u'Proxy type not provided in proxy definition "' + proxyName + u'"')
	proxy = proxyConfig[u'type']
	if proxy not in _proxies:
		proxyFile = _os.path.dirname(_os.path.abspath(__file__)) + _os.sep + proxy + '.py'
		if not _os.path.isfile(proxyFile):
			raise ValueError(u'Invalid proxy type: "' + proxy + u'"; file not found: "' + proxyFile + u'"')
		try:
			proxyData = _importFile(proxyFile)
		except BaseException as e:
			raise SystemError(u'Error while trying to import "' + proxyFile + u'"', e)
		if 'proxyInfo' not in proxyData.__dict__:
			raise SystemError(u'proxyInfo not found in "' + proxyFile + u'"')
		if type(proxyData.proxyInfo) is not type({}):
			raise SystemError('proxyInfo is not a dictionary in "' + proxyFile + u'"')
		for key in (u'class', u'config'):
			if key not in proxyData.proxyInfo:
				raise SystemError(u'"' + proxyFile + u'": Key not found in proxyInfo: "' + key + u'"')
		proxyClass = proxyData.proxyInfo['class']
		proxyDefaultConfig = {}
		proxyConfigRequired = []
		for key in proxyData.proxyInfo['config']:
			if 'default' in proxyData.proxyInfo['config'][key]:
				proxyDefaultConfig[key] = proxyData.proxyInfo['config'][key]['default']
			else:
				proxyConfigRequired.append(key)
		proxyClass._proxyConfig = proxyDefaultConfig
		proxyClass._proxyConfigRequired = proxyConfigRequired
		_proxies[proxy] = proxyClass
	return _proxies[proxy](proxyName, proxyConfig)
