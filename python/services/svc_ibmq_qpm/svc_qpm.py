import os, logging, yaml, sys
from util.qpm.util_qpm import UTIL_QPM
import requests, json
from .svc_qrc import QRC

CURRENT_PATH = os.path.split(os.path.abspath(__file__))[0]

class QPM(UTIL_QPM):
    def __init__(self, start=True):
        logging.debug("Initializing IBMQ QPM")
        super().__init__(QRC(start=start), start=start)

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        self.provider = "IBMQ"
        logging.debug("CURRENT_PATH for IBMQ QPM: " + str(CURRENT_PATH))
        self.load_ibmq_env_yaml(os.path.join(CURRENT_PATH, "ibmq_env.yaml"))

        # check if HTTPS_PROXY is set
        https_proxy = os.getenv('HTTPS_PROXY', None)
        if https_proxy is None:
            logging.debug("IBMQ: HTTPS_PROXY not set in environment for IBMQ!")
        else:
            logging.debug(f"IBMQ: Using HTTPS_PROXY for IBMQ: {https_proxy}")

        IBMQ_API_KEY = os.getenv('IBMQ_API_KEY', None)

        if IBMQ_API_KEY is None:
            from defw_exception import DEFwError
            logging.debug("IBMQ: IBMQ_API_KEY not set in environment!")
            raise DEFwError("IBMQ_API_KEY not set in environment!")

        try:
            logging.debug("IBMQ: Requesting IBMQ Bearer token...")
            ibm_token_url = os.getenv('IBMQ_TOKEN_URL', None)
            if ibm_token_url is None:
                raise DEFwError("IBMQ_TOKEN_URL is not in env.")
            data = f'grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey={IBMQ_API_KEY}'
            response = requests.post(ibm_token_url, headers=headers, data=data)
            # check response
            if response.status_code != 200:
                raise DEFwError(f"IBMQ token request failed with status {response.status_code}: {response.text}")
            BEARER_TOKEN = response.json()['access_token']
            if BEARER_TOKEN is None:
                raise DEFwError("IBMQ token request did not return access_token")

            logging.debug("IBMQ: Bearer token obtained successfully.")
            os.environ['IBMQ_BEARER_TOKEN'] = BEARER_TOKEN # we set the short lived token here!

            # test this bearer token? but it is only 1 hour, I am confused what to do here..
            # we'll get back here if need be.

        except Exception as e:
            from defw_exception import DEFwError
            logging.critical(f"IBMQ: API Key test failed: {e}")
            raise DEFwError(f"IBMQ_API_KEY invalid/unreachable: {e}")

    def load_ibmq_env_yaml(self, path=None):
        logging.debug("IBMQ: Loading IBMQ environment variables from YAML")

        if path is None:
            path = os.path.join(CURRENT_PATH, "ibmq_env.yaml")

        logging.debug(f"IBMQ: Loading IBMQ config from {path}")

        if not os.path.exists(path):
            logging.error(f"IBMQ: YAML config file not found: {path}")
            raise FileNotFoundError(f"IBMQ: YAML config not found: {path}")

        with open(path, "r") as f:
            logging.debug("IBMQ: Reading YAML config file")
            cfg = yaml.safe_load(f)
            logging.debug(f"IBMQ: YAML config content: {cfg}")

        logging.debug(f"IBMQ: YAML config loaded: {cfg}")

        ibmq = cfg.get("CONFIG", {})
        logging.debug(f"IBMQ: CONFIG section: {ibmq}")

        for key, value in ibmq.items():
            if value is None:
                logging.warning(f"IBMQ: config field {key} is None")
                continue
            logging.debug(f"IBMQ: setting env {key}={value}")
            os.environ[f"{key}"] = str(value)
        logging.debug("IBMQ: environment variables loaded from YAML")

    def query(self):
        logging.debug("IBMQ: Querying IBMQ QPM info")
        from . import SERVICE_NAME, SERVICE_DESC
        from api_qpm import QPMType, QPMCapability

        info = self.query_helper(
            QPMType.QPM_TYPE_IBMQ,
            QPMCapability.QPM_CAP_SUPERCONDUCTOR,
            SERVICE_NAME,
            SERVICE_DESC,
        )
        logging.debug(f"IBMQ: {SERVICE_NAME} info: {info}")
        return info

    def create_circuit(self, info):
        """
        Override to inject IBMQ backend and neutralize resource-heavy fields.
        """
        info["qfw_backend"] = self.provider
        info["np"] = 0 # IBMQ does not use MPI
        info["exec"] = None
        info["modules"] = {}
        return super().create_circuit(info)

    def consume_resources(self, circ):
        """
        IBMQ does not require resource allocation, but mark the circuit
        as 'resources consumed' so it is tracked properly.
        """
        circ.set_resources_consumed()
        logging.debug(f"IBMQ: marked circuit {circ.get_cid()} as resources consumed")

    def test(self):
        if not hasattr(self, "provider"):
            from defw_exception import DEFwError
            raise DEFwError("IBMQ QPM not ready: missing provider")
        return "****IBMQ QPM Test Successful****"
