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

		qiskitaer_executable = shutil.which(info['qfw_backend'])
		gpuwrapper = shutil.which("gpuwrapper.sh")

		if not qiskitaer_executable or not gpuwrapper:
			raise DEFwExecutionError("Couldn't find qiskitaer_executable or gpuwrapper. Check paths")

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

		backend_chosen = ""
		if "qpm_options" in info:
			qpm_options = info["qpm_options"]
			if "backend" in qpm_options:
				if qpm_options["backend"] in ["automatic", "statevector", "density_matrix", "stabilizer", "matrix_product_state", "extended_stabilizer", "unitary", "superop", "tensor_network"]:
					backend_chosen = qpm_options["backend"]
				else:
					logging.debug("Incorrect backend specified. Using default statevector")
					backend_chosen = "statevector"
			else:
				backend_chosen = "statevector"

			if "device" in qpm_options:
				device = qpm_options["device"]
				if device in ["CPU", "GPU"]:
					device_chosen = device
				else:
					logging.debug("Incorrect device specified. Using default CPU")
					device_chosen = "CPU"
			else:
				device_chosen = "CPU"

		cmd = f'{exec_cmd} --dvm {dvm} -x LD_LIBRARY_PATH ' \
			  f'--mca btl ^tcp,ofi,vader,openib ' \
			  f'--mca pml ^ucx --mca mtl ofi --mca opal_common_ofi_provider_include '\
			  f'{info["provider"]} --map-by {info["mapping"]} --bind-to core '\
			  f'--np {info["np"]} --host {hosts} {gpuwrapper} '

		cmd += f'-v {qiskitaer_executable} -q {qasm_file} -b {backend_chosen} '

		if "num_shots" in info:
			cmd += f'-s {info["num_shots"]} '

		logging.debug(f"QiskitAer CMD - {cmd}")

		return cmd

	def test(self):
		return "****Testing the QiskitAer QRC****"
