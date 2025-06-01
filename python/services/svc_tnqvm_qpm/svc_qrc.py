from defw_agent_info import *
from defw_util import prformat, fg, bg
from defw import me
import logging, uuid, time, queue, threading, sys, os, io, contextlib
import importlib, yaml, copy, subprocess, traceback
from defw_exception import DEFwExecutionError, DEFwInProgress
from util.qpm.util_qrc import UTIL_QRC

sys.path.append(os.path.split(os.path.abspath(__file__))[0])

class QRC(UTIL_QRC):
	def __init__(self, start=True):
		super().__init__(start=start)

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

			r = {'cid': cid,
				 'result': output,
				 'rc': rc,
				 'launch_time': circ.launch_time,
				 'creation_time': circ.creation_time,
				 'exec_time': circ.exec_time,
				 'completion_time': circ.completion_time,
				 'resources_consumed_time': circ.resources_consumed_time,
				 'cq_enqueue_time': time.time(),
				 'cq_dequeue_time': -1 }
			with self.circuit_results_lock:
				self.circuit_results.append(r)

		for task_info in complete:
			self.worker_pool[wid]['active_tasks'].remove(task_info)

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

		try:
			dvm = info["qfw_dvm_uri_path"]
		except:
			dvm = "search"

		exec_cmd = shutil.which(info["exec"])

		cmd = f'{exec_cmd} --dvm {dvm} -x LD_LIBRARY_PATH ' \
			  f'--mca btl ^tcp,ofi,vader,openib ' \
			  f'--mca pml ^ucx --mca mtl ofi --mca opal_common_ofi_provider_include '\
			  f'{info["provider"]} --map-by {info["mapping"]} --bind-to core '\
			  f'--np {info["np"]} --host {hosts} {gpuwrapper} -v {circuit_runner} ' \
			  f'-q {qasm_file} -b {info["num_qubits"]} -s {info["num_shots"]} ' \
			  f'-c {compiler}'

		return cmd

	def test(self):
		return "****Testing the TNQVM QRC****"
