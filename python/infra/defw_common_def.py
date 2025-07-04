import cdefw_global
from defw_exception import DEFwError, DEFwDumper, DEFwNotFound
import logging, os, yaml, shutil, threading, time, sys
import cdefw_global
from pathlib import Path
from collections import deque

FILE_HANDLER = None
CUSTOM_LEVELS = {}

# DEFAULT LOG LEVELS
DEFW_LOG_LEVEL_INFRA =			30
DEFW_LOG_LEVEL_SERVICES =		31
DEFW_LOG_LEVEL_EXPERIMENTS = 	32
DEFW_LOG_LEVEL_WORKER =			33
DEFW_LOG_LEVEL_STACKTRACE =		34
DEFW_LOG_LEVEL_APP =			35

DEFW_LOG_LEVEL_INFRA_NAME =				"DEFW_INFRA"
DEFW_LOG_LEVEL_SERVICES_NAME =			"DEFW_SERVICES"
DEFW_LOG_LEVEL_EXPERIMENTS_NAME =		"DEFW_EXPERIMENTS"
DEFW_LOG_LEVEL_WORKER_NAME =			"DEFW_WORKERS"
DEFW_LOG_LEVEL_STACKTRACE_NAME =		"DEFW_STACKTRACE"
DEFW_LOG_LEVEL_APP_NAME =				"DEFW_APP"

DEFW_STATUS_STRING = 'DEFw STATUS: '
DEFW_STATUS_SUCCESS = 'Success'
DEFW_STATUS_FAILURE = 'Failure'
DEFW_STATUS_IGNORE = 'Ignore'
DEFW_CODE_STRING = 'DEFw CODE: '
MASTER_PORT = 8494
MASTER_DAEMON_PORT = 8495
AGENT_DAEMON_PORT = 8094
DEFW_SCRIPT_PATHS = ['src/',
		     'python/',
		     'python/service-apis',
		     'python/service-apis/util',
		     'python/services',
		     'python/services/util',
		     'python/infra',
		     'python/config'
		     'python/experiments']
MIN_IFS_NUM_DEFAULT = 3
g_system_shutdown = False
# RPC statistics by endpoint. Contains Max/Min/Avg time taken for each RPC
# which is blocking and non-blocking separately

class RPCMetrics:
	def __init__(self, window_size=4096):
		self.lock = threading.Lock()
		self.window_size = window_size
		self.rpc_rsp_timing_db = {'window': deque(maxlen=self.window_size),
								  'avg': 0.0, 'min': sys.maxsize, 'max': 0.0,
								  'total': 0}
		self.rpc_req_timing_db = {'window': deque(maxlen=self.window_size),
								  'avg': 0.0, 'min': sys.maxsize, 'max': 0.0,
								  'total': 0}
		self.method_timing_db = {}

	def add_timing_locked(self, send_time, recv_time, db):
		rtt = recv_time - send_time
		db['total'] += 1
		db['window'].append(rtt)
		window_len = len(db['window'])
		if window_len > 0:
			db['avg'] = sum(db['window']) / window_len
		if rtt > db['max']:
			db['max'] = rtt
		if rtt < db['min']:
			db['min'] = rtt

	def add_rpc_req_time(self, send_time, recv_time):
		with self.lock:
			self.add_timing_locked(send_time, recv_time, self.rpc_req_timing_db)

	def add_rpc_rsp_time(self, send_time, recv_time):
		with self.lock:
			self.add_timing_locked(send_time, recv_time, self.rpc_rsp_timing_db)

	def add_method_time(self, start_time, end_time, method):
		with self.lock:
			if method not in self.method_timing_db:
				self.method_timing_db[method] = {'window': deque(maxlen=self.window_size),
												 'avg': 0.0, 'min': sys.maxsize, 'max': 0.0,
												 'total': 0}
			self.add_timing_locked(start_time, end_time, self.method_timing_db[method])

	def dump(self):
		import copy

		reqdb = copy.deepcopy(self.rpc_req_timing_db)
		rspdb = copy.deepcopy(self.rpc_rsp_timing_db)
		methodb = copy.deepcopy(self.method_timing_db)
		del(reqdb['window'])
		del(rspdb['window'])
		for k, v in methodb.items():
			del(v['window'])
		logging.critical("RPC request timing statistics")
		logging.critical(yaml.dump(reqdb,
						 Dumper=DEFwDumper, indent=2, sort_keys=False))
		logging.critical("RPC response timing statistics")
		logging.critical(yaml.dump(rspdb,
						 Dumper=DEFwDumper, indent=2, sort_keys=False))
		logging.critical("RPC method timing statistics")
		logging.critical(yaml.dump(methodb,
						 Dumper=DEFwDumper, indent=2, sort_keys=False))

g_rpc_metrics = RPCMetrics()

def get_rpc_rsp_base():
	return {'rpc': {'dst': None, 'src': None, 'type': 'results', 'rc': None,
			'statistics': {'send_time': None}}}

