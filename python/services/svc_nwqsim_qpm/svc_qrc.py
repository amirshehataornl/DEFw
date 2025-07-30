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
				return {"Error": "Empty output!"}
			lines = out_str.split("\n")
			logging.debug(f"NWQSIM: Output lines: {lines}")
			catch = -1
			for i, each_line in enumerate(lines):
				if "===============  Measurement" in each_line:
					catch = i
			if catch == -1:
				logging.error("Could not find measurement results in output!")
				raise DEFwError({"Error": "Could not parse result!"})
				return {"Error": "Could not parse result!"}
			results = lines[catch+1:-1]
			counts = {}
			for each_res_line in results:
				k,v = each_res_line.split(":")
				k = k.strip('" ').strip()
				v = int(v)
				counts[k] = v
			logging.debug(f"NWQSIM: Parsed counts: {counts}")
			return counts
		except Exception as e:
			logging.error(f"Error parsing result: {str(e)}")
			raise DEFwError({"Error": str(e)})
			return {"Error": str(e)}

	def form_cmd(self, circ, qasm_file):
		import shutil
		info = circ.info

		nwqsim_executable = shutil.which(info['qfw_backend'])
		gpuwrapper = shutil.which("gpuwrapper.sh")

		if not nwqsim_executable or not gpuwrapper:
			raise DEFwExecutionError("Couldn't find nwqsim_executable or gpuwrapper. Check paths")

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

		# ------------------------------------------------------------------------------------ #
		# Usage: program [OPTIONS] new
		# Available options:
		# -a, --all_tests                   Run all available testing benchmarks
		# -b, --backend        <BACKEND>    Specify the simulation backend
		# 	--backend_list                Print the list of available simulation backends
		# 	--basis                       Run the test benchmark using basis gates
		# 	--device         <FILE_PATH>  Specify the device noise profile
		# 	--disable_fusion              Disable gate fusion
		# 	--dump_file      <FILE_PATH>  Path to dump the binary statevector/density matrix result
		# -f, --fidelity                    Run both DM-Sim and SV-Sim and report state fidelity
		# -h, --help                        Print this help message
		# 	--hw_avx512                   Enable the use of AVX512
		# 	--hw_matrixcore               Enable the use of MatrixCore
		# 	--hw_tensorcore               Enable the use of Tensor Cores
		# 	--hw_threads     <INT>        Specify the number of OMP threads
		# 	--init_file      <FILE_PATH>  Path to the initial statevector/density matrix file
		# 	--init_format    <FILE_PATH>  Specify the format of the initial state
		# -j, --json_file      <FILE_PATH>  Execute simulation with the given JSON file (Qiskit Qobj)
		# 	--json_string    <STR>        Execute simulation with the provided JSON string (Qiskit Qobj)
		# 	--layout         <FILE_PATH>  Path to JSON mapping logical qubits to physical qubits
		# 	--layout_str     <STR>        String format mapping logical qubits to physical qubits
		# 	--metrics                     Print the metrics of the executed circuit
		# -q, --qasm_file      <FILE_PATH>  Execute simulation with the given QASM file
		# 	--qasm_string    <STR>        Execute simulation with the provided QASM string
		# 	--random_seed    <INT>        Set the random seed for the simulation
		# -s, --shots          <SHOTS>      Specify the number of shots
		# 	--sim            <METHOD>     Specify the simulation method
		# -t, --test           <INT>        Run testing benchmarks for the specified index
		# -v, --verbose                     Enable verbose simulation trace
		# ------------------------------------------------------------------------------------ #

		# ------------------------------------------------------------------------------------ #
		# old:
		# Usage: ./nwq_qasm [options]

		# Option              Description
		# -q                  Executes a simulation with the given QASM file.
		# -qs                 Executes a simulation with the given QASM string.
		# -j                  Executes a simulation with the given json file with Qiskit Experiment Qobj.
		# -js                 Executes a simulation with the given json string.
		# -t <index>          Runs the testing benchmarks for the specific index provided.
		# -a                  Runs all testing benchmarks.
		# -backend_list       Lists all the available backends.
		# -metrics            Print the metrics of the circuit.
		# -backend <name>     Sets the backend for your program to the specified one (default: CPU). The backend name string is case-insensitive.
		# -shots <value>      Configures the total number of shots (default: 1024).
		# -sim <method>       Select the simulation method: sv (state vector, default), dm (density matrix). (default: sv).
		# -basis              Run the transpiled benchmark circuits which only contain basis gates.
		# ------------------------------------------------------------------------------------ #

		backend_options = ["CPU", "OpenMP", "MPI", "AMDGPU", "AMDGPU_MPI"]

		if "qpm_options" in info and "backend" in info["qpm_options"]:
			if info["qpm_options"]["backend"] in backend_options:
				backend_chosen = info["qpm_options"]["backend"]
			else:
				logging.debug(f"Available backends: {backend_options}")
				logging.debug("Incorrect backend specified in qpm_options. Using default MPI")
				backend_chosen = "MPI"
		else:
			backend_chosen = "MPI"

		# # command common across QPMs!
		# cmd = f'{exec_cmd} --dvm {dvm} -x LD_LIBRARY_PATH ' \
		# 	f'--mca btl ^tcp,ofi,vader,openib ' \
		# 	f'--mca pml ^ucx --mca mtl ofi --mca opal_common_ofi_provider_include '\
		# 	f'{info["provider"]} --map-by {info["mapping"]} --bind-to core '\
		# 	f'--np {info["np"]} --host {hosts} {gpuwrapper} '

		# command common across QPMs!
		cmd = f'{exec_cmd} --dvm {dvm} -x LD_LIBRARY_PATH ' \
			f'--mca btl ^tcp,ofi,vader,openib ' \
			f'--mca pml ^ucx --mca mtl ofi --mca opal_common_ofi_provider_include '\
			f'{info["provider"]} --map-by {info["mapping"]} --bind-to core '\
			f'--np {info["np"]} --host {hosts} {gpuwrapper} '

		cmd += f'-v {nwqsim_executable} --qasm_file {qasm_file} --backend {backend_chosen} '

		if "num_shots" in info:
			cmd += f'--shots {info["num_shots"]} '

		if "method" in info:
			cmd += f'--sim {info["method"]}'

		logging.debug(f"NWQSIM cmd - {cmd}")

		return cmd

	def test(self):
		return "****Testing the NWQSIM QRC****"
