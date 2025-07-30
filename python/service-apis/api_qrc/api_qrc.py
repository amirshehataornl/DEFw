from defw_remote import BaseRemote

class QRC(BaseRemote):
	def __init__(self, si):
		super().__init__(service_info = si)

	def sync_run(self, cid, info):
		pass

	def async_run(self, cid, info):
		pass

	def read_cq(self, cid=None):
		pass

	def test(self):
		pass