def get_rpc_req_base():
	return {'rpc': {'src': None, 'dst': None, 'type': None, 'script': None,
			'class': None, 'method': None, 'function': None,
			'parameters': {'args': None, 'kwargs': None},
			'statistics': {'send_time': None}}}

global_class_db = {}

def system_shutdown():
	global g_system_shutdown
	logging.debug("System Shutting down")
	g_system_shutdown = True

def is_system_up():
	global g_system_shutdown
	logging.debug(f"System is {not g_system_shutdown}")
	return not g_system_shutdown

def add_to_class_db(instance, class_id):
	if class_id in global_class_db:
		raise DEFwError("Duplicate class_id. Contention in timing")
	logging.debug(f"created instance for {type(instance).__name__} "\
			      f"with id {class_id}")
	global_class_db[class_id] = instance

def get_class_from_db(class_id):
	if class_id in global_class_db:
		return global_class_db[class_id]
	logging.debug(f"Request for class not in the database {class_id}")
	raise DEFwNotFound(f'no {class_id} in database')

def del_entry_from_class_db(class_id):
	if class_id in global_class_db:
		instance = global_class_db[class_id]
		logging.debug(f"removing instance for {type(instance).__name__} "\
					"with id {class_id}")
		del global_class_db[class_id]

def dump_class_db():
	for k, v in global_class_db.items():
		logging.debug("id = %f, name = %s" % (k, type(v).__name__))

def populate_rpc_req(src, dst, req_type, module, cname,
		     mname, class_id, *args, **kwargs):
	rpc = get_rpc_req_base()
	rpc['rpc']['src'] = src
	rpc['rpc']['dst'] = dst
	rpc['rpc']['type'] = req_type
	rpc['rpc']['module'] = module
	rpc['rpc']['class'] = cname
	rpc['rpc']['method'] = mname
	rpc['rpc']['class_id'] = class_id
	rpc['rpc']['parameters']['args'] = args
	rpc['rpc']['parameters']['kwargs'] = kwargs
	rpc['rpc']['statistics']['send_time'] = time.time()
	rpc['rpc']['statistics']['recv_time'] = 0
	return rpc

def populate_rpc_rsp(src, dst, rc, exception=None):
	rpc = get_rpc_rsp_base()
	rpc['rpc']['src'] = src
	rpc['rpc']['dst'] = dst
	if exception:
		rpc['rpc']['type'] = 'exception'
		rpc['rpc']['exception'] = exception
	else:
		rpc['rpc']['type'] = 'response'
	rpc['rpc']['rc'] = rc
	rpc['rpc']['statistics']['send_time'] = time.time()
	rpc['rpc']['statistics']['recv_time'] = 0
	return rpc

GLOBAL_PREF_DEF = {'editor': shutil.which('vim'), 'loglevel': 'critical',
		   'halt_on_exception': False, 'remote copy': False,
		   'RPC timeout': 300, 'num_intfs': MIN_IFS_NUM_DEFAULT,
		   'cmd verbosity': True}

global_pref = GLOBAL_PREF_DEF

def set_editor(editor):
	'''
	Set the text base editor to use for editing scripts
	'''
	global global_pref
	if shutil.which(editor):
		global_pref['editor'] = shutil.which(editor)
	else:
		logging.critical("%s is not found" % (str(editor)))
	save_pref()

def set_halt_on_exception(exc):
	'''
	Set halt_on_exception.
		True for raising exception and halting test progress
		False for continuing test progress
	'''
	global global_pref

	if type(exc) is not bool:
		logging.critical("Must be True or False")
		global_pref['halt_on_exception'] = False
		return
	global_pref['halt_on_exception'] = exc
	save_pref()

def set_rpc_timeout(timeout):
	'''
	Set the RPC timeout in seconds.
	That's the timeout to wait for the operation to complete on the remote end.
	'''
	global global_pref
	global_pref['RPC timeout'] = timeout
	save_pref()

def get_rpc_timeout():
	'''
	Get the RPC timeout in seconds.
	That's the timeout to wait for the operation to complete on the remote end.
	'''
	global global_pref
	return global_pref['RPC timeout']

def set_script_remote_cp(enable):
	'''
	set the remote copy feature
	If True then scripts will be remote copied to the agent prior to execution
	'''
	global global_pref
	global_pref['remote copy'] = enable
	save_pref()

def set_logging_level_helper(levelno):
	global FILE_HANDLER
	global CUSTOM_LEVELS

	root_logger = logging.getLogger('')
	for handler in root_logger.handlers[:]:
		root_logger.removeHandler(handler)

	root_logger.setLevel(levelno)

	FILE_HANDLER.setLevel(levelno)
	for filt in FILE_HANDLER.filters[:]:
		FILE_HANDLER.removeFilter(filt)
	if levelno in CUSTOM_LEVELS.values():
		FILE_HANDLER.addFilter(ExclusiveLevelFilter(levelno))

	root_logger.addHandler(FILE_HANDLER)

class ExclusiveLevelFilter(logging.Filter):
	def __init__(self, levelno):
		super().__init__()
		self.levelno = levelno

	def filter(self, record):
		return record.levelno == self.levelno or record.levelno == logging.CRITICAL

