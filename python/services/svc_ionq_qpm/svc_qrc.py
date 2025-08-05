import logging
from util.qpm.util_qrc import UTIL_QRC
from qiskit.circuit import QuantumCircuit
from defw_exception import DEFwError, DEFwInProgress
from api_events import Event

import sys, os, time
sys.path.append(os.path.split(os.path.abspath(__file__))[0])

class QRC(UTIL_QRC):
    def __init__(self, start=True):
        logging.debug("Initializing IonQ QRC")
        super().__init__(start=start)

        os.environ["IONQ_API_KEY"]="FvoHMZhguJptdSIHwDlQ3E6z0vqNbEl7"
        os.environ["HTTPS_PROXY"]="http://proxy.ccs.ornl.gov:3128/"

    def form_cmd(self, circ, qasm_file):
        """
        IonQ does not run commands locally. This method is unused, but required by UTIL_QRC.
        """
        raise DEFwError("IonQ QRC does not use local command execution!")

    def parse_result(self, counts):
        """
        IonQ results are already in counts dictionary format.
        """
        logging.debug(f"Parsing IONQ result: {counts}")
        # convert numpy int64 to regular int for JSON serialization if needed
        counts = {str(k): int(v) for k, v in counts.items()}
        return counts

    def run_circuit(self, circ):
        """
        Synchronous IonQ job execution. Blocks until results are ready.
        """
        logging.debug(f"IonQ run_circuit for circuit {circ.get_cid()}")
        provider = circ.info.get("qfw_backend")
        if not provider:
            raise DEFwError("IonQ provider not set in circuit info")

        backend_name = circ.info.get("qpm_options", {}).get("backend", "simulator")
        backend = provider.get_backend(backend_name)

        qc = QuantumCircuit.from_qasm_str(circ.info["qasm"])
        shots = circ.info.get("num_shots", 1024)

        circ.set_launching()
        circ.set_running()

        job = backend.run(qc, shots=shots)
        result = job.result().get_counts()

        circ.set_exec_done()

        logging.debug(f"IonQ run_circuit result: {result}")

        ret_obj = {
            "cid": circ.get_cid(),
            "result": result,
            "rc": 0,
            "launch_time": circ.launch_time,
            "creation_time": circ.creation_time,
            "exec_time": circ.exec_time,
            "completion_time": circ.completion_time,
            "resources_consumed_time": circ.resources_consumed_time,
            "cq_enqueue_time": tim.time(),
            "cq_dequeue_time": -1,
        }

        logging.debug(f"IonQ run_circuit result: {ret_obj}")

        return ret_obj

    def run_circuit_async(self, circ):
        """
        Asynchronous IonQ job execution. Submits the job and returns a task_info object.
        The worker thread will later check for job completion.
        """
        logging.debug(f"IonQ run_circuit_async for circuit {circ.get_cid()}")
        provider = circ.info.get("qfw_backend")
        if not provider:
            raise DEFwError("IonQ provider not set in circuit info")

        backend_name = circ.info.get("qpm_options", {}).get("backend", "simulator")
        backend = provider.get_backend(backend_name)

        logging.debug(f"IonQ run_circuit_async using backend: {backend_name}")

        qc = QuantumCircuit.from_qasm_str(circ.info["qasm"])
        shots = circ.info.get("num_shots", 1024)

        circ.set_launching()
        circ.set_running()

        try:
            job = backend.run(qc, shots=shots)
        except Exception as e:
            logging.error(f"Error submitting IONQ job: {e}")
            circ.set_fail()
            raise DEFwError(f"Failed to submit IONQ job: {e}")

        logging.debug(f"IonQ run_circuit_async submitted job: {job.job_id()}")

        # Return task_info similar to UTIL_QRC expectations
        task_info = {
            "circ": circ,
            "qasm_file": None,  # IonQ does not use local QASM files
            "pid": None,  # No local process ID
            "job": job,
        }
        logging.debug(f"IonQ run_circuit_async submitted job: {job.job_id()}")
        return task_info

    def check_active_tasks(self, wid):
        """
        Override UTIL_QRC's active task polling: IonQ jobs can be polled via job.status().
        """
        os.environ["HTTPS_PROXY"]="http://proxy.ccs.ornl.gov:3128/"
        os.environ["HTTP_PROXY"]="http://proxy.ccs.ornl.gov:3128/"
        os.environ["ALL_PROXY"]="socks://proxy.ccs.ornl.gov:3128/"
        os.environ["FTP_PROXY"]="ftp://proxy.ccs.ornl.gov:3128/"
        os.environ["NO_PROXY"]="localhost,127.0.0.0/8,*.ccs.ornl.gov"

        logging.debug(f"IonQ check_active_tasks for worker {wid}")
        complete = []
        for task_info in self.worker_pool[wid]["active_tasks"]:
            job = task_info["job"]
            circ = task_info["circ"]

            logging.debug(f"check_active_tasks worker {wid} checking job {job.job_id()} for circuit {circ.get_cid()}")

            logging.debug(f"Job {job.job_id()} has a status: {job.status()}, does it have a name? {job.status().name}")

            if job.status().name == "DONE":
                try:
                    result_obj = job.result()
                    logging.debug(f"IONQ job {job.job_id()} completed with result: {result_obj}")
                    circ.set_exec_done()

                except Exception as e:
                    logging.error(f"Error fetching IONQ job result: {result_obj}")
                    result = {"error": str(e)}
                    circ.set_fail()

                complete.append(task_info)

                logging.debug(f"dir(job)={dir(job)}")
                try:
                    logging.debug(f"circ = {circ}")
                    r = {
                        "cid": circ.get_cid(),
                        "result": self.parse_result(result_obj.get_counts()),
                        "rc": 0 if circ.getState() else -1,
                        "launch_time": circ.launch_time,
                        "creation_time": circ.creation_time,
                        "exec_time": circ.exec_time,
                        "completion_time": circ.completion_time,
                        "resources_consumed_time": circ.resources_consumed_time,
                        "cq_enqueue_time": time.time(),
                        "cq_dequeue_time": -1,
                    }
                except Exception as e:
                    logging.error(f"Error parsing IONQ job result: {e}")

                logging.debug(f"IonQ check_active_tasks result: {r}")

                # push the result if push info were registered:
                if self.push_info:
                    try:
                        logging.debug(f"Pushing result for circuit {circ.get_cid()} to client")
                        event = Event(self.push_info['evtype'], r)
                        logging.debug(f"Pushing event {event} to client {self.push_info['class']}")
                        self.push_info['class'].put(event)
                    except Exception as e:
                        logging.critical(f"Failed to push event to client. Exception encountered {e}")
                        raise e
                else:
                    logging.debug(f"No push info registered, appending result for circuit {circ.get_cid()}")
                    with self.circuit_results_lock:
                        self.circuit_results.append(r)

        for task_info in complete:
            self.worker_pool[wid]['active_tasks'].remove(task_info)
