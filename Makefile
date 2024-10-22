REGISTRY         ?= docker.io
ORG              ?= ansibleplaybookbundle
TAG              ?= $(shell git rev-parse --short HEAD)
BROKER_IMAGE     ?= $(REGISTRY)/$(ORG)/origin-ansible-service-broker:${TAG}
ANSIBLE_ROLE_DIR ?= ansible_role
APB_DIR          ?= ${ANSIBLE_ROLE_DIR}/apb
OPERATOR_DIR     ?= operator
OP_BUILD_DIR     ?= ${OPERATOR_DIR}/build
OP_DEPLOY_DIR    ?= ${OPERATOR_DIR}/deploy
OP_CRD_DIR       ?= ${OP_DEPLOY_DIR}/crds
APB_ORG          ?= automationbroker
APB_IMAGE        ?= ${REGISTRY}/${APB_ORG}/automation-broker-apb:${TAG}
OPERATOR_ORG     ?= automationbroker
OPERATOR_IMAGE   ?= ${REGISTRY}/${OPERATOR_ORG}/automation-broker-operator:${TAG}
VARS             ?= ""
BUILD_DIR        = "${GOPATH}/src/github.com/openshift/ansible-service-broker/build"
PREFIX           ?= /usr/local
BROKER_CONFIG    ?= $(PWD)/etc/generated_local_development.yaml
SOURCE_DIRS      = cmd pkg
SOURCES          := $(shell find . -name '*.go' -not -path "*/vendor/*")
PACKAGES         := $(shell go list ./pkg/...)
SVC_ACCT_DIR     := /var/run/secrets/kubernetes.io/serviceaccount
KUBERNETES_FILES := $(addprefix $(SVC_ACCT_DIR)/,ca.crt token tls.crt tls.key)
COVERAGE_SVC     := travis-ci
.DEFAULT_GOAL    := build
ASB_DEBUG_PORT   := 9000
AUTO_ESCALATE    ?= false
NAMESPACE        ?= openshift-ansible-service-broker
TEMPLATE_CMD      = sed 's|REPLACE_IMAGE|${IMAGE}|g; s|REPLACE_NAMESPACE|${NAMESPACE}|g; s|Always|IfNotPresent|'
DEPLOY_OBJECTS    = ${OP_DEPLOY_DIR}/namespace.yaml ${OP_DEPLOY_DIR}/service_account.yaml ${OP_DEPLOY_DIR}/role.yaml ${OP_DEPLOY_DIR}/role_binding.yaml
DEPLOY_OPERATOR   = ${OP_DEPLOY_DIR}/operator.yaml
DEPLOY_CRDS       = ${OP_CRD_DIR}/osb_v1alpha1_ansibleservicebroker_crd.yaml ${OP_CRD_DIR}/bundlebindings.crd.yaml ${OP_CRD_DIR}/bundle.crd.yaml ${OP_CRD_DIR}/bundleinstances.crd.yaml
DEPLOY_CRS        = ${OP_CRD_DIR}/osb_v1alpha1_ansibleservicebroker_cr.yaml

vendor: ## Install or update project dependencies
	@dep ensure

broker: $(SOURCES) ## Build the broker
	go build -i -ldflags="-s -w" ./cmd/broker

migration: $(SOURCES)
	go build -i -ldflags="-s -w" ./cmd/migration

dashboard-redirector: $(SOURCES)
	go build -i -ldflags="-s -w" ./cmd/dashboard-redirector

build: broker ## Build binary from source
	@echo > /dev/null

generate: ## regenerate mocks
	go get github.com/vektra/mockery/.../
	@go generate ./...

lint: ## Run golint
	@golint -set_exit_status $(addsuffix /... , $(SOURCE_DIRS))

fmt: ## Run go fmt
	@gofmt -d $(SOURCES)

fmtcheck: ## Check go formatting
	@gofmt -l $(SOURCES) | grep ".*\.go"; if [ "$$?" = "0" ]; then exit 1; fi

test: ## Run unit tests
	@go test -cover ./pkg/...