def add_logging_level(log_level, level_name):
	global CUSTOM_LEVELS

	func_name = level_name.lower()
	logging.addLevelName(log_level, level_name.upper())

	def custom_level_logger(message, *args, **kwargs):
		if logging.getLogger().isEnabledFor(log_level):
			logging.getLogger()._log(log_level, message, args, **kwargs)

	CUSTOM_LEVELS[level_name.upper()] = log_level

	setattr(logging, func_name, custom_level_logger)

def set_logging_level(level, save=True):
	'''
	Set Python log level. One of: critical, debug, error, fatal
	'''
	global global_pref
	global CUSTOM_LEVELS

	try:
		if level.upper() in CUSTOM_LEVELS:
			log_level = CUSTOM_LEVELS[level.upper()]
		else:
			log_level = getattr(logging, level.upper())
		set_logging_level_helper(log_level)
		if save:
			global_pref['loglevel'] = level
	except Exception as e:
		logging.critical(f"error encountered {e}")
		logging.critical("Log level must be one of: critical, debug, error, fatal")
	if save:
		save_pref()

def setup_log_file():
	global FILE_HANDLER

	py_log_path = cdefw_global.get_defw_tmp_dir()
	Path(py_log_path).mkdir(parents=True, exist_ok=True)
	flog_name = os.path.join(py_log_path, "defw_py.log")
	flog_mode = 'w'
	printformat = "[%(asctime)s:%(filename)s:%(lineno)s:%(funcName)s():Thread-%(thread)d]-> %(message)s"

	logging.basicConfig(filename=flog_name, filemode='w',
						format=printformat)

	FILE_HANDLER = logging.FileHandler(flog_name, mode=flog_mode)
	FILE_HANDLER.setFormatter(logging.Formatter(printformat))

def setup_log_levels():
	add_logging_level(DEFW_LOG_LEVEL_INFRA, DEFW_LOG_LEVEL_INFRA_NAME)
	add_logging_level(DEFW_LOG_LEVEL_SERVICES, DEFW_LOG_LEVEL_SERVICES_NAME)
	add_logging_level(DEFW_LOG_LEVEL_EXPERIMENTS, DEFW_LOG_LEVEL_EXPERIMENTS_NAME)
	add_logging_level(DEFW_LOG_LEVEL_WORKER, DEFW_LOG_LEVEL_WORKER_NAME)
	add_logging_level(DEFW_LOG_LEVEL_STACKTRACE, DEFW_LOG_LEVEL_STACKTRACE_NAME)
	add_logging_level(DEFW_LOG_LEVEL_APP, DEFW_LOG_LEVEL_APP_NAME)

def set_cmd_verbosity(value):
	'''
	Set the shell command verbosity to either on or off. If on, then
	all the shell commands will be written to the debug logging.
	'''
	global global_pref
	if value.upper() == 'ON':
		global_pref['cmd verbosity'] = True
	else:
		global_pref['cmd verbosity'] = False
	save_pref()

def is_cmd_verbosity():
	'''
	True if command verbosity is set, False otherwise.
	'''
	global global_pref
	return global_pref['cmd verbosity']

def load_pref():
	'''
	Load the DEFw preferences.
		editor - the editor of choice to use for editing scripts
		halt_on_exception - True to throw an exception on first error
				    False to continue running scripts
		log_level - Python log level. One of: critical, debug, error, fatal
	'''
	global GLOBAL_PREF_DEF
	global global_pref

	try:
		global_pref_file = os.environ['DEFW_PREF_PATH']
	except:
		global_pref_file = os.path.join(cdefw_global.get_defw_tmp_dir(), 'defw_pref.yaml')

	if os.path.isfile(global_pref_file):
		with open(global_pref_file, 'r') as f:
			global_pref = yaml.load(f, Loader=yaml.FullLoader)
			if not global_pref:
				global_pref = GLOBAL_PREF_DEF
			else:
				#compare with the default and fill in any entries
				#which might not be there.
				for k, v in GLOBAL_PREF_DEF.items():
					if not k in global_pref:
						global_pref[k] = v
	save_pref()
	return global_pref

def save_pref():
	'''
	Save the DEFw preferences.
		editor - the editor of choice to use for editing scripts
		halt_on_exception - True to throw an exception on first error
				    False to continue running scripts
		log_level - Python log level. One of: critical, debug, error, fatal
	'''
	global global_pref

	try:
		global_pref_file = os.environ['DEFW_PREF_PATH']
	except:
		global_pref_file = os.path.join(cdefw_global.get_defw_tmp_dir(), 'defw_pref.yaml')

	with open(global_pref_file, 'w') as f:
		f.write(yaml.dump(global_pref, Dumper=DEFwDumper, indent=2, sort_keys=False))

	with open(global_pref_file, 'r') as f:
		p = yaml.load(f, Loader=yaml.FullLoader)
		set_logging_level(p['loglevel'], save=False)

def dump_pref():
	global global_pref
	print(yaml.dump(global_pref, Dumper=DEFwDumper, indent=2, sort_keys=True))

