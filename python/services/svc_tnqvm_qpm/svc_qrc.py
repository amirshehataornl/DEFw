from defw_agent_info import *
from defw_util import prformat, fg, bg
from defw import me
import logging, uuid, time, queue, threading, sys, os, io, contextlib
import importlib, yaml, copy, subprocess, traceback
from defw_exception import DEFwError, DEFwExists, DEFwExecutionError, DEFwInProgress, DEFwOutOfResources
import svc_launcher, cdefw_global

sys.path.append(os.path.split(os.path.abspath(__file__))[0])
import qpm_common as common

def dump_tmp_dir():
	try:
		for root, dirs, files in os.walk('/tmp'):
			logger.info(f"Directory: {root}")
			for file in files:
				logger.info(f"  File: {os.path.join(root, file)}")
	except:
		pass

@contextlib.contextmanager
def suppress_prints():
	# Save the original stdout
	original_stdout = sys.stdout
	original_stderr = sys.stderr
	sys.stdout = io.StringIO()
	sys.stderr = io.StringIO()

	yield

	sys.stdout = original_stdout
	sys.stderr = original_stderr

class QRC:
	# number of worker threads started
	MAX_NUM_WORKERS = 8
	# max work queue size
	MAX_NUM_WORKER_TASKS = 256
	THREAD_STATE_FREE = 0
	THREAD_STATE_BUSY = 1

	def __init__(self, start=True):
		self.__load = 0
		self.circuit_results_lock = threading.Lock()
		self.worker_pool_lock = threading.Lock()
		self.circuit_results = []
		self.module_util = None
		self.colocated_dvm = False
		self.is_colocated_dvm()
		self.worker_pool = {}
		if start:
			for x in range(0, QRC.MAX_NUM_WORKERS):
				with self.worker_pool_lock:
					runner = threading.Thread(target=self.runner, args=(x,))
					logging.debug(f"inserting {x} in the worker pool")
					self.worker_pool[x] = {'thread': runner,
										   'active_tasks': [],
										   'queue': queue.Queue(),
										   'state': QRC.THREAD_STATE_FREE}
					runner.daemon = True
					runner.start()

	def __del__(self):
		common.qpm_shutdown = True
		with self.worker_pool_lock:
			for k, v in self.worker_pool.items():
				v['queue'].put(None)

	def is_colocated_dvm(self):
		import psutil
		pids = psutil.pids()
		for pid in pids:
			try:
				proc = psutil.Process(pid)
				if "prte" == proc.name():
					logging.debug(f"Found prte: {proc}")
					self.colocated_dvm = True
					return
			except:
				continue

	def check_active_tasks(self, wid):
		complete = []
		for task_info in self.worker_pool[wid]['active_tasks']:
			try:
				stdout, stderr, rc = task_info['launcher'].status(task_info['pid'])
			except DEFwInProgress:
				logging.debug(f"{task_info} still in progress")
				continue
			except Exception as e:
				raise e
			logging.debug(f"{task_info} completed")
			complete.append(task_info)
			circ = task_info['circ']
			cid = circ.get_cid()
			qasm_file = task_info['qasm_file']
			if not rc:
				logging.debug(f"Circuit {cid} successful")
				try:
					output_file = qasm_file+".result.r0"
					with open(output_file, 'r') as f:
						output = f.read()
						output = yaml.safe_load(output)
					os.remove(output_file)
					circ.set_exec_done()
				except Exception as e:
					output = "{result: missing, exception: "+ f"{e}" + "}"
					circ.set_fail()
			else:
				stdout = stdout.decode('utf-8')
				stderr = stderr.decode('utf-8')
				res = stdout + '\n' + stderr
				output = "{result: "+ f"{res}" + "}"
				circ.set_fail()

			try:
				os.remove(qasm_file)
			except:
				pass

			r = {'cid': cid, 'result': output, 'rc': rc}
			logging.debug(f"Circuit result = {r}")
			with self.circuit_results_lock:
				self.circuit_results.append(r)

		for task_info in complete:
			self.worker_pool[wid]['active_tasks'].remove(task_info)

	def runner(self, my_id):
		# get the next available entry on the queue
		# if one is available run it
		# check on currently running tasks to see if any of them complete
		# Add completed tasks to the results dictionary
		with self.worker_pool_lock:
			if my_id not in self.worker_pool:
				logging.debug(f"{my_id}: A worker thread is not part of the pool")
			my_queue = self.worker_pool[my_id]['queue']
		logging.debug(f"starting QRC main loop for {my_id}")
		while not common.qpm_shutdown:
			empty = False
			try:
				circ = my_queue.get(timeout=1)
				if circ == None:
					common.qpm_shutdown = True
					continue
			except queue.Empty:
				empty = True

			self.check_active_tasks(my_id)

			if not empty:
				result = None
				pid = -1
				try:
					task_info = self.run_circuit_async(circ)
				except Exception as e:
					result = e
					rc = -1
					pass
				if my_queue.qsize() < QRC.MAX_NUM_WORKER_TASKS:
					with self.worker_pool_lock:
						self.worker_pool[my_id]['state'] = QRC.THREAD_STATE_FREE
				if result:
					r = {'cid': circ.get_cid(), 'result': result, 'rc': rc}
					logging.debug(f"Problem with circuit {cid} appending result {r}")
					with self.circuit_results_lock:
						self.circuit_results.append(r)
						logging.debug(f"{len(self.circuit_results)} pending results")
				else:
					self.worker_pool[my_id]['active_tasks'].append(task_info)

	def read_cq(self, cid=None):
		if cid:
			with self.circuit_results_lock:
				logging.debug(f"read_cq for {cid}: {len(self.circuit_results)}")
				i = 0
				for e in self.circuit_results:
					if cid == e['cid']:
						r = self.circuit.pop(i)
						return r
					i += 1
		else:
			with self.circuit_results_lock:
				logging.debug(f"read_cq for top: {len(self.circuit_results)}")
				if len(self.circuit_results) > 0:
					r = self.circuit_results.pop(0)
					return r
		return None

	def peak_cq(self, cid=None):
		if cid:
			with self.circuit_results_lock:
				logging.debug(f"pead_cq for {cid}: {len(self.circuit_results)}")
				i = 0
				for e in self.circuit_results:
					if cid == e['cid']:
						return e
					i += 1
		else:
			with self.circuit_results_lock:
				logging.debug(f"read_cq for top: {len(self.circuit_results)}")
				if len(self.circuit_results) > 0:
					return self.circuit_results[0]
		return None

	def import_module_util(self):
		try:
			mod_path = os.path.join(os.environ['MODULESHOME'], "init",
					"env_modules_python.py")
			mod_name = "env_modules_python"
			spec = importlib.util.spec_from_file_location(mod_name,
					mod_path)
			self.module_util = importlib.util.module_from_spec(spec)
			spec.loader.exec_module(self.module_util)
		except:
			raise DEFwError("module utility not available on this system")

	def load_modules(self, modules):
		if not self.module_util:
			self.import_module_util()

		for use in modules['use']:
			self.module_util.module("use", use)
		for mod in modules['mods']:
			self.module_util.module("load", mod)

		with suppress_prints():
			mod_list = self.module_util.module("list")
		logging.debug(f"Module loaded\n{mod_list[1]}")

	def form_cmd(self, circ, qasm_file):
		import shutil

		info = circ.info

		logging.debug(f"Circuit Info = {info}")

		if 'qpm_options' not in info or 'compiler' not in info["qpm_options"]:
			compiler = 'staq'
		else:
			compiler = info["qpm_options"]["compiler"]

		circuit_runner = shutil.which(info['qfw_backend'])
		gpuwrapper = shutil.which("gpuwrapper.sh")

		if not circuit_runner or not gpuwrapper:
			logging.debug(f"{os.environ['PATH']}")
			logging.debug(f"{os.environ['LD_LIBRARY_PATH']}")
			raise DEFwExecutionError("Couldn't find circuit_runner or gpuwrapper. Check paths")

		if not os.path.exists(info["qfw_dvm_uri_path"].split('file:')[1]):
			raise DEFwExecutionError(f"dvm-uri {info['qfw_dvm_uri_path']} doesn't exist")

		hosts = ''
		for k, v in info["hosts"].items():
			if hosts:
				hosts += ','
			hosts += f"{k}:{v}"

		dump_tmp_dir()
		if self.colocated_dvm:
			dvm = info["qfw_dvm_uri_path"]
		else:
			dvm = "search"

		exec_cmd = shutil.which(info["exec"])
		#exec_cmd = info["exec"]

