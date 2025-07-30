export DEFW_PATH=/lustre/orion/gen008/proj-shared/qhpc/srikar/qfw_related/QFw/DEFw
export DEFW_CONFIG_PATH=$DEFW_PATH/python/config/defw_generic.yaml
export LD_LIBRARY_PATH=$DEFW_PATH/src/:$LD_LIBRARY_PATH
export DEFW_AGENT_NAME=qrc_nwqsim
export DEFW_LISTEN_PORT=9095
export DEFW_AGENT_TYPE=service
#export DEFW_PARENT_ADDR=10.129.3.9
export DEFW_PARENT_ADDR=127.0.0.1
export DEFW_PARENT_PORT=8090
export DEFW_PARENT_NAME=resmgr
export DEFW_PARENT_HNAME=login1
export DEFW_SHELL_TYPE=interactive
export DEFW_LOG_LEVEL=all
export DEFW_LOG_DIR=/tmp/${DEFW_AGENT_NAME}
export DEFW_ONLY_LOAD_MODULE=svc_qrc

