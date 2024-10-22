# Build
![](https://i.imgur.com/waxVImv.png)
### [View all Roadmaps](https://github.com/nholuongut/all-roadmaps) &nbsp;&middot;&nbsp; [Best Practices](https://github.com/nholuongut/all-roadmaps/blob/main/public/best-practices/) &nbsp;&middot;&nbsp; [Questions](https://www.linkedin.com/in/nholuong/)
<br/>

Automation Broker APB
=========

Ansible Role for installing (and uninstalling) the
[automation-broker](http://automation-broker.io) in a Kubernetes/OpenShift
Cluster with the
[service-catalog](https://github.com/kubernetes-incubator/service-catalog).

Requirements
------------

- [openshift-restclient-python](https://github.com/openshift/openshift-restclient-python)
- [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/)

Role Variables
--------------

See [defaults/main.yml](defaults/main.yml).

Usage
-----

Until this project is configured to publish `docker.io/automation-broker/automation-broker-apb`
you will want to first build the image:

```
$ docker build -t automation-broker-apb -f Dockerfile .
```

## OpenShift/Kubernetes

You may replace `kubectl` for `oc` in the case you have the origin client
installed but not the kubernetes client.

**Note:** You will likely need to be an administrator (ie. `system:admin` in OpenShift).
If you don't have sufficient permissions to create the `clusterrolebinding`,
the provision/deprovision will fail.

```
$ kubectl create -f install.yaml
```

This will create the serviceaccount, clusterrolebinding, and job to install the
broker.

Example Playbook
----------------

See [playbooks/provision.yml](playbooks/provision.yml).

