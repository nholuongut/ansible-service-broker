#!/bin/bash
source "$(dirname "${BASH_SOURCE}")/lib/init.sh"

BROKER_CMD=${ASB_ROOT}/broker

asb::load_vars
asb::validate_var "BROKER_CMD" $BROKER_CMD
asb::validate_var "CLUSTER_HOST" $CLUSTER_HOST
asb::validate_var "CLUSTER_PORT" $CLUSTER_PORT

export KUBERNETES_SERVICE_HOST=${CLUSTER_HOST}
export KUBERNETES_SERVICE_PORT=${CLUSTER_PORT}

BROKER_CONFIG=$GENERATED_BROKER_CONFIG
if [ ! -z "$1" ]; then
  BROKER_CONFIG="$1"
fi

if [ -z "${BROKER_CONFIG}" ]; then
  echo "Please specify a broker configuration file to run"
  exit 1
fi

echo "Running ${BROKER_CMD} --config ${BROKER_CONFIG}"
${BROKER_CMD} --config ${BROKER_CONFIG}
