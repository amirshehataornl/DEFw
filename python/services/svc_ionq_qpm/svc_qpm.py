import os, logging, yaml
from util.qpm.util_qpm import UTIL_QPM
from .svc_qrc import QRC

class QPM(UTIL_QPM):
    def __init__(self, start=True):
        logging.debug("Initializing IONQ QPM")
        super().__init__(QRC(start=start), start=start)

        self.provider = "IONQ"
        self.load_ionq_env_yaml()

        IONQ_API_KEY = os.getenv('IONQ_API_KEY', None)

        if IONQ_API_KEY is None:
            from defw_exception import DEFwError
            logging.debug("IONQ_API_KEY not set in environment!")
            raise DEFwError("IONQ_API_KEY not set in environment!")

        try:
            # quick check if qiskit_ionq is in pip freeze
            from qiskit_ionq import IonQProvider
            self.provider = IonQProvider(os.environ["IONQ_API_KEY"])
            self.backends = self.provider.backends()
            logging.debug(f"IONQ provider initialized with {len(self.backends)} backends")
            logging.debug("IONQ provider initialized successfully")
        except Exception as e:
            from defw_exception import DEFwError
            logging.critical(f"IONQ API Key test failed: {e}")
            raise DEFwError(f"IONQ_API_KEY invalid/unreachable: {e}")

    def load_ionq_env_yaml(self, path="ionq_env.yaml"):
        if not os.path.exists(path):
            raise FileNotFoundError(f"IONQ YAML config not found: {path}")

        with open(path, "r") as f:
            cfg = yaml.safe_load(f)

        ionq = cfg.get("IONQ", {})

        for key, value in ionq.items():
            if value is None:
                logging.warning(f"IONQ config field {key} is None")
                continue
            env_key = f"IONQ_{key}"
            os.environ[env_key] = str(value)
            logging.debug(f"Set environment variable {env_key} from YAML")

    def query(self):
        logging.debug("Querying IONQ QPM info")
        from . import SERVICE_NAME, SERVICE_DESC
        from api_qpm import QPMType, QPMCapability

        info = self.query_helper(
            QPMType.QPM_TYPE_IONQ,
            QPMCapability.QPM_CAP_IONTRAP,
            SERVICE_NAME,
            SERVICE_DESC,
        )
        logging.debug(f"IONQ {SERVICE_NAME} info: {info}")
        return info

    def create_circuit(self, info):
        """
        Override to inject IonQ backend and neutralize resource-heavy fields.
        """
        info["qfw_backend"] = self.provider
        info["np"] = 0 # IonQ does not use MPI
        info["exec"] = None
        info["modules"] = {}
        return super().create_circuit(info)

    def consume_resources(self, circ):
        """
        IonQ does not require resource allocation, but mark the circuit
        as 'resources consumed' so it is tracked properly.
        """
        circ.set_resources_consumed()
        logging.debug(f"IonQ: marked circuit {circ.get_cid()} as resources consumed")

    def test(self):
        if not hasattr(self, "provider"):
            from defw_exception import DEFwError
            raise DEFwError("IonQ QPM not ready: missing provider")
        return "****IonQ QPM Test Successful****"
