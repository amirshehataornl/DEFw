import logging
import os
import time
import requests

from util.qpm.util_qrc import UTIL_QRC
from defw_exception import DEFwError
from api_events import Event

import sys
sys.path.append(os.path.split(os.path.abspath(__file__))[0])


class QRC(UTIL_QRC):
	def __init__(self, start=True):
		logging.debug("IBMQ_QRC: __init__ starting")
		super().__init__(start=start)

		self.session = requests.Session()

		# env: HTTPS_PROXY / HTTP_PROXY
		self._proxy_cfg = self._build_proxy_cfg()

		logging.debug("IBMQ_QRC: __init__ done")

	def form_cmd(self, circ, qasm_file):
		raise DEFwError("IBMQ QRC does not use local command execution!")

	# -------------------------
	# Proxy handling
	# -------------------------
	def _build_proxy_cfg(self):
		https_proxy = os.getenv("HTTPS_PROXY", "").strip()
		http_proxy = os.getenv("HTTP_PROXY", "").strip()

		if not https_proxy and not http_proxy:
			logging.debug("IBMQ_QRC: no proxy configured (direct connection)")
			return None

		proxies = {}
		if http_proxy:
			proxies["http"] = http_proxy
		if https_proxy:
			proxies["https"] = https_proxy

		logging.debug(f"IBMQ_QRC: using proxies={proxies}")
		return proxies

	# -------------------------
	# Env + headers
	# -------------------------
	def _get_env(self, key, required=True, default=None):
		val = os.getenv(key, default)
		logging.debug(f"IBMQ_QRC: env[{key}] -> {'<set>' if val else '<unset>'}")
		if required and (val is None or str(val).strip() == ""):
			raise DEFwError(f"IBMQ_QRC: missing required env var: {key}")
		return val

	def _jobs_url(self):
		url = self._get_env("IBMQ_JOB_API_URL", required=True).rstrip("/")
		logging.debug(f"IBMQ_QRC: jobs_url={url}")
		return url

	def _headers(self):
		token = self._get_env("IBMQ_BEARER_TOKEN", required=True)
		crn = self._get_env("IBMQ_SERVICE_CRN", required=True)
		api_ver = self._get_env("IBMQ_API_VERSION", required=False, default="2025-05-01")

		logging.debug(f"IBMQ_QRC: token length={len(token)}")
		logging.debug(f"IBMQ_QRC: Service-CRN startswith 'crn:'? {str(crn).startswith('crn:')}")
		logging.debug(f"IBMQ_QRC: IBM-API-Version={api_ver}")

		return {
			"accept": "application/json",
			"Content-Type": "application/json",
			"Authorization": f"Bearer {token}",
			"Service-CRN": crn,
			"IBM-API-Version": api_ver,
		}

	def _normalize_state(self, state):
		if state is None:
			return ""
		s = str(state).upper()
		if "." in s:
			s = s.split(".")[-1]
		return s

	def _format_ibm_error(self, resp):
		"""
		IBM Runtime often returns:
		{"errors":[{"code":1215,"message":"...","solution":"...","more_info":"..."}],"trace":"..."}
		Return a compact, readable message.
		"""
		status = getattr(resp, "status_code", None)
		text = getattr(resp, "text", "")

		try:
			j = resp.json()
		except Exception:
			return f"HTTP {status}: {text}"

		errors = j.get("errors", None)
		trace = j.get("trace", None)

		if not errors:
			return f"HTTP {status}: {j}"

		e0 = errors[0] if isinstance(errors, list) and len(errors) > 0 else {}
		code = e0.get("code", None)
		msg = e0.get("message", None)
		solution = e0.get("solution", None)
		more_info = e0.get("more_info", None)

		out = f"HTTP {status}"
		if code is not None:
			out += f" (code {code})"
		if msg:
			out += f": {msg}"
		if solution:
			out += f" | solution: {solution}"
		if more_info:
			out += f" | more_info: {more_info}"
		if trace:
			out += f" | trace: {trace}"
		return out

	def _fail_msg(self, prefix, resp):
		return f"{prefix}: {self._format_ibm_error(resp)}"

	# -------------------------
	# Requests helper
	# -------------------------
	def _request(self, method, url, headers, json_body=None, timeout_s=60):
		"""
		Wrapper for HTTP calls with consistent logging, proxy support, and better errors.
		"""
		logging.debug(f"IBMQ_QRC: HTTP {method} {url}")
		if json_body is not None:
			logging.debug(f"IBMQ_QRC: HTTP {method} json={json_body}")

		logging.debug(f"IBMQ_QRC: HTTP {method} has Authorization? {'Authorization' in headers}")
		logging.debug(f"IBMQ_QRC: HTTP {method} has Service-CRN? {bool(headers.get('Service-CRN','').strip())}")
		logging.debug(f"IBMQ_QRC: HTTP {method} proxies={'<none>' if self._proxy_cfg is None else self._proxy_cfg}")

		try:
			if method == "GET":
				resp = self.session.get(url, headers=headers, proxies=self._proxy_cfg, timeout=timeout_s)
			elif method == "POST":
				resp = self.session.post(url, headers=headers, json=json_body, proxies=self._proxy_cfg, timeout=timeout_s)
			else:
				raise DEFwError(f"IBMQ_QRC: unsupported HTTP method: {method}")

			logging.debug(f"IBMQ_QRC: HTTP {method} status={resp.status_code}")
			logging.debug(f"IBMQ_QRC: HTTP {method} text={resp.text}")
			return resp

		except requests.exceptions.ProxyError as e:
			msg = (
				f"IBMQ_QRC: ProxyError while connecting to {url}: {e}. "
				f"This is typically ORNL proxy tunnel failure (503). "
				f"Check HTTPS_PROXY / HTTP_PROXY. Current proxies={self._proxy_cfg}"
			)
			logging.exception(msg)
			raise DEFwError(msg)

		except requests.exceptions.ConnectTimeout as e:
			msg = f"IBMQ_QRC: ConnectTimeout to {url}: {e} (timeout_s={timeout_s})"
			logging.exception(msg)
			raise DEFwError(msg)

		except requests.exceptions.ReadTimeout as e:
			msg = f"IBMQ_QRC: ReadTimeout from {url}: {e} (timeout_s={timeout_s})"
			logging.exception(msg)
			raise DEFwError(msg)

		except Exception as e:
			msg = f"IBMQ_QRC: HTTP {method} exception to {url}: {e}"
			logging.exception(msg)
			raise DEFwError(msg)

	def _hex_to_bitstring(self, x, width=None):
		s = str(x)

		if all(ch in "01" for ch in s) and len(s) > 0:
			if width is None:
				return s
			return s.zfill(width)[-width:]

		try:
			if s.startswith(("0x", "0X")):
				v = int(s, 16)
			else:
				v = int(s)
			b = format(v, "b")
			if width is None:
				return b
			return b.zfill(width)[-width:]
		except Exception:
			return s

	def parse_counts_from_sampler_results(self, res_json, width=None):
		logging.debug(f"IBMQ_QRC: parse_counts keys={list(res_json.keys())}")

		results = res_json.get("results", [])
		if not results:
			logging.debug("IBMQ_QRC: parse_counts: empty results")
			return {"raw": res_json}

		data = results[0].get("data", {}) or {}
		c = data.get("c", {}) or {}
		samples = c.get("samples", None)

		logging.debug(f"IBMQ_QRC: parse_counts data_keys={list(data.keys())}")
		logging.debug(f"IBMQ_QRC: parse_counts c_keys={list(c.keys())}")
		logging.debug(f"IBMQ_QRC: parse_counts samples_present={samples is not None}")

		if samples is None:
			return {"raw": res_json}

		counts = {}
		for samp in samples:
			k = self._hex_to_bitstring(samp, width=width)
			counts[k] = counts.get(k, 0) + 1

		logging.debug(f"IBMQ_QRC: parse_counts counts_size={len(counts)}")
		return counts

	# -------------------------
	# Return object helpers
	# -------------------------
	def _ok_ret(self, circ, result):
		ret_obj = {
			"cid": circ.get_cid(),
			"result": result,
			"rc": 0,
			"launch_time": circ.launch_time,
			"creation_time": circ.creation_time,
			"exec_time": circ.exec_time,
			"completion_time": circ.completion_time,
			"resources_consumed_time": circ.resources_consumed_time,
			"cq_enqueue_time": time.time(),
			"cq_dequeue_time": -1,
		}
		logging.debug(f"IBMQ_QRC: _ok_ret cid={circ.get_cid()} rc=0")
		return ret_obj

	def _error_ret(self, circ, msg):
		ret_obj = {
			"cid": circ.get_cid(),
			"result": {"error": msg},
			"rc": -1,
			"launch_time": circ.launch_time,
			"creation_time": circ.creation_time,
			"exec_time": circ.exec_time,
			"completion_time": circ.completion_time,
			"resources_consumed_time": circ.resources_consumed_time,
			"cq_enqueue_time": time.time(),
			"cq_dequeue_time": -1,
		}
		logging.debug(f"IBMQ_QRC: _error_ret cid={circ.get_cid()} rc=-1 msg={msg}")
		return ret_obj

	def _finalize_task(self, circ, result_obj, rc, err_msg=None):
		"""
		Finalize a task (success or failure) and notify the waiting layer.
		"""
		r = {
			"cid": circ.get_cid(),
			"result": result_obj if err_msg is None else {"error": err_msg, "raw": result_obj},
			"rc": rc,
			"launch_time": circ.launch_time,
			"creation_time": circ.creation_time,
			"exec_time": circ.exec_time,
			"completion_time": circ.completion_time,
			"resources_consumed_time": circ.resources_consumed_time,
			"cq_enqueue_time": time.time(),
			"cq_dequeue_time": -1,
		}

		logging.debug(f"IBMQ_QRC: _finalize_task cid={circ.get_cid()} rc={rc} err={err_msg}")

		if self.push_info:
			try:
				logging.debug(f"IBMQ_QRC: pushing event cid={circ.get_cid()} rc={rc}")
				event = Event(self.push_info["evtype"], r)
				self.push_info["class"].put(event)
			except Exception as e:
				logging.critical(f"IBMQ_QRC: failed to push event cid={circ.get_cid()}: {e}")
				with self.circuit_results_lock:
					self.circuit_results.append(r)
		else:
			with self.circuit_results_lock:
				self.circuit_results.append(r)

		return r

	# -------------------------
	# Sync execution
	# -------------------------
	def run_circuit(self, circ):
		logging.debug(f"IBMQ_QRC: run_circuit start cid={circ.get_cid()}")
		logging.debug(f"IBMQ_QRC: circ.info keys={list(circ.info.keys())}")

		try:
			jobs_url = self._jobs_url()
			headers = self._headers()
		except Exception as e:
			circ.set_fail()
			return self._error_ret(circ, str(e))

		if "qasm" not in circ.info:
			msg = "IBMQ_QRC: circ.info['qasm'] missing"
			logging.error(msg)
			circ.set_fail()
			return self._error_ret(circ, msg)

		qpm_opts = circ.info.get("qpm_options", {}) or {}
		backend = qpm_opts.get("backend", None)  # keep None if you want
		poll_s = int(qpm_opts.get("poll_s", 5))
		shots = int(circ.info.get("num_shots", 1024))

		width = circ.info.get("num_clbits", circ.info.get("num_qubits", None))
		try:
			width = int(width) if width is not None else None
		except Exception:
			width = None

		logging.debug(f"IBMQ_QRC: backend={backend} shots={shots} poll_s={poll_s} width={width}")

		circ.set_launching()
		circ.set_running()

		# Leave None in pubs (as requested)
		payload = {
			"program_id": "sampler",
			"backend": backend,
			"params": {
				"pubs": [[circ.info["qasm"], None, shots]],
				"version": int(qpm_opts.get("version", 2)),
			}
		}
		if "options" in qpm_opts:
			payload["params"]["options"] = qpm_opts["options"]

		try:
			resp = self._request("POST", jobs_url, headers, json_body=payload, timeout_s=60)
			if resp.status_code != 200:
				msg = self._fail_msg("IBMQ_QRC submit failed", resp)
				logging.error(msg)
				circ.set_fail()
				return self._error_ret(circ, msg)

			job_id = resp.json().get("id", None)
			logging.debug(f"IBMQ_QRC: submit job_id={job_id}")
			if not job_id:
				msg = f"IBMQ_QRC submit failed: response missing 'id': {resp.text}"
				logging.error(msg)
				circ.set_fail()
				return self._error_ret(circ, msg)

			job_url = f"{jobs_url}/{job_id}"
			while True:
				st = self._request("GET", job_url, headers, timeout_s=60)
				if st.status_code != 200:
					msg = self._fail_msg("IBMQ_QRC status failed", st)
					logging.error(msg)
					circ.set_fail()
					return self._error_ret(circ, msg)

				state = self._normalize_state(st.json().get("state", None))
				logging.debug(f"IBMQ_QRC: job_id={job_id} state={state}")

				if state in ("DONE", "COMPLETED"):
					break
				if state in ("ERROR", "FAILED", "CANCELLED", "CANCELED"):
					msg = f"IBMQ_QRC: Job ended with state={state}"
					logging.error(msg)
					circ.set_fail()
					return self._error_ret(circ, msg)

				time.sleep(poll_s)

			results_url = f"{jobs_url}/{job_id}/results"
			rr = self._request("GET", results_url, headers, timeout_s=60)
			if rr.status_code != 200:
				msg = self._fail_msg("IBMQ_QRC results failed", rr)
				logging.error(msg)
				circ.set_fail()
				return self._error_ret(circ, msg)

			counts = self.parse_counts_from_sampler_results(rr.json(), width=width)

			circ.set_exec_done()
			return self._ok_ret(circ, counts)

		except Exception as e:
			msg = f"IBMQ_QRC: Exception during run_circuit: {e}"
			logging.exception(msg)
			circ.set_fail()
			return self._error_ret(circ, msg)

	# -------------------------
	# Async execution
	# -------------------------
	def run_circuit_async(self, circ):
		logging.debug(f"IBMQ_QRC: run_circuit_async start cid={circ.get_cid()}")

		jobs_url = self._jobs_url()
		headers = self._headers()

		if "qasm" not in circ.info:
			circ.set_fail()
			raise DEFwError("IBMQ_QRC: circ.info['qasm'] missing")

		qpm_opts = circ.info.get("qpm_options", {}) or {}
		backend = qpm_opts.get("backend", None)  # keep None if you want
		poll_s = int(qpm_opts.get("poll_s", 5))
		shots = int(circ.info.get("num_shots", 1024))

		width = circ.info.get("num_clbits", circ.info.get("num_qubits", None))
		try:
			width = int(width) if width is not None else None
		except Exception:
			width = None

		circ.set_launching()
		circ.set_running()

		payload = {
			"program_id": "sampler",
			"backend": backend,
			"params": {
				"pubs": [[circ.info["qasm"], None, shots]],
				"version": int(qpm_opts.get("version", 2)),
			}
		}
		if "options" in qpm_opts:
			payload["params"]["options"] = qpm_opts["options"]

		resp = self._request("POST", jobs_url, headers, json_body=payload, timeout_s=60)
		if resp.status_code != 200:
			msg = self._fail_msg("IBMQ_QRC async submit failed", resp)
			logging.error(msg)
			circ.set_fail()
			raise DEFwError(msg)

		job_id = resp.json().get("id", None)
		logging.debug(f"IBMQ_QRC: async submit job_id={job_id}")
		if not job_id:
			circ.set_fail()
			raise DEFwError(f"IBMQ_QRC async submit failed: response missing 'id': {resp.text}")

		return {
			"circ": circ,
			"job_id": job_id,
			"poll_s": poll_s,
			"width": width,
		}

	def check_active_tasks(self, wid):
		logging.debug(f"IBMQ_QRC: check_active_tasks wid={wid}")

		try:
			jobs_url = self._jobs_url()
			headers = self._headers()
		except Exception as e:
			logging.error(f"IBMQ_QRC: check_active_tasks cannot build headers/env: {e}")
			return

		complete = []

		for task_info in self.worker_pool[wid]["active_tasks"]:
			circ = task_info["circ"]
			job_id = task_info["job_id"]
			width = task_info.get("width", None)

			job_url = f"{jobs_url}/{job_id}"
			logging.debug(f"IBMQ_QRC: async poll job_id={job_id} cid={circ.get_cid()}")

			try:
				st = self._request("GET", job_url, headers, timeout_s=60)

				# ---- FAILURE: status endpoint itself failed ----
				if st.status_code != 200:
					msg = self._fail_msg("IBMQ_QRC async status failed", st)
					logging.error(msg)
					circ.set_fail()
					self._finalize_task(circ, {"status_resp": st.text}, rc=-1, err_msg=msg)
					complete.append(task_info)
					continue

				state = self._normalize_state(st.json().get("state", None))
				logging.debug(f"IBMQ_QRC: async job_id={job_id} state={state}")

				# ---- FAILURE: IBM marked job failed/cancelled ----
				if state in ("ERROR", "FAILED", "CANCELLED", "CANCELED"):
					msg = f"IBMQ_QRC: job ended with state={state}"
					logging.error(msg)
					circ.set_fail()
					self._finalize_task(circ, {"state": state}, rc=-1, err_msg=msg)
					complete.append(task_info)
					continue

				# ---- NOT DONE YET ----
				if state not in ("DONE", "COMPLETED"):
					continue

				# ---- DONE: fetch results ----
				results_url = f"{jobs_url}/{job_id}/results"
				rr = self._request("GET", results_url, headers, timeout_s=60)

				# ---- FAILURE: results endpoint failed ----
				if rr.status_code != 200:
					msg = self._fail_msg("IBMQ_QRC async results failed", rr)
					logging.error(msg)
					circ.set_fail()
					self._finalize_task(circ, {"results_resp": rr.text}, rc=-1, err_msg=msg)
					complete.append(task_info)
					continue

				counts = self.parse_counts_from_sampler_results(rr.json(), width=width)
				circ.set_exec_done()
				self._finalize_task(circ, counts, rc=0)
				complete.append(task_info)

			except Exception as e:
				msg = f"IBMQ_QRC: async poll exception job_id={job_id}: {e}"
				logging.exception(msg)
				circ.set_fail()
				self._finalize_task(circ, {"exception": str(e)}, rc=-1, err_msg=msg)
				complete.append(task_info)

		for t in complete:
			self.worker_pool[wid]["active_tasks"].remove(t)
