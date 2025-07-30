# Distributed Execution Framework

**Environment Variables**
- DEFW_NO_RESMGR: No resource manager available
- DEFW_CONFIG_PATH: Path to YAML configuration file
- LD_LIBRARY_PATH: Path DEFw libraries
- DEFW_PATH: Path to the DEFw top directory
- DEFW_AGENT_NAME: DEFw instance name. Should be unique
- DEFW_LISTEN_PORT: port the agent listens on
- DEFW_AGENT_TYPE: type of the agent. One of: agent, service or resmgr
- DEFW_PARENT_ADDR: The address of the parent DEFw should connect to
- DEFW_PARENT_PORT: The port of the parent DEFw should connect on
- DEFW_PARENT_NAME: The parent name
- DEFW_PARENT_HNAME: The parent hostname
- DEFW_SHELL_TYPE: How to run the DEFw. One of: interactive, cmdline or daemon
- DEFW_ONLY_LOAD_MODULE: Comma separated list of modules to load
- DEFW_LOG_LEVEL: debug level. One of: all, message, debug, error
- DEFW_LOG_DIR: Directory where logging files and other data is stored. If
                executing in a distributed environment, this needs to be in a globally
                shared file space. Processes on different nodes might need to access that
                directory

Beside DEFW_CONFIG_PATH all the other environment variables are used in
the YAML configuration file directly. This allows us to have only one YAML
file used for everything.

**These are QFw environment variables needed**

- QFW_BASE_QRC_PORT: (optional. Defaults to 9000) The base QRC listen port
- QFW_NUM_QRC: (optional. Defaults to 1) The number of QRC processes to start
- QFW_QRC_BIN_PATH: (optional. Defaults to 'defwp') The binary path to the QRC
- QFW_STARTUP_TIMEOUT: (optional. Defaults to 40s) Timeout used in the QFW for waiting for processes to startup
- QFW_MODULE_USE_PATH: The module path to load for execution of simulators
- QFW_QPM_ASSIGNED_HOSTS: The set of hosts assigned to this QPM
- QFW_CIRCUIT_RUNNER_PATH: Path to the circuit runner
- QFW_LAUNCHER_BIN: The launcher. Ex: mpirun or srun or prun
