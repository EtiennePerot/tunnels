#!/usr/bin/env python

# Dirty script that reads /etc/services and creates a list of common ports by name
# Works with any Python

services='/etc/services'

import re

tcpPort = re.compile(r'^([^#\s]+)\s+(\d+)/tcp', re.IGNORECASE)
udpPort = re.compile(r'^([^#\s]+)\s+(\d+)/udp', re.IGNORECASE)

tcpPorts = {}
udpPorts = {}
for line in open(services, 'r').readlines():
	tcpResults = tcpPort.search(line)
	if tcpResults is not None:
		if tcpResults.group(1) not in tcpPorts:
			tcpPorts[tcpResults.group(1)] = set()
		tcpPorts[tcpResults.group(1)].add(int(tcpResults.group(2)))
	udpResults = udpPort.search(line)
	if udpResults is not None:
		if udpResults.group(1) not in udpPorts:
			udpPorts[udpResults.group(1)] = set()
		udpPorts[udpResults.group(1)].add(int(udpResults.group(2)))

# Plenty of registrations are done for the same port for both TCP and UDP.
# Most of these protocols only use one of them. The problem is that having
# each alias contain both means twice the number of sockets need to be
# allocated, and it also forces the user to use a proxy that supports UDP
# in order to use a port alias of a service that may only use TCP.
# Thus, this script assumes that if a port alias contains just the same TCP
# and UDP ports with the same number, then it will just use the TCP ones.
for t in tcpPorts:
	if t in udpPorts and tcpPorts[t] == udpPorts[t]:
		del udpPorts[t]

print('# ---------------------------------' + (len(services) * '-') + '-------------------------------')
print('# This file was autogenerated from ' +      services         + ' - Edits to this file get lost.')
print('# ---------------------------------' + (len(services) * '-') + '-------------------------------')
print('ports:')
for portAlias in sorted(set(tcpPorts.keys()) | set(udpPorts.keys())):
	ports = []
	if portAlias in tcpPorts:
		ports.extend(('t' + str(tcpPort) for tcpPort in sorted(tcpPorts[portAlias])))
	if portAlias in udpPorts:
		ports.extend(('u' + str(udpPort) for udpPort in sorted(udpPorts[portAlias])))
	print('\t' + portAlias + ': ' + ', '.join(ports))
