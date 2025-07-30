import defw, logging
from defw_exception import DEFwReserveError
from time import sleep

SYSTEM_UP_TIMEOUT = 40

def defw_get_resource_mgr(timeout=SYSTEM_UP_TIMEOUT):
	if not defw.wait_resmgr(timeout):
		logging.debug("Couldn't find a resmgr")
		raise DEFwReserveError("Couldn't find a resmgr")

	return defw.resmgr

def defw_reserve_service_by_name(resmgr, svc_name, svc_type = -1,
								 svc_cap = -1, timeout=SYSTEM_UP_TIMEOUT):
	wait = 0
	while wait < timeout:
		service_infos = resmgr.get_services(svc_name, svc_type, svc_cap)
		if service_infos and len(service_infos) > 0:
			break
		wait += 1
		logging.debug(f"Waiting to connect to {svc_name}")
		sleep(1)

	if len(service_infos) == 0:
		raise DEFwReserveError(f"Couldn't connect to a {svc_name}, {svc_type}, {svc_cap}")

	logging.debug(f"Received service_infos: {service_infos}")

	svc_apis = defw.connect_to_resource(service_infos, svc_name)

	return svc_apis

