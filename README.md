# Ansible Service Broker
![](https://i.imgur.com/waxVImv.png)
### [View all Roadmaps](https://github.com/nholuongut/all-roadmaps) &nbsp;&middot;&nbsp; [Best Practices](https://github.com/nholuongut/all-roadmaps/blob/main/public/best-practices/) &nbsp;&middot;&nbsp; [Questions](https://www.linkedin.com/in/nholuong/)
<br/>

# Getting Started on Kubernetes

[Minikube](https://kubernetes.io/docs/getting-started-guides/minikube/) makes
it easy to get started with Kubernetes. Run the commands below individually or
as a script to start a minikube VM that includes the service catalog and the
broker. If you already have a Kubernetes cluster, skip the ``minikube`` command
and proceed with the remaining ones as applicable.

## Prerequisites:

* [Install](https://kubernetes.io/docs/tasks/tools/install-minikube/) minikube
  and kubectl. Make sure ``minikube start`` and ``minikube delete`` are
  working.
* [Install](https://docs.helm.sh/using_helm/#install-helm) the ``helm`` binary.
* Clone the broker's [GitHub repository](https://github.com/openshift/ansible-service-broker)

## Install

Run the following from the root of the cloned git repository.

```bash
#!/bin/env bash

# Adjust the version to your liking. Follow installation docs
# at https://github.com/kubernetes/minikube.
minikube start --bootstrapper kubeadm --kubernetes-version v1.9.4

# Install helm and tiller. See documentation for obtaining the helm
# binary. https://docs.helm.sh/using_helm/#install-helm
helm init

# Wait until tiller is ready before moving on
until kubectl get pods -n kube-system -l name=tiller | grep 1/1; do sleep 1; done

kubectl create clusterrolebinding tiller-cluster-admin --clusterrole=cluster-admin --serviceaccount=kube-system:default

# Adds the chart repository for the service catalog
helm repo add svc-cat https://svc-catalog-charts.storage.googleapis.com

# Installs the service catalog
helm install svc-cat/catalog --name catalog --namespace catalog

# Wait until the catalog is ready before moving on
until kubectl get pods -n catalog -l app=catalog-catalog-apiserver | grep 2/2; do sleep 1; done
until kubectl get pods -n catalog -l app=catalog-catalog-controller-manager | grep 1/1; do sleep 1; done

./scripts/run_latest_k8s_build.sh
```

## Use

Once everything is installed, you can interact with the service catalog using
the ``svcat`` command. Learn how to install and use it
[here](https://github.com/kubernetes-incubator/service-catalog/tree/master/cmd/svcat).

# Getting Started on OpenShift

There are a few different ways to quickly get up and running with a cluster + ansible-service-broker:

* `oc cluster up`
* Alternatively, [you can use minishift and install the broker with our addon, documented here](https://github.com/minishift/minishift-addons/tree/master/add-ons/ansible-service-broker).

Let's walk through an `oc cluster up` based setup.

## Prerequisites
1. You will need a system setup for local [OpenShift Origin Cluster Management](https://github.com/openshift/origin/blob/master/docs/cluster_up_down.md)
    * Your OpenShift Client binary (`oc`) must be `>=` [v3.7.0-rc.0](https://github.com/openshift/origin/releases/tag/v3.7.0-rc.0)

2. If you are using minishift you should look at the [minishift](https://github.com/openshift/ansible-service-broker/blob/master/docs/minishift.md) documentation to get the ansible service broker deployed and running.

## Deploy a v3.10+ Openshift Origin Cluster with the Ansible Service Broker
[![Watch the full asciicast](docs/images/oc-enable.gif)](https://asciinema.org/a/qWbzLFt1GyWNYwH1TPsXJGAKr)

* Starting with Origin v3.10  it's as simple as running `oc cluster up --enable=service-catalog,automation-service-broker`.
  * Running `oc cluster up --enable` will give you a full list of features. You may find it helpful to also add `persistent-volumes`, `registry`, `rhel-imagestreams`, `router`, etc.
  * You might also want to add a public-hostname and routing-suffix to make it easier to access your provisioned applications as well.
  * Complete example would look like `oc cluster up --routing-suffix=172.17.0.1.nip.io --public-hostname=172.17.0.1.nip.io --enable=service-catalog,router,registry,web-console,persistent-volumes,rhel-imagestreams,automation-service-broker`

## Deploy a Pre v3.10 OpenShift Origin Cluster with the Ansible Service Broker

1. Download and execute our [run_latest_build.sh](https://raw.githubusercontent.com/openshift/ansible-service-broker/master/scripts/run_latest_build.sh) script

    Origin Version 3.7:
    ```
    wget https://raw.githubusercontent.com/openshift/ansible-service-broker/master/scripts/run_latest_build.sh
    chmod +x run_latest_build.sh
    ./run_latest_build.sh
    ```

1. At this point you should have a running cluster with the [service-catalog](https://github.com/kubernetes-incubator/service-catalog/) and the Ansible Service Broker running.

**Provision an instance of MediaWiki and PostgreSQL**
1. Log into OpenShift Web Console
1. Create a new project 'apb-demo'
1. Provision [MediaWiki APB](https://github.com/ansibleplaybookbundle/mediawiki-apb)
    * Select the 'apb-demo' project
    * Enter a 'MediaWiki Admin User Password': 's3curepw'
    * Click 'Create'
1. Provision [PostgreSQL APB](https://github.com/ansibleplaybookbundle/postgresql-apb)
    * Select the 'apb-demo' project
    * Leave 'PostgreSQL Password' blank, a random password will be generated
    * Choose a 'PostgreSQL Version'; either version will work.
    * Click 'Next'
    * Select 'Do not bind at this time' and then 'Create'
1. Wait until both APBs have finished deploying, and you see pods running for MediaWiki and PostgreSQL

**Bind MediaWiki to PostgreSQL**
1. Bind MediaWiki to PostgreSQL
    * Click on kebab menu for PostgreSQL
    * Select 'Create Binding' and then 'Bind'
    * Click on the link to the created secret
    * Click 'Add to Application'
    * Select 'mediawiki123' and 'Environment variables'
    * Click 'Save'
1. View the route for MediaWiki and verify the wiki is up and running.
    * Observe that mediawiki123 is on deployment '#2', having been automatically redeployed

# Versioning

Our release versions align with
[openshift/origin](https://github.com/openshift/origin/). For more detailed
information see our [version document](docs/versioning.md).

## Release Dates

| Kubernetes | OpenShift | Ansible Service Broker | Feature Freeze | Release Date |
|:----------:|:---------:|:----------------------:|:--------------:|:------------:|
|    1.7     |    3.7    |       release-1.0      |    2017/9/4    |   2017/11/16 |
|    1.9     |    3.9    |       release-1.1      |    2018/1/4    |   2018/3/28  |
|    1.10    |    3.10   |       release-1.2      |    2018/4/4    |   2018/7/4*  |
|    1.11    |    3.11   |       release-1.3      |    2018/7/4*   |   2018/10/4* |
|    1.12    |    4.0    |       release-1.4      |    2018/10/4*  |   2019/1/4*  |


# Compatibility

## APB Compatibility Matrix

| ansible-service-broker                      | APB runtime 1 | APB runtime 2 |
|---------------------------------------------|---------------|---------------|
| ansible-service-broker release-1.0, v3.7    |       ✓       |       X       |
| ansible-service-broker release-1.1, v3.9    |       ✓       |       ✓       |
| ansible-service-broker HEAD                 |       ✓       |       ✓       |

Key:

* `✓` Supported.
* `X` Will not work. Not supported.

Ansible Playbook Bundle images are built on the [apb-base
image](https://github.com/ansibleplaybookbundle/apb-base). Starting with
apb-base 1.1, a new APB runtime was introduced and captured in the label
[`com.redhat.apb.runtime`](https://github.com/ansibleplaybookbundle/apb-base/blob/master/Dockerfile-latest#L3).
Currently, there are two APB runtime versions:

* APB runtime 1 - all APBs tagged `release-1.0` as well as APBs with no
  `"com.redhat.apb.runtime"` label.
* APB runtime 2 - all APBs tagged `release-1.1` as well as APBs with label
  `"com.redhat.apb.runtime"="2"`.

You can examine the runtime of a
particular APB with `docker inspect $APB --format "{{ index
.Config.Labels \"com.redhat.apb.runtime\" }}"`. An APB without a
`"com.redhat.apb.runtime"` label is APB runtime 1. For example:

```
$ docker inspect docker.io/ansibleplaybookbundle/mediawiki-apb:latest --format "{{ index .Config.Labels \"com.redhat.apb.runtime\" }}"
2

# No label on release-1.0
$ docker inspect docker.io/ansibleplaybookbundle/mediawiki-apb:release-1.0 --format "{{ index .Config.Labels \"com.redhat.apb.runtime\" }}"
```

# Contributing

First, **start with the** [Contributing Guide](CONTRIBUTING.md).

Contributions are welcome. Open issues for any bugs or problems you may run into,
ask us questions on [IRC (Freenode): #asbroker](http://webchat.freenode.net/?channels=%23asbroker),
or see what we are working on at our [Trello Board](https://trello.com/b/50JhiC5v/ansible-service-broker).

If you want to run the test suite, when you are ready to submit a PR for example,
make sure you have your development environment setup, and from the root of the
project run:

```
# Check your go source files (gofmt, go vet, golint), build the broker, and run unit tests
make check

# Get helpful information about our make targets
make help
```

# 🚀 I'm are always open to your feedback.  Please contact as bellow information:
### [Contact ]
* [Name: nho Luong]
* [Skype](luongutnho_skype)
* [Github](https://github.com/nholuongut/)
* [Linkedin](https://www.linkedin.com/in/nholuong/)
* [Email Address](luongutnho@hotmail.com)

![](https://i.imgur.com/waxVImv.png)
![](Donate.png)
[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/nholuong)

# License
* Nho Luong (c). All Rights Reserved.🌟
