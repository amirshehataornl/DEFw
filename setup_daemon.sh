export DEFW_PATH=/lustre/orion/gen008/proj-shared/qhpc/srikar/qfw_related/QFw/DEFw/
export DEFW_CONFIG_PATH=$DEFW_PATH/python/config/defw_generic.yaml
export LD_LIBRARY_PATH=$DEFW_PATH/src/
export DEFW_AGENT_NAME=testd
export DEFW_LISTEN_PORT=8092
export DEFW_TELNET_PORT=8092
export DEFW_AGENT_TYPE=agent
export DEFW_LOG_LEVEL=all
export DEFW_LOG_DIR=/tmp/${DEFW_AGENT_NAME}
export DEFW_ONLY_LOAD_MODULE=resmgr
export DEFW_SHELL_TYPE=daemon
export DEFW_PARENT_ADDR=127.0.0.1
export DEFW_PARENT_PORT=8090
export DEFW_PARENT_NAME=resmgr

