from defw_agent_info import *
import logging, sys, os
import importlib, yaml, psutil
from defw_exception import DEFwError, DEFwExecutionError
from util.qpm.util_qrc import UTIL_QRC

sys.path.append(os.path.split(os.path.abspath(__file__))[0])

class QRC(UTIL_QRC):
	def __init__(self, start=True):
		super().__init__(start=start)

	def parse_result(self, out):
		logging.debug(f"parse_result called with output: {out}")
		try:
			out_str = out.decode("utf-8")
			if out_str == "":
				logging.error("Empty output received!")
				raise DEFwError({"Error": "Empty output!"})
			lines = out_str.split("\n")
			result_line = [line for line in lines if line.startswith("solution:")]
			if not result_line:
				logging.error("Could not find solution in output!")
				raise DEFwError({"Error": "Could not parse solution!"})
			sol_str = result_line[0].split("solution:")[-1].strip()
			logging.debug(f"Parsed solution: {sol_str}")
			return {"solution": sol_str}
		except Exception as e:
			logging.error(f"Error parsing result: {str(e)}")
			raise DEFwError({"Error": str(e)})

	def form_cmd(self, circ, qfile):
		import shutil
		info = circ.info

		qaoa_executable = shutil.which(info['qfw_backend'])
		if not qaoa_executable:
			raise DEFwExecutionError("Couldn't find qaoa_runner.qfw executable. Check paths.")

		if not os.path.exists(qfile):
			raise DEFwExecutionError(f"QUBO numpy file {qfile} does not exist.")

		sim_type = info.get("sim_type", "nwqsim")
		sub_backend = info.get("sub_backend", "AMDGPU")
		device = info.get("device", "GPU")
		run_mode = info.get("run_mode", "sync")
		reps = str(info.get("reps", 1))

		cmd = f"{qaoa_executable} {sim_type} {sub_backend} {device} {run_mode} {reps} {qfile}"

		logging.debug(f"QAOA Runner cmd - {cmd}")
		return cmd

	def test(self):
		return "****Testing the QAOA QPM QRC****"
