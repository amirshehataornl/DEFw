from defw_remote import BaseRemote

class Launcher(BaseRemote):
	def __init__(self, si):
		super().__init__(service_info = si)

	# returns only after the process has been launched
	def launch(self, proc, path=''):
		pass

	def kill(self, pid):
		pass

	def terminate(self, pid):
		pass

	def status(self, pid):
		pass

	def shutdown(self):
		pass

	def test(self):
		pass