#		cmd = f'{circuit_runner} ' \
#			  f'-q {qasm_file} -b {info["num_qubits"]} -s {info["num_shots"]} ' \
#			  f'-c {compiler} -v'

		cmd = f'{exec_cmd} --dvm {dvm} -x LD_LIBRARY_PATH ' \
			  f'--mca btl ^tcp,ofi,vader,openib ' \
			  f'--mca pml ^ucx --mca mtl ofi --mca opal_common_ofi_provider_include '\
			  f'{info["provider"]} --map-by {info["mapping"]} --bind-to core '\
			  f'--np {info["np"]} --host {hosts} {gpuwrapper} -v {circuit_runner} ' \
			  f'-q {qasm_file} -b {info["num_qubits"]} -s {info["num_shots"]} ' \
			  f'-c {compiler}'

#		cmd = f'{exec_cmd} --dvm {dvm} -x LD_LIBRARY_PATH ' \
#			  f'--report-bindings --display-map --display-allocation --np 1 /ccs/home/shehataa/mysleep.sh '

#		cmd = f'{exec_cmd} --dvm {dvm} -x LD_LIBRARY_PATH ' \
#			  f'--mca btl ^tcp,ofi,vader,openib --pmixmca pmix_client_spawn_verbose 100 ' \
#			  f'--mca pml ^ucx --mca mtl ofi --mca opal_common_ofi_provider_include '\
#			  f'{info["provider"]} --map-by {info["mapping"]} --bind-to core  '\
#			  f'--np {info["np"]} --host {hosts} /ccs/home/shehataa/mysleep.sh '

