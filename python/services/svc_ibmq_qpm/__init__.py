import sys, os, logging, threading
import util.qpm.util_qpm as uq
import defw

SERVICE_NAME = "QPM"
SERVICE_DESC = "Quantum Platform Manager for IBMQ"

svc_info = {
    "name": SERVICE_NAME,
    "module": __name__,
    "description": SERVICE_DESC,
    "version": 1.0,
}

# Import QPM class
from .svc_qpm import QPM
service_classes = [QPM]

def qpm_complete_init():
    uq.qpm_initialized = True
    logging.debug("IBMQ QPM initialized successfully")


def qpm_wait_resmgr():
    while not defw.resmgr and not uq.qpm_shutdown:
        logging.debug("IBMQ QPM waiting for resmgr...")
        threading.Event().wait(1)
    if not uq.qpm_shutdown:
        qpm_complete_init()

def initialize():
    if uq.qpm_initialized:
        return

    timeout = int(os.environ.get("QFW_STARTUP_TIMEOUT", 40))
    if not defw.resmgr:
        svc_qpm_thr = threading.Thread(target=qpm_wait_resmgr)
        svc_qpm_thr.daemon = True
        svc_qpm_thr.start()
        return

    qpm_complete_init()

def uninitialize():
    uq.qpm_shutdown = True
    logging.debug("IBMQ QPM shutdown called")
