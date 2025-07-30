from defw_agent_info import *
import logging, sys, os
import importlib, yaml, psutil
from defw_exception import DEFwError, DEFwExecutionError
from util.qpm.util_qrc import UTIL_QRC
from time import perf_counter

sys.path.append(os.path.split(os.path.abspath(__file__))[0])

class QRC(UTIL_QRC):
	def __init__(self, start=True):
		super().__init__(start=start)

	def parse_result(self, out):
		before = perf_counter()
		try:
			logging.debug(f"parse_result out = {out}")
			out_str = out.decode("utf-8")
			logging.debug(f"parse_result out_str = {out_str}")
			if out_str == "":
				raise DEFwError({"Error": "Empty output!"})
			try:
				counts = {}
				for line in out_str.split('\n'):
					if "counts" in line:
						c = line.split("=")[1]
						logging.debug(f"parse_result c = {c}")
						counts = yaml.safe_load(c)
						after = perf_counter()
						logging.debug(f"parse_result took {after - before} seconds")
						return counts
			except Exception as e:
				raise DEFwError({"Error": f"Failed to parse output: {e}"})
		except Exception as e:
			raise DEFwError({"Error": f"Failed to decode output: {e}"})

	def form_cmd(self, circ, qasm_file):
		import shutil
		info = circ.info

		ionq_executable = shutil.which(info['qfw_backend'])
		gpuwrapper = shutil.which("gpuwrapper.sh")

		if not ionq_executable or not gpuwrapper:
			raise DEFwExecutionError("Couldn't find ionq_executable or gpuwrapper. Check paths")

		if not os.path.exists(info["qfw_dvm_uri_path"].split('file:')[1]):
			raise DEFwExecutionError(f"dvm-uri {info['qfw_dvm_uri_path']} doesn't exist")

		hosts = list(info["hosts"].keys())[0] + ":1"

		try:
			dvm = info["qfw_dvm_uri_path"]
		except:
			dvm = "search"

		exec_cmd = shutil.which(info["exec"])

		logging.debug(f"ionq_executable: {ionq_executable}, gpuwrapper: {gpuwrapper}, dvm: {dvm}, exec_cmd: {exec_cmd}")

		backend_chosen = ""
		if "qpm_options" in info:
			qpm_options = info["qpm_options"]
			if "backend" in qpm_options:
				if qpm_options["backend"] in ["simulator", "qpu"]:
					backend_chosen = qpm_options["backend"]
				else:
					logging.debug("Incorrect backend specified. Using default simulator")
					backend_chosen = "simulator"
			else:
				backend_chosen = "simulator"

		cmd = f'{ionq_executable} -q {qasm_file} -b {backend_chosen} '

		if "num_shots" in info:
			cmd += f'-s {info["num_shots"]} '

		logging.debug(f"IONQ CMD - {cmd}")

		return cmd

	def test(self):
		return "****Testing the IONQ QRC****"
