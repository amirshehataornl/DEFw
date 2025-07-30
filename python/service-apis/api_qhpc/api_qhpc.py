from defw_remote import BaseRemote

class Qhpc(BaseRemote):
	def __init__(self, ep):
		super().__init__(target=ep)

	def create_circuit(self, qasm, nbits=1):
		pass

	def delete_circuit(self):
		pass

	def sync_run(self, cid):
		pass

	def async_run(self, cid):
		pass

	def status(self):
		pass

	def read_cq(self, cid=None):
		pass

	def peek_cq(self, cid=None):
		pass


