from defw_agent_info import *
from defw_util import prformat, fg, bg
from defw import me
import logging, uuid, time, queue, threading, logging
from defw_exception import DEFwError

CID_COUNTER = 0
QCR_VERBOSE = 1

class CircuitStates:
	UNDEF = 0
	READY = 1
	RUNNING = 2
	DONE = 3

class Circuit:
	__state = 0    # Circuit state (enum of valid states)
	__spec = None  # Circuit specification (qasm string)
	__cid = -1     # Circuit id (uniq id)
	qasm = None
	qpu = None
	qubitReg = None
	compiler = None
	compiled_circuit = None
	nbits = -1

	def __init__(self):
		self.__state = CircuitStates.UNDEF
		self.__spec  = None
		self.qpu = None
		self.qubitReg = None
		self.compiler = None
		self.compiled_circuit = None
		self.nbits = 0

	def getState(self):
		return self.__state

	def setState(self, state):
		# State is monotonically increasing
		if self.__state > state:
			return False
		self.__state = state
		return True

	def set_ready(self):
		return self.setState(CircuitStates.READY)

	def set_running(self):
		return self.setState(CircuitStates.RUNNING)

	def set_done(self):
		return self.setState(CircuitStates.DONE)

	def getCirSpec(self):
		return self.__circuit_spec

	def setCirSpec(self, spec):
		self.__circuit_spec = spec
		self.setReady()
		self.__cid = CID_COUNTER
		CID_COUNTER += 1
		return True

	def status(self):
		if self.__state == CircuitStates.READY:
			return 'READY'
		if self.__state == CircuitStates.RUNNING:
			return 'RUNNING'
		if self.__state == CircuitStates.DONE:
			return 'DONE'

		return 'BUG'

class Qhpc:
	def __init__(self, start=True):
		self.circuits = {}
		self.runner_queue = queue.Queue()
		self.circuit_results = []
		if start:
			self.runner = threading.Thread(target=self.runner, args=())
			self.runner.start()
		self.runner_shutdown = False

	def __del__(self):
		self.runner_shutdown = True
		self.runner_queue.put(-1)

	def runner(self):
		logging.debug("starting Qhpc main loop")
		while not self.runner_shutdown:
			try:
				cid = self.runner_queue.get(timeout=1)
				if cid == -1:
					self.runner_shutdown = True
					continue
			except queue.Empty:
				continue
			result = self.run_circuit(cid)
			r = {'cid': cid, 'result': result}
			self.circuit_results.append(r)

	def read_cq(self, cid=None):
		if cid:
			i = 0
			for e in self.circuit_results:
				if cid == e['cid']:
					r = self.circuit.pop(i)
					return r
				i += 1
		else:
			if len(self.circuit_results) > 0:
				r = self.circuit_results.pop(0)
				return r
		return None

	def peek_cq(self, cid=None):
		if cid:
			for e in self.circuit_results:
				if cid == e['cid']:
					return e
		else:
			if len(self.circuit_results) > 0:
				return self.circuit_results[0]
		return None

	def status(self):
		logging.debug("Querying Status of Circuits")
		r = {}
		for k, v in self.circuits.items():
			r[k] = v.status()
		return r

	def query(self):
		from . import svc_info
		cap = Capability("QuantumSim", "Quantum HPC Simulator", 1)
		svc = ServiceDescr(svc_info['name'], svc_info['description'], [cap], 1)
		info = DEFwServiceInfo(self.__class__.__name__,
						  self.__class__.__module__, [svc])
		return info

	def reserve(self, svc, client_ep, *args, **kwargs):
		logging.debug(f"{client_ep} reserved the {svc}")

	def release(self, services):
		self.runner_shutdown = True

	def __find_circuit(self, cid):
		if cid in self.circuits:
			return self.circuits[cid]
		return None

	def create_circuit(self, qasm, nbits=1, endpoint=None):
		import xacc
		cid = str(uuid.uuid4())
		self.circuits[cid] = Circuit()
		self.circuits[cid].qasm = qasm
		circuit = self.circuits[cid]

		logging.debug(f"Start circuit compile at: {time.monotonic_ns()}")
		circuit.qpu = xacc.getAccelerator("tnqvm:exatn-mps", {"shots":2})
		compiler = xacc.getCompiler('staq')
		circuit.compiled_circuit = compiler.compile(circuit.qasm,
													circuit.qpu)
		circuit.nbits = nbits
		logging.debug(f"Finished circuit compile at: {time.monotonic_ns()}")
		circuit.set_ready()

		return cid

	def delete_circuit(self, cid):
		try:
			del self.circuits[cid]
		except:
			pass

	def run_circuit(self, cid):
		"""
		 Input: None
		 Return: return: Event object
		 Description: Run a circuit synchronously. Return the event object.
		"""
		# sanity check
		import xacc
		circuit = self.__find_circuit(cid)
		if not circuit:
			raise DEFwError(f"Got circuit {cid} does not exist in database")

		circuit.set_running()

		if QCR_VERBOSE:
			logging.debug(f"  DBG: qalloc {circuit.nbits} nbits")
		qubitReg = xacc.qalloc(circuit.nbits)

		if QCR_VERBOSE:
			logging.debug(f"  DBG: compiled circuit {circuit.compiled_circuit} here")
		c = circuit.compiled_circuit

		if QCR_VERBOSE:
			logging.debug(f"  DBG: execute circuit now")
		logging.debug(f"Start circuit execution at: {time.monotonic_ns()}")
		circuit.qpu.executeWithoutGIL(qubitReg, c.getComposites()[0])
		logging.debug(f"Finish circuit execution at: {time.monotonic_ns()}")

		if QCR_VERBOSE:
			logging.debug(qubitReg)

		r1 = qubitReg.getInformation()
		r2 = qubitReg.getMeasurements()

		if QCR_VERBOSE:
			logging.debug("DBG: ==information==")
			logging.debug(r1)

			logging.debug("DBG: ==measurements==")
			logging.debug(r2)

		results = { "Info": r1, "Measurements": r2}

		circuit.set_done()

		return results

	def sync_run(self, cid):
		return self.run_circuit(cid)

	def async_run(self, cid):
		return self.runner_queue.put(cid)