coverage-all.out: $(PACKAGES)
	@grep -q -F 'mode: count' coverage-all.out || sed -i '1i mode: count' coverage-all.out

$(PACKAGES): $(SOURCES)
	@touch coverage.out
	@go test -coverprofile=coverage.out -covermode=count $@ && tail -n +2 coverage.out >> coverage-all.out;

test-coverage-html: coverage-all.out ## checkout the coverage locally of your tests
	@go tool cover -html=coverage-all.out

ci-test-coverage: coverage-all.out ## CI test coverage, upload to coveralls
	@goveralls -coverprofile=coverage-all.out -service $(COVERAGE_SVC)

vet: ## Run go vet
	@go tool vet ./cmd ./pkg

check: fmtcheck vet lint build test ## Pre-flight checks before creating PR

run: broker
	@./scripts/run_local.sh ${BROKER_CONFIG}

# NOTE: Must be explicitly run if you expect to be doing local development
# Basically brings down the broker pod and extracts token/cert files to
# /var/run/secrets/kubernetes.io/serviceaccount
# Resetting a catasb cluster WILL generate new certs, so you will have to
# run prep-local again to export the new certs.
prep-local: ## Prepares the local dev environment
	@./scripts/prep_local_devel_env.sh

build-dev: ## Build a docker image with the broker binary for development
	docker cp $(shell docker create docker.io/philipgough/dlv:centos):/go/bin/dlv ${BUILD_DIR}
	env GOOS=linux go build -i -gcflags="-N -l" -o ${BUILD_DIR}/broker ./cmd/broker
	env GOOS=linux go build -i -ldflags="-s -s" -o ${BUILD_DIR}/migration ./cmd/migration
	env GOOS=linux go build -i -ldflags="-s -s" -o ${BUILD_DIR}/dashboard-redirector ./cmd/dashboard-redirector
	docker build -f ${BUILD_DIR}/Dockerfile-localdev -t ${BROKER_IMAGE} ${BUILD_DIR} --build-arg DEBUG_PORT=${ASB_DEBUG_PORT}
	@echo ""
	@echo "Remember you need to push your image before calling make deploy or updating deployment config"
	@echo "    docker push ${BROKER_IMAGE}"
	@echo ""
	@echo "To remotely debug the container, update the deployment config and run the following before connecting the debugger"
	@echo "    ./scripts/prep_debug_env.sh ${ASB_DEBUG_PORT} <broker-namespace> <broker-deployment-name> "

build-image: ## Build the broker (from canary)
	docker build -f ${BUILD_DIR}/Dockerfile-canary --build-arg VERSION=${TAG} --build-arg DEBUG_PORT=${ASB_DEBUG_PORT} -t ${BROKER_IMAGE} .

build-apb: ## Build the broker apb
ifeq ($(TAG),canary)
	docker build -f ${APB_DIR}/Dockerfile-canary --build-arg VERSION=${TAG} --build-arg APB=${TAG} -t ${APB_IMAGE} ${ANSIBLE_ROLE_DIR}
else ifeq ($(TAG),nightly)
	docker build -f ${APB_DIR}/Dockerfile-nightly --build-arg VERSION=${TAG} --build-arg APB=${TAG} -t ${APB_IMAGE} ${ANSIBLE_ROLE_DIR}
else ifneq (,$(findstring release,$(TAG)))
	docker build -f ${APB_DIR}/Dockerfile-canary --build-arg VERSION=${TAG} --build-arg APB=${TAG} -t ${APB_IMAGE} ${ANSIBLE_ROLE_DIR}
else
	docker build -f ${APB_DIR}/Dockerfile-canary --build-arg VERSION=${TAG} -t ${APB_IMAGE} ${ANSIBLE_ROLE_DIR}
endif

build-operator: ## Build the broker operator image
	docker build -f ${OP_BUILD_DIR}/Dockerfile -t ${OPERATOR_IMAGE} ${OPERATOR_DIR}

$(DEPLOY_OBJECTS) $(DEPLOY_CRDS) $(DEPLOY_OPERATOR) $(DEPLOY_CRS):
	@${TEMPLATE_CMD} $@ | kubectl create -f - ||:

