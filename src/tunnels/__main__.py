def _interactiveMode():
	import sys
	from .tunnels import main
	main(sys.argv[1:])

def _daemonMode():
	import sys
	from .tunnels import init
	from .tunnels import run
	from .tunnels import terminate as tunnelsTerminate
	from .logger import mkInfoFunction, flushLog
	import daemon
	daemon.daemon.close_all_open_files = lambda *args, **kwargs: None # Work around https://github.com/dlitz/pycrypto/pull/34
	info = mkInfoFunction('Daemon')
	class DaemonContext(daemon.DaemonContext):
		def terminate(self, *args, **kwargs):
			tunnelsTerminate()
			daemon.DaemonContext.terminate(self, *args, **kwargs)
	context = DaemonContext()
	context.stdout = sys.stdout
	context.stderr = sys.stderr
	context.detach_process = True
	try:
		import daemon.pidfile as pidfile
	except ImportError:
		import daemon.pidlockfile as pidfile
	pidFile = u'/var/run/tunnels.pid'
	if u'--pid' in sys.argv:
		pidFile = sys.argv[sys.argv.index(u'--pid') + 1]
		sys.argv = sys.argv[:sys.argv.index(u'--pid')] + sys.argv[sys.argv.index(u'--pid') + 2:]
	context.pidfile = pidfile.TimeoutPIDLockFile(pidFile, acquire_timeout=30)
	if len(sys.argv) < 2:
		sys.argv.append(u'/etc/tunnels.d')
	info('Initializing.')
	init(sys.argv[1:])
	info('Initialization done, entering daemon mode.')
	flushLog()
	with context:
		run()

if __name__ == u'__main__':
	import sys
	if len(sys.argv) < 2:
		sys.stderr.write(u'Interactive usage: tunnels   <conf1> [<conf2> [<conf3> [...]]]\n')
		sys.stderr.write(u'     Daemon usage: tunnelsd [<conf1> [<conf2> [<conf3> [...]]]]\n')
		sys.stderr.write(u'                   If no configuration is provided in daemon mode,\n')
		sys.stderr.write(u'                   it will use /etc/tunnels.d\n')
		sys.exit(1)
	try:
		if u'--daemon' in sys.argv:
			sys.argv.remove(u'--daemon')
			_daemonMode()
		else:
			_interactiveMode()
	except ValueError as e:
		sys.stderr.write(u'Configuration error: ' + str(e) + u'\n')
		sys.exit(2)