#		cmd = '/ccs/home/shehataa/mysleep.sh'

#			  f'-c {compiler} 2>&1 | tee {output_file}'
#--display mapping,bindings
# --prtemca ras_base_verbose 50
		return cmd

	def run_circuit_async(self, circ):
		# check that we can run on CXI
		if "SLINGSHOT_VNIS" in os.environ:
			logging.debug(f"Found SLINGSHOT_VNIS: {os.environ['SLINGSHOT_VNIS']}")
		else:
			logging.critical(f"Didn't find SLINGSHOT_VNIS")

		cid = circ.get_cid()

		#self.load_modules(circ.info["modules"])

		tmp_dir = cdefw_global.get_defw_tmp_dir()

		qasm_c = circ.info["qasm"]
		qasm_file = os.path.join(tmp_dir, str(cid)+".qasm")
		logging.debug(f"Writing circuit file to {qasm_file}")
		with open(qasm_file, 'w') as f:
			f.write(qasm_c)

		try:
			circ.set_running()
			launcher = svc_launcher.Launcher()
			logging.debug(f"Running Circuit --\n{qasm_c}")
			cmd = self.form_cmd(circ, qasm_file)
		except Exception as e:
			os.remove(qasm_file)
			logging.critical(f"Got Exception: {e}")
			raise e

		task_info = {}
		pid = -1
		try:
			#env = {'FI_LOG_LEVEL': 'info'}
			#output, error, rc = launcher.launch(cmd, env=env, wait=True)
			pid = launcher.launch(cmd)
			logging.debug(f"Running -- {cmd} -- with pid {pid}")
		except Exception as e:
			os.remove(qasm_file)
			logging.critical(f"Failed to launch {cmd}")
			raise e

		task_info['circ'] = circ
		task_info['qasm_file'] = qasm_file
		task_info['launcher'] = launcher
		task_info['pid'] = pid

		return task_info

