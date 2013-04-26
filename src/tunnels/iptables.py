import subprocess as _subprocess
import threading as _threading
from .tunnels import config as _config

def _iptables(*args):
	command = [u'iptables', u'-t', u'nat']
	command.extend(args)
	try:
		_subprocess.check_output(command, stderr=_subprocess.STDOUT)
		return True
	except _subprocess.CalledProcessError:
		return False

_iptablesChain = None

def addRedirect(destination, protocol, fromPort, toPort):
	return _iptables(u'-A', _iptablesChain, u'-d', destination, u'-p', protocol, u'--dport', str(fromPort), u'-j', u'REDIRECT', u'--to-ports', str(toPort))

def removeRedirect(destination, protocol, fromPort, toPort):
	return _iptables(u'-D', _iptablesChain, u'-d', destination, u'-p', protocol, u'--dport', str(fromPort), u'-j', u'REDIRECT', u'--to-ports', str(toPort))

def init():
	global _iptablesChain
	_iptablesChain = _config('iptablesChain')
	# Delete old chain if it is there for some reason
	deinit()
	# Add new chain
	_iptables(u'-N', _iptablesChain)
	_iptables(u'-A', u'PREROUTING', u'-j', _iptablesChain)
	_iptables(u'-A', u'OUTPUT', u'-j', _iptablesChain)

def deinit():
	_iptables(u'-D', u'OUTPUT', u'-j', _iptablesChain)
	_iptables(u'-D', u'PREROUTING', u'-j', _iptablesChain)
	_iptables(u'-F', _iptablesChain)
	_iptables(u'-X', _iptablesChain)
