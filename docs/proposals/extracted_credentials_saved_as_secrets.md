## Extracted Credentials Saved As Secrets

Extracted Credentials are currently saved in our etcd for the service broker. This is not desirable for many reasons, but the two biggest are kubernetes already has a built-in way to manage this data, secrets, and when moving to CRDs we don't want to create a resource for extracted credentials.

### Problem Description
The problem is that we should not manage data that is of a sensitive nature if we do not have to. This proposal is limited in scope and only interested in how we save the extracted credentials. It is worth noting that we should eventually be better about how we transmit this data to APBs. 

In the secret, we will save the data in the following format.
```yaml
data:
  credentials: <base64 encoded json>
apiVersion: v1
kind: Secret
metadata:
  name: <Service/Binding id>
  namespace: <Namespace for the broker>
  labels:
    <labels provided>
```

To encode the credentials in a generic way, we must marshal a `map[string]interface{}` so that we can retrieve the data. This is not how I wanted the secret to look, but will allow anyone to use the credentials and will allow us to retrieve the credentials without writing our own gob parser.

The functions for saving and retrieving will be in the `clients` package. This means the callers will be required to use the underlying extracted credentials type `map[string]interface{}` because we do not want a circular dependency between `apb` package and `clients` package. 

We will interact with the secrets from the namespace defined in the configuration by the `openshift.namespace` value. 

The APB package will now be required to do all CRUD operations for extracted credentials. The APB package will expose a single retrieve extracted credentials method, that will take a UUID (either service instance id or binding instance id) and returns an `apb` package extracted credentials object.

Runtime package should be used to encapsulate the `clients` package calls. This will mean we have a default functions for CRUD operations with extracted credentials. These default functions will be attached to a default struct and the default struct will be unexported. the NewRuntime function will now have a parameter of an ExtractedCredentials interface. If this interface is nil we will use the default struct. to function vars at init of runtime. The function vars are then overrideable in the future. example:
```go

type defaultExtCreds struct{}

func (d defaultExtCreds) saveExtractedCredentials(...) {
    ...
    k8scli, err := clients.Kubernetes()
    if err != nil {
        ...
    }
    k8scli.Clients.CoreV1().Secrets()...
}
...

type ExtractedCredentials interface {
    // Saves the extracted credentials. 
    // string - Id or name of the extracted credntials.
    // string - namespace or location information for the extracted credentials.
    // map[strin]interface{} - extracted credentials
    // map[string]string - labels or other metadata to associate with the extracted credentials.
    SaveExtractedCredentials(string, string, map[string]interface{}, map[string]string) error
    ....
}
```


### Work Items
- [x] Add kubernetes client methods to interact with extracted credentials in the [namespace](https://github.com/openshift/ansible-service-broker/blob/master/docs/config.md#openshift-configuration). 
- [x] Add runtime methods for interacting with extracted credentials. These methods should be overridable. 
- [x] Remove all dao implementation and interface methods regarding extracted credentials.
- [x] Remove all instances of interacting with dao extracted credentials in the `broker` package. Add back call to APB package to get extracted credentials when needed.
- [x] Update APB package to create/save/delete extracted credentials for the correct actions. this should call the correct `runtime` package methods.
- [x] Add exposed method on APB  that will retrieve the extracted credentials.