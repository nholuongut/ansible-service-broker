# Ansible Service Broker Configuration Examples

The behavior of the broker is largely dictated by the broker's configuration
file loaded on startup and contains:

- [Registry Configuration](#registry-configuration)
- [DAO Configuration](#dao-configuration)
- [Log Configuration](#log-configuration)
- [OpenShift Configuration](#openshift-configuration)
- [Broker Configuration](#broker-configuration)
- [Secrets Configuration](#secrets-configuration)

## Registry Configuration

The Registry section will allow you to define the registries that the broker should look at
for APBs. All the registry config options are defined below

| field         | description                                                                                                                      | required |
|---------------|----------------------------------------------------------------------------------------------------------------------------------|----------|
| name            | The name of the registry. Used by the broker to identify APBs from this registry.                                                |     Y    |
| auth_type       | How the broker should read the credentials                                                                                       |     N    |
| auth_name       | Name of secret/file credentials should be read from. Used when auth_type is set to `secret` or `file`                            |     N    |
| user            | The username for authenticating to the registry                                                                                  |     N    |
| pass            | The password for authenticating to the registry                                                                                  |     N    |
| org             | The namespace/organization that the image is contained in                                                                        |     N    |
| type            | The type of registry. The only adapters so far are mock, RHCC, openshift, dockerhub, and local_openshift.                        |     Y    |
| namespaces      | The list of namespaces to configure the local_openshift registry adapter with. By default a user should use `openshift`          |     N    |
| url             | The url that is used to retrieve image information. Used extensively for RHCC while the docker hub adapter uses hard-coded URLs. |     N    |
| fail_on_error   | Should this registry fail the bootstrap request if it fails. will stop the execution of other registries loading.                |     N    |
| white_list      | The list of regular expressions used to define which image names should be allowed through. Must have a white list to allow APBs to be added to the catalog. The most permissive regular expression that you can use is `.*-apb$` if you would want to retrieve all APBs in a registry.                                     |     N    |
| black_list      | The list of regular expressions used to define which images names should never be allowed through.                               |     N    |
| skip_verify_tls | Should this registry verify TLS with connections. | |    N     |
| images          | The list of images to be used with OpenShift Registry.                                                                           |     N    |
| tag             | The tag to define which version of the images should be pulled. Default is `latest`, can be set to `canary` to pull most recent but unstable images. |     N    |

For filter please look at the [filtering documentation](filtering_apbs.md).

### Production

The Production broker configuration is designed to be pointed at a trusted
container distribution registry.

```
registry:
  - name: rhcc
    type: rhcc
    url: http://rhcc.redhat.com/api
    user: USER
    pass: PASS
  - type: local_openshift
    name: lo
    namespaces:
      - openshift
```

### Storing registry credentials in a secret/file

```
registry:
  - name: rhcc
    type: rhcc
    url: registry.access.redhat.com
    auth_type: secret
    auth_name: asb-auth-secret
```
The associated secret should have the values `username` and `password` defined. When using a secret you must ensure that `openshift.namespace` is also defined. This is where the secret will be read from. (`ansible-service-broker` namespace when using the template).

```
registry:
  - name: rhcc
    type: rhcc
    url: registry.access.redhat.com
    auth_type: file
    auth_name: /tmp/auth-credentials
```

The following is an example of using a YAML file to define credentials.
```
$ cat /tmp/auth-credentials
---
username: leto
password: spicemustflow
```

### Development

The developer configuration is primarily used by developers working on the
broker. Set the registry name to 'dev' and 'devbroker' field to 'true' to enable
developer settings.

```
registry:
  name: dev
```

```
broker:
  devbroker: true
```

### Mock Registry
Using a Mock registry is useful for reading local APB specs. Instead of going
out to a registry to search for image specs, use a list of local specs. Set the
name of the registry to 'mock' to use the Mock registry.

```
registry:
  - name: mock
    type: mock
```

### Dockerhub Registry
Using the dockerhub registry will allow you to load APBs from  a specific organization dockerhub. A good example is the examples [organization](https://hub.docker.com/u/ansibleplaybookbundle/).

```yaml
registry:
  - name: dockerhub
    type: dockerhub
    org: ansibleplaybookbundle
    user: user
    pass: password
    white_list:
      - ".*-apb$"
```

### Local OpenShift Registry
Using the local openshift registry will allow you to load APBs from the internal registry. The administrator can configure which namespaces they want to look for published APBs.
```yaml
registry:
  - type: local_openshift
    name: lo
    namespaces:
      - openshift
    white_list:
      - ".*-apb$"
```

### Helm Chart Repository

Using a Helm registry will allow you to consume Helm
Charts from a Helm Chart Respository. For example:

```yaml
registry:
  - name: stable
    type: helm
    url: "https://kubernetes-charts.storage.googleapis.com"
    runner: "docker.io/automationbroker/helm-runner:latest"
    white_list:
      - ".*"
```

**NOTE**: A heavy percentage of helm charts from the stable repository are not
well suited for OpenShift. For more information see
[here](https://github.com/ansibleplaybookbundle/helm2bundle/wiki/Known-Issues).

### Ansible Galaxy Registry

Using the [Ansible Galaxy](https://galaxy.ansible.com) will allow you to
consume APB roles in Galaxy. The configuration would look like:

```yaml
registry:
  - type: galaxy
    name: galaxy
    url: https://galaxy.ansible.com
    # Optional:
    # org: ansibleplaybookbundle
    runner: docker.io/ansibleplaybookbundle/apb-base:latest
    white_list:
      - ".*"
```

### Red Hat Container Catalog (RHCC) Registry
Using the RHCC (Red Hat Container Catalog) registry will allow you to load APBs that are published to this type of [registry](https://access.redhat.com/containers).

```yaml
registry:
  - name: rhcc
    type: rhcc
    url: <rhcc url>
    white_list:
      - ".*-apb$"
    skip_verify_tls: false
```

If `skip_verify_tls` is `true`, the TLS certificate of the remote registry will not be verified. Defaults to `false`.

### OpenShift Registry
Using the OpenShift registry will allow you to load APBs that are published to this type of [registry](http://www.projectatomic.io/registry/).

```yaml
registry:
  - name: openshift
    type: openshift
    user: <RH_user>
    pass: <RH_pass>
    url: <openshift_url>
    images:
      - <image_1>
      - <image_2>
    white_list:
      - ".*-apb$"
```

There is a limitation when working with the OpenShift Registry right now. We have no capability to search the registry so we require that the user configure the broker with a list of images they would like to source from for when the broker bootstraps. The image name must be the fully qualified name without the registry URL.

### Red Hat Connect Partner Registry

Third-party images in the Red Hat Container Catalog are served from the Red Hat Connect Partner Registry (registry.connect.redhat.com). The `PartnerRhccAdapter` allows the broker to be bootstrapped from this, "Red Hat Connect Partner Registry" to retrieve a list of APBs and load their specs. Note this is an authenticated repository and will require authentication credentials to access.

```yaml
registry:
  - name: partner_reg
    type: partner_rhcc
    url:  https://registry.connect.redhat.com
    user: <registry-user>
    pass: <registry-password>
    white_list:
      - ".*-apb$"
```

The partner registry requires authentication for pulling images.  This can be achieved by running the following command on every node in your existing OpenShift cluster:

```bash
docker --config=/var/lib/origin/.docker login -u <registry-user> -p <registry-password> registry.connect.redhat.com
```

### API V2 Registry

Registries that implements the Docker [Registry HTTP API V2](https://docs.docker.com/registry/spec/api/) protocol can be configured with the `apiv2` registry adapter as follows

```yaml
registry:
  - name: <registry_name>
    type: apiv2
    url:  <registry_url>
    user: <registry-user>
    pass: <registry-password>
    white_list:
      - ".*-apb$"
```


If the registry requires authentication for pulling images, this can be achieved by running the following command on every node in your existing cluster:

```bash
docker --config=/var/lib/origin/.docker login -u <registry-user> -p <registry-password> <registry_url>
```

### Quay Registry

Using the Quay registry will allow you to load APBs that are published to the [CoreOS Quay Registry](https://quay.io/about/).  If an authentication `token` is provided, private repositories (*which the token is configured to access*) will also load as well as any public repositories in the specified `org`.

```yaml
registry:
  - name: quay_reg
    type: quay
    url:  https://quay.io
    token: <for_private_repos>
    org: <your_org>
    white_list:
      - ".*-apb$"
```

The Quay registry requires authentication for pulling images.  This can be achieved by running the following command on every node in your existing cluster:

```bash
docker --config=/var/lib/origin/.docker login -u <registry-user> -p <registry-password> quay.io
```

### Multiple Registries Example
You can use more then one registry to separate APBs into logical organizations and be able to manage them from the same broker. The main thing here is that the registries must have a unique non-empty name. If there is no unique name the service broker will fail to start with an error message alerting you to the problem.

```yaml
registry:
  - name: dockerhub
    type: dockerhub
    org: ansibleplaybookbundle
    user: user
    pass: password
    white_list:
      - ".*-apb$"
  - name: rhcc
    type: rhcc
    url: <rhcc url>
    white_list:
      - ".*-apb$"
```

## DAO Configuration

| field     | description                                         | required |
|-----------|-----------------------------------------------------|----------|
| etcd_host | The url of the etcd host.                           |     Y    |
| etcd_port | The port to use when communicating with `etcd_host` |     Y    |

## Log Configuration

| field   | description                      | required |
|---------|----------------------------------|----------|
| logfile | Where to write the broker's logs |     Y    |
| stdout  | Write logs to stdout             |     Y    |
| level   | Level of the log output          |     Y    |
| color   | Color the logs                   |     Y    |

## OpenShift Configuration

| field                   | description                                                                                                       | required |
|-------------------------|-------------------------------------------------------------------------------------------------------------------|----------|
| host                    | OpenShift host                                                                                                    |     N    |
| ca_file                 | Location of the certificate authority file                                                                        |     N    |
| bearer_token_file       | Location of bearer token to be used                                                                               |     N    |
| image_pull_policy       | When to pull the image                                                                                            |     Y    |
| namespace               | The namespace that the broker has been deployed to. Important for things like passing parameter values via secret |     Y    |
| sandbox_role            | Role to give to apb sandbox environment                                                                           |     Y    |
| keep_namespace          | Always keep namespace after apb execution                                                                         |     N    |
| keep_namespace_on_error | Keep namespace after apb execution has an error                                                                   |     N    |

## Broker Configuration
The broker config section will tell the broker what functionality should be enabled
and disabled. It will also tell the broker where to find files on disk that will
enable the full functionality.

*Note: with the absence of async bind, setting launch_apb_on_bind to true can cause the bind action to timeout and will span a retry. The broker will handle with with 409 Conflicts because it is the same bind request with different parameters.*

| field                | description                                                                                                                                      | default value          | required |
|----------------------|--------------------------------------------------------------------------------------------------------------------------------------------------|------------------------|----------|
| dev_broker           | Allow development routes to be accessible                                                                                                        | false                  |     N    |
| launch_apb_on_bind   | Allow bind be be no op                                                                                                                           | false                  |     N    |
| bootstrap_on_startup | Allow the broker attempt to bootstrap itself on start up. Will retrieve the APBs from configured registries                                      | false                  |     N    |
| recovery             | Allow the broker to attempt to recover itself by dealing with pending jobs noted in etcd                                                         | false                  |     N    |
| output_request       | Allow the broker to output the requests to the log file as they come in for easier debugging                                                     | false                  |     N    |
| ssl_cert_key         | Tells the broker where to find the tls key file. If not set the [apiserver](https://github.com/kubernetes/apiserver) will attempt to create one. | ""                     |     N    |
| ssl_cert             | Tells the broker where to find the tls crt file. If not set the [apiserver](https://github.com/kubernetes/apiserver) will attempt to create one. | ""                     |     N    |
| refresh_interval     | The interval to query registries for new image specs                                                                                             | "600s"                 |     N    |
| auto_escalate        | Allows the broker to escalate the permissions of a user while running the APB [read more](administration.md)                                     | false                  |     N    |

## Secrets Configuration
The secrets config section will create associations between secrets in the broker's namespace and apbs the broker runs.
The broker will use these rules to mount secrets into running apbs, allowing the user to use secrets to pass parameters
without exposing them to the catalog or users. The config section is a list where each entry has the following structure:

| field         | description                                                                                                                 | required |
|---------------|-----------------------------------------------------------------------------------------------------------------------------|----------|
| title         | The title of the rule. This is just for display/output purposes.                                                            |     Y    |
| apb_name      | The name of the APB to associate with the specified secret. This is the fully qualified name (registry_name-image).         |     Y    |
| secret        | The name of the secret to pull parameters from.                                                                             |     Y    |

You can use the script in scripts/create_broker_secret.py to create and format this configuration section.

### Secrets Example
```yaml
secrets:
- title: Database credentials
  secret: db_creds
  apb_name: dh-rhscl-postgresql-apb
```