#	def run_cmd(self, cmd):
#		proc = Process(cmd, None, "")
#		pid = proc.launch()
#		stdout, stderr, rc = proc.get_result()
#		proc.terminate()
#		#rc = proc.run()
#		return stdout, stderr, rc
#		#return "out", "err", rc

	def run_circuit(self, circ):
		# check that we can run on CXI
		if "SLINGSHOT_VNIS" in os.environ:
			logging.debug(f"Found SLINGSHOT_VNIS: {os.environ['SLINGSHOT_VNIS']}")
		else:
			logging.critical(f"Didn't find SLINGSHOT_VNIS")

		cid = circ.get_cid()

		#self.load_modules(circ.info["modules"])

		tmp_dir = cdefw_global.get_defw_tmp_dir()

		qasm_c = circ.info["qasm"]
		qasm_file = os.path.join(tmp_dir, str(cid)+".qasm")
		logging.debug(f"Writing circuit file to {qasm_file}")
		with open(qasm_file, 'w') as f:
			f.write(qasm_c)

		circ.set_running()
		launcher = svc_launcher.Launcher()
		logging.debug(f"Running Circuit --\n{qasm_c}")
		cmd = self.form_cmd(circ, qasm_file)
		logging.debug(f"Running -- {cmd}")

		try:
			#env = {'FI_LOG_LEVEL': 'info'}
			#output, error, rc = launcher.launch(cmd, env=env, wait=True)
			output, error, rc = launcher.launch(cmd, wait=True)
			logging.debug(f"Completed -- {cmd} -- returned {rc} -- {output} -- {error}")
		except Exception as e:
			os.remove(qasm_file)
			logging.critical(f"Failed to launch {cmd}")
			logging.critical(f"encountered exception {e}")
			launcher.shutdown()
			raise e

		launcher.shutdown()
		logging.debug(f"Removing {qasm_file}")
		os.remove(qasm_file)

		if not rc:
			logging.debug(f"Circuit {cid} successful")
			try:
				output_file = qasm_file+".result.r0"
				with open(output_file, 'r') as f:
					output = f.read()
					output = yaml.safe_load(output)
				os.remove(output_file)
				circ.set_exec_done()
			except Exception as e:
				output = "{result: missing, exception: "+ f"{e}"
			return 0, output
		circ.set_fail()
		self.is_colocated_dvm()
		error_str = f"Circuit failed with {rc}:{output.decode('utf8')}:" \
				f"{error.decode('utf-8')}:dvm {self.colocated_dvm}"
		logging.debug(error_str)
		raise DEFwExecutionError(error_str)

	def sync_run(self, circ):
		return self.run_circuit(circ)

	def async_run(self, circ):
		cid = circ.get_cid()
		with self.worker_pool_lock:
			for k, v in self.worker_pool.items():
				if v['state'] == QRC.THREAD_STATE_FREE and \
				   v['queue'].qsize() < QRC.MAX_NUM_WORKER_TASKS:
					v['queue'].put(circ)
					if v['queue'].qsize() >= QRC.MAX_NUM_WORKER_TASKS:
						v['state'] = QRC.THREAD_STATE_BUSY
					return cid
				elif v['state'] == QRC.THREAD_STATE_BUSY:
					raise DEFwOutOfResources(f"No more resource to run {cid}")

	def shutdown(self):
		common.qpm_shutdown = True

	def test(self):
		return "****Testing the QRC****"
