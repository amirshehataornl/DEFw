import sys, os, logging
from .svc_qrc import QRC
from util.qpm.util_qpm import UTIL_QPM

class QPM(UTIL_QPM):
	def __init__(self, start=True):
		super().__init__(QRC(start=start), start=start)

	def query(self):
		from . import SERVICE_NAME, SERVICE_DESC
		from api_qpm import QPMType, QPMCapability
		info = self.query_helper(QPMType.QPM_TYPE_QISKITAER | QPMType.QPM_TYPE_SIMULATOR,
								 QPMCapability.QPM_CAP_STATEVECTOR, # qiskit-aer does have statevector, but it also have stabilizer/clifford-T, tensor-networks etc.
								 SERVICE_NAME, SERVICE_DESC)
		logging.debug(f"Qiskit-Aer {SERVICE_DESC}: {info}")
		return info

	def create_circuit(self, info):
		info['qfw_backend'] = 'circuit_runner.qiskitaer'
		return super().create_circuit(info)

	def test(self):
		return "****Qiskit-Aer QPM Test Successful****"

