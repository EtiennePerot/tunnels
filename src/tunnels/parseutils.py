import random as _random
import re as _re

_commaSeparatedSplit = _re.compile(u'\\s*,[,\\s]*')
def commaSeparatedSplit(*args, **kwargs):
	return _commaSeparatedSplit.split(*args, **kwargs)


_plusSeparatedSplit = _re.compile(u'\\s*\\+[+\\s]*')
def plusSeparatedSplit(*args, **kwargs):
	return _plusSeparatedSplit.split(*args, **kwargs)

def randomString(length, set=u'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'):
	return u''.join((_random.choice(set) for i in range(length)))

_randomCredentialsLength = None
def addressParse(address, defaultPort=u'Address must include a port number (address:portNumber).', asTuple=False):
	global _randomCredentialsLength
	if _randomCredentialsLength is None:
		from .tunnels import config as _config
		_randomCredentialsLength = _config(u'randomCredentialsLength')
	username = password = port = None
	if u'@' in address:
		address = address.split(u'@')
		username, password = address[0].split(u':')
		if username == u'$RANDOM':
			username = randomString(_randomCredentialsLength)
		if password == u'$RANDOM':
			password = randomString(_randomCredentialsLength)
		address = address[1]
	if u':' in address:
		address, port = address.split(u':')
		port = int(port)
	elif type(defaultPort) is type(u''):
		raise ValueError(defaultPort)
	elif type(defaultPort) is int:
		port = defaultPort
	if asTuple:
		return (address, port)
	return {
		'address': address,
		'port': port,
		'username': username,
		'password': password
	}

def multiAddressParse(addresses, *args, **kwargs):
	return [addressParse(x, *args, **kwargs) for x in commaSeparatedSplit(addresses)]

def portRangeParse(portRange):
	return tuple(map(int, portRange.split(u'-')))