deploy-objects: $(DEPLOY_OBJECTS) ## Create the operator namespace and RBAC in cluster

deploy-crds: $(DEPLOY_CRDS) ## Create operator's custom resources
	sleep 1

deploy-cr: $(DEPLOY_CRS) ## Create a CR for the operator

deploy-operator: deploy-objects deploy-crds $(DEPLOY_OPERATOR) deploy-cr ## Deploy everything for the operator in cluster

undeploy-operator: ## Delete everything for the operator from the cluster
	@${TEMPLATE_CMD} $(DEPLOY_OBJECTS) $(DEPLOY_OPERATOR) $(DEPLOY_CRDS) $(DEPLOY_CRS) | kubectl delete -f - ||:

publish: build-image build-apb
ifdef PUBLISH
	docker push ${BROKER_IMAGE}
	docker push ${APB_IMAGE}
else
	@echo "Must set PUBLISH, here be dragons"
endif

clean: ## Clean up your working environment
	@rm -f broker
	@rm -f migration
	@rm -f build/broker
	@rm -f build/migration
	@rm -f adapters.out apb.out app.out auth.out broker.out coverage-all.out coverage.out handler.out registries.out validation.out

really-clean: clean cleanup-ci ## Really clean up the working environment
	@rm -f $(KUBERNETES_FILES)

deploy: build-dev build-apb ## Deploy a built broker docker image to a running cluster
	APB_IMAGE=${APB_IMAGE} BROKER_IMAGE=${BROKER_IMAGE} ACTION="provision" ./scripts/deploy.sh

undeploy: build-apb ## Uninstall a deployed broker from a running cluster
	APB_IMAGE=${APB_IMAGE} BROKER_IMAGE=${BROKER_IMAGE} ACTION="deprovision" ./scripts/deploy.sh

## Continuous integration stuff
ci: ## Run the broker ci
	APB_IMAGE=${APB_IMAGE} BROKER_IMAGE=${BROKER_IMAGE} ACTION="test" ./scripts/deploy.sh

help: ## Show this help screen
	@echo 'Usage: make <OPTIONS> ... <TARGETS>'
	@echo ''
	@echo 'Available targets are:'
	@echo ''
	@grep -E '^[ a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ''

wtf: ## Use this target to help you diagnose development problems
	@echo ""
	@echo "Hi, this task helps you get out your frustration when"
	@echo "writing code.  Please feel free to bop your cubemate"
	@echo "in the head for some comic relief."
	@echo ""

openshift-ci-test-container:
	yum -y install ansible-lint
	mkdir -p /opt/ansible/roles/
	cp -r operator/roles/ansible-service-broker /opt/ansible/roles/ansible-service-broker
	cp -r operator/watches.yaml /opt/ansible/watches.yaml
	cp -r operator/playbook.yaml /opt/ansible/playbook.yaml
	go get -u github.com/golang/dep/cmd/dep
	make vendor

openshift-ci-operator-lint:
	ANSIBLE_LOCAL_TEMP=/tmp/.ansible ansible-lint /opt/ansible/playbook.yaml

openshift-ci-make-rpm:
	yum -y install tito yum-utils
	yum-builddep -y ./ansible-service-broker.spec
	tito build --test --rpm
	mkdir /tmp/rpms
	cp /tmp/tito/noarch/ansible-service-broker-selinux* /tmp/rpms/ansible-service-broker-selinux.rpm
	cp /tmp/tito/noarch/ansible-service-broker-container-scripts* /tmp/rpms/ansible-service-broker-container-scripts.rpm
	cp /tmp/tito/x86_64/ansible-service-broker-* /tmp/rpms/ansible-service-broker.rpm

.PHONY: run build-image clean deploy undeploy ci cleanup-ci lint build vendor fmt fmtcheck test vet help test-cover-html prep-local wtf openshift-ci-test-container openshift-ci-operator-lint openshift-ci-make-rpm $(DEPLOY_OBJECTS) $(DEPLOY_OPERATOR) $(DEPLOY_CRDS) $(DEPLOY_CRS)
