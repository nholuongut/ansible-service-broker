# Bind Use Cases

## External Service with Bind (mLab and webapp)
The external service use case is where an Ansible Playbook Bundle (APB) is able to connect to a service outside of the cluster. One example, is a webapp that uses mLab as their back end store. There will be a specific APB for the external service.

Catalog Operator does the following:
* Creates a broker resource which calls the AnsibleServiceBroker /catalog endpoint
* The /catalog endpoint response populates the ServiceCatalog's list of ServiceClasses. In our example, this is mLab and Go WebApp

The Service Consumer then utilizes the ServiceClasses for their needs. After getting a list of the available service classes, the Consumer will then:

* Creates an instance of the mLab service.
  * ServiceCatalog calls provision endpoint on AnsibleServiceBroker
  * AnsibleServiceBroker provisions the mLab APB
  * mLab APB configures the mLab instance being made available
  * mLab service ready for consumption
* Create a binding resource for the mLab service
  * ServiceCatalog calls the binding endpoint on the AnsibleServiceBroker
  * AnsibleServiceBroker calls bind on the mLab APB
  * mLab APB will return the credentials, coordinates, & configs for the service.
  * Magic happens
    * ServiceCatalog does something with the bind information such that it can be injected into the applications later
* Creates an instance of the Go WebApp service.
  * ServiceCatalog calls provision endpoint on AnsibleServiceBroker
  * AnsibleServiceBroker provisions the Go WebApp APB
  * The mLab binding information is *injected* into the Go WebApp APB
  * Go WebApp APB configures itself to use the information
  * Go WebApp service is ready for consumption and utilizing the mLab service

### Binding diagram
![binding example](images/binding-example.png)

### Binding example sequence diagram
![binding example sequence diagram](images/binding-example-seq-diagram.png)

### Sequence diagram source

```
Catalog Operator -> ServiceCatalog: POST broker
ServiceCatalog -> ServiceCatalog: Create Broker resource
Controller -> AnsibleServiceBroker: GET /catalog
AnsibleServiceBroker -> Controller: List of available service classes: mLab, Go WebApp
Controller -> ServiceCatalog: Creates list of service classes available
Service Consumer -> ServiceCatalog: GET /serviceclasses
Service Consumer -> ServiceCatalog: POST /instance (mLab)
Controller -> AnsibleServiceBroker: PUT /provision (mLab)
AnsibleServiceBroker -> mLab APB: docker run provision
mLab APB -> OpenShift: creates Kubernetes service endpoint
ServiceCatalog -> Service Consumer: mLab instance ready
Service Consumer -> ServiceCatalog: PUT /binding
ServiceCatalog -> ServiceCatalog: Create binding resource
Controller -> AnsibleServiceBroker: PUT /binding
AnsibleServiceBroker -> mLab APB: docker run binding
mLab APB -> AnsibleServiceBroker: Returns the binding information for external mLab Service
AnsibleServiceBroker -> Controller: Returns binding information
Controller -> Magic: Store binding information for injection later
Service Consumer -> ServiceCatalog: POST /instance (Go WebApp)
Controller -> AnsibleServiceBroker: PUT /provision (Go WebApp)
AnsibleServiceBroker -> Go WebApp APB: docker run provision
Magic -> Go WebApp APB: INJECT binding information
Go WebApp APB -> mLab Service: Uses
AnsibleServiceBroker -> Controller: Go WebApp service instance ready
ServiceCatalog -> Service Consumer: Go WebApp instance ready

```

## Bindable Database Service
There are services that will be deployed that simply exist to be bound to other applications. Typical use case is a Mariadb database instance.

* provision database APB (stays up to let other bind)
* bind request to app returns connection information,

### Database example sequence diagram
![database provision and bind](images/database-provision-and-bind.png)

### Sequence diagram source
```
Service Consumer -> ServiceCatalog: POST instance
ServiceCatalog -> Ansible Service Broker: PUT provision/instance_id
Ansible Service Broker -> etcd : get database image
etcd -> Ansible Service Broker: return image record
Ansible Service Broker -> Docker Hub: pull database image
Docker Hub -> Ansible Service Broker: return database image
Ansible Service Broker -> Ansible Service Broker: run database image
Ansible Service Broker -> ServiceCatalog: return 200 image
ServiceCatalog -> Service Consumer: ServiceClass
Service Consumer -> ServiceCatalog: PUT /binding
ServiceCatalog -> ServiceCatalog: Create binding resource
Controller -> AnsibleServiceBroker: PUT /binding
Ansible Service Broker -> Controller: return database connection string
Controller -> Magic: Store binding information for injection later
```
## Etherpad wants to connect to database
* provision etherpad
* bind to database
* assume database service previously provisioned

### Etherpad sequence diagram
![etherpad connect to db](images/etherpad-connect-to-db.png)

### Sequence diagram source
```
Service Consumer -> ServiceCatalog: POST /instance (Etherpad)
Controller -> AnsibleServiceBroker: PUT /provision (Etherpad)
AnsibleServiceBroker -> Go WebApp APB: docker run provision
Ansible Service Broker -> etcd : get etherpad image
etcd -> Ansible Service Broker: return image record
Ansible Service Broker -> Docker Hub: pull etherpad image
Docker Hub -> Ansible Service Broker: return etherpad image
Ansible Service Broker -> Ansible Service Broker: run etherpad image
Ansible Service Broker -> ServiceCatalog: return 200 OK
Magic -> Go WebApp APB: INJECT binding information
Go WebApp APB -> mLab Service: Uses
AnsibleServiceBroker -> Controller: Go WebApp service instance ready
ServiceCatalog -> Service Consumer: Go WebApp instance ready
```
## Issues

* does the service consumer have to initiate the binds?
