import sys, os, logging
from .svc_qrc import QRC
from util.qpm.util_qpm import UTIL_QPM

class QPM(UTIL_QPM):
	def __init__(self, start=True):
		super().__init__(QRC(start=start), start=start)

	def query(self):
		from . import SERVICE_NAME, SERVICE_DESC
		from api_qpm import QPMType
		info = self.query_helper(QPMType.QPM_TYPE_QAOA,
								 QPMType.QPM_TYPE_STATEVECTOR,
								 SERVICE_NAME, SERVICE_DESC)
		logging.debug(f"QAOA QFW {SERVICE_DESC}: {info}")
		return info

	def create_circuit(self, info):
		info['qfw_backend'] = 'qaoa_runner.qfw'
		return super().create_circuit(info)

	def test(self):
		return "****QAOA QPM Test Successful****"
