if __name__ == u'__main__':
	import sys
	if len(sys.argv) < 2:
		sys.stderr.write(u'Usage: ' + sys.argv[0] + u' <confDir>\n')
		sys.exit(1)
	from .tunnels import main
	try:
		main(sys.argv[1])
	except ValueError as e:
		sys.stderr.write(u'Configuration error: ' + str(e) + u'\n')
		sys.exit(2)
