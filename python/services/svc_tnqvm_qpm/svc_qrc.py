from defw_agent_info import *
from defw_util import prformat, fg, bg
from defw import me
import logging, uuid, time, queue, threading, sys, os, io, contextlib
import importlib, yaml, copy, subprocess, traceback
from defw_exception import DEFwExecutionError, DEFwInProgress
from defw_exception import DEFwError, DEFwExecutionError
from util.qpm.util_qrc import UTIL_QRC
import json

sys.path.append(os.path.split(os.path.abspath(__file__))[0])

class QRC(UTIL_QRC):
	def __init__(self, start=True):
		super().__init__(start=start)

	# def parse_result(self, out):
	# 	logging.debug(f"parse_result called with output: {out}")
	# 	try:
	# 		out_str = out.decode("utf-8") if isinstance(out, bytes) else str(out)
	# 		if out_str.strip() == "":
	# 			raise DEFwError({"Error": "Empty output!"})

	# 		json_start = out_str.find('{')
	# 		json_end = out_str.rfind('}') + 1
	# 		json_str = out_str[json_start:json_end]

	# 		data = json.loads(json_str)

	# 		counts = data.get("AcceleratorBuffer", {}).get("Measurements", None)
	# 		if counts is None:
	# 			raise DEFwError({"Error": "Measurements not found in output!"})			
	# 		return counts

	# 	except Exception as e:
	# 		raise DEFwError({"Error": str(e)})

	def parse_result(self, out):
		logging.debug(f"parse_result called with output: {out}")

		try:
			if isinstance(out, bytes):
				out_str = out.decode("utf-8")
			else:
				out_str = str(out)

			measurements_start = out_str.find('"Measurements": {')
			if measurements_start == -1:
				raise DEFwError({"Error": "Measurements section not found!"})

			brace_count = 0
			i = measurements_start
			in_measurements = False
			measurements_str = ""

			while i < len(out_str):
				c = out_str[i]
				if c == '{':
					brace_count += 1
					in_measurements = True
				if c == '}':
					brace_count -= 1

				if in_measurements:
					measurements_str += c

				if in_measurements and brace_count == 0:
					break

				i += 1

			if not measurements_str:
				raise DEFwError({"Error": "Failed to extract measurements content!"})

			counts = {}
			lines = measurements_str.splitlines()
			for line in lines:
				line = line.strip().rstrip(',')
				if line.startswith('"') and ':' in line:
					key_part, value_part = line.split(':', 1)
					bitstring = key_part.strip().strip('"')
					count_str = value_part.strip().replace(',', '').replace('"', '')
					try:
						count = int(count_str)
						counts[bitstring] = count
					except ValueError:
						continue

			if not counts:
				raise DEFwError({"Error": "No measurements parsed!"})
			
			logging.debug(f"Parsed counts: {counts}")

			return counts

		except Exception as e:
			raise DEFwError({"Error": str(e)})


	def form_cmd(self, circ, qasm_file):
		import shutil

		info = circ.info

		logging.debug(f"Circuit Info = {info}")

		if 'qpm_options' not in info or 'compiler' not in info["qpm_options"]:
			compiler = 'staq'
		else:
			compiler = info["qpm_options"]["compiler"]

		if 'qpm_options' not in info or 'backend' not in info["qpm_options"]:
			visitor = 'exatn-mps'
		else:
			visitor = info["qpm_options"]["backend"]

		if 'qpm_options' not in info or 'device' not in info["qpm_options"]:
			device = 'CPU'
		else:
			device = info["qpm_options"]["device"]

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

		# common across QPMs
		cmd = f'{exec_cmd} --dvm {dvm} -x LD_LIBRARY_PATH ' \
			  f'--mca btl ^tcp,ofi,vader,openib ' \
			  f'--mca pml ^ucx --mca mtl ofi --mca opal_common_ofi_provider_include '\
			  f'{info["provider"]} --map-by {info["mapping"]} --bind-to core '\
			  f'--np {info["np"]} --host {hosts} {gpuwrapper} '

		cmd += f'-v {circuit_runner} ' \
			f'--qasm {qasm_file} --qubits {info["num_qubits"]} --shots {info["num_shots"]} ' \
			f'--compiler {compiler} --visitor {visitor} '

		logging.debug(f"TNQVM cmd - {cmd}")

		return cmd

	def test(self):
		return "****Testing the TNQVM QRC****"
