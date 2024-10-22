## Bind / Unbind New Work flow

The goal of this new work flow is to give more control over the actions that the APB takes on bind and unbind to the APB author. This means that we want the APB should have the ability to manage the bindings that are requested of it.

While this is still using existing workflow pieces (i.e extracting credentials, saving those credentials), it is also creating a new workflow. This is an enhancement on the current design and will allow for the APB to choose which workflow it would prefer to follow.

### Default Settings Needed
* set `launch_apb_on_bind: true` - If this is set to false we will behave the exact same as today, handing back the credentials received at provision to the service catalog.

NOTE: The launch_apb_on_bind will eventually be deprecated.


### Brokers Responsibility
* The broker will save the credentials for each bind. this will be saved in etcd under the `extracted_credentials` directory. The key will be the binding id.
* The broker will be responsible for providing the provisioned credentials (extracted credentials given at provision time) to the APB as extra vars during bind and unbind. Example
  - `--extra-vars '{..., "_apb_provision_creds:{}`
  - during unbind `{..., "_apb_provision_creds:{}, "_apb_bind_creds:{}}`
* The broker will be responsible for deleting the bindings extracted credentials in etcd during unbind.

### APB Responsibility
* The APB is responsible for encoding credentials. Using the [asb_encode_binding](https://github.com/fusor/apb-examples/pull/93/files/3d444b778e27ac3fb266fc5cc55d55eee211fb50#diff-c0c3dd5820ea9b91bd5f865af6a41f67) ansible module.
- Note: will be unused until PR is merged and we everything can use this method.
* The APB is responsible for handling the use of superuser/admin user vs. regular user to manage their image.
* The APB is responsible for handling the deletion/creation of users for their image.

#### Example Usage (workflow proposed):
1. On APB provision, the APB decides that, for what ever application it is responsible for deploying, to create an admin user & password.
2. The APB does not want to hand out the admin user and password, for the application that it is responsible for, to all the other applications that could be bound. Instead the APB author would like to create new user accounts (by using the already saved/created admin user & password), and pass those back as credentials during the bind. The new credentials are for the application that the APB is responsible for.
3. The same is true for unbind. The APB author could want to delete the user and password, for the application that it manages, credentials and would need to use the admin user & password. The broker would also be deleting credentials from etcd at this time.

#### Example Usage:
1. APB author would like to keep only 1 account, and use that 1 account for all the bindings(current behavior).
2. That means their bind would need to pass back the credentials created at provision time. They can now do this by just taking the parameters passed in and sending them back to the broker.
