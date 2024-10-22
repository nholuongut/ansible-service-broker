# Remove Image Field from APB Spec Proposal

## Introduction

The broker currently relies on the image field of the
[apb.yaml](https://github.com/fusor/ansible-playbook-bundle/blob/master/src/apb/dat/apb.yml.j2)
to determine the location of the docker image to deploy instead of relying on the
registry adapters to formulate the image path based on the location of the spec
plus the name of the apb.

## Problem Description

Similar to #288, there is a problem with the way the broker uses ansible
playbook bundle specifications (APB spec); the image from which we retrieve the
specification is not necessarily the same image we use to execute the
`[provision, bind, unbind, deprovision]`.

## Implementation Details

Before continuing into the implementation details it is important to
distinguish the APB spec from the broker's perspective and the APB spec that is
built from the `apb.yaml` (APB yaml). This proposal will use APB spec to refer
to the use of the `Spec struct` in [pkg/apb/types.go](../../pkg/apb/types.go)
and APB yaml to refer to the specification that is build using the APB tool.

### Let the Broker Fill in the Image Field

Regardless of where the APB yaml says the image can be found, the broker should
use the path to the image from which the spec was retrieved. The image from
which we retrieve the APB spec and the image we use to execute the APB spec
should be equivalent; this change will enforce that change without breaking
the current APB yaml.

In [pkg/apb/types.go](../../pkg/apb/types.go):

```diff
type Spec struct {
   ID          string                 `json:"id"`
   FQName      string                 `json:"name" yaml:"name"`
-  Image       string                 `json:"image"`
+  Image       string                 `json:"image,omitempty"`
   Tags        []string               `json:"tags"`
   Bindable    bool                   `json:"bindable"`
   Description string                 `json:"description"`
   Metadata    map[string]interface{} `json:"metadata,omitempty"`
   Async       string                 `json:"async"`
   Plans       []Plan                 `json:"plans"`
}
```

In [pkg/registries/adapters/adapter.go](../../pkg/registries/adapters/adapter.go):

```diff
- func imageToSpec(log *logging.Logger, req *http.Request, apbtag string) (*apb.Spec, error) {
+ func imageToSpec(log *logging.Logger, req *http.Request, image string) (*apb.Spec, error) {

...

-  spec.Image = fmt.Sprintf("%s:%s", spec.Image, apbtag)
+  spec.Image = image
```

Then update the adapters to include the image when calling `imageToSpec`, for
example in [pkg/registries/adapters/dockerhub_adapter.go](../../pkg/registries/adapters/dockerhub_adapter.go):

```diff
-  return imageToSpec(r.Log, req, r.Config.Tag)
+  return imageToSpec(r.Log, req, fmt.Sprintf("%s/%s:%s", r.RegistryName(), imageName, r.Config.Tag))
```

### Update FQName

In order for these changes to work, we will also have to update the `FQName` of
the APB Spec. Since we know that image name must be unique to a registry
(each entry under `registry` in the broker config is a specific registry)
**and** each registries name must be unique, then
`${registry_name}-${apb_name}` is a sufficiently unique name for `FQName`. We
will update the [pkg/broker/broker.go](../../pkg/broker/broker.go):

```diff
-  imageName := strings.Replace(spec.Image, ":", "-", -1)
-  spec.FQName = strings.Replace(fmt.Sprintf("%v-%v", registryName, imageName),
+  spec.FQName = strings.Replace(
+      fmt.Sprintf("%v-%v", registryName, spec.FQName),
       "/", "-", -1)
```

## Examples

With all of these changes and a broker configured with the following registries:

```yaml
---
registry:
  - type: dockerhub
    name: dh
    url: https://registry.hub.docker.com
    user: changeme
    pass: changeme
    org: ansibleplaybookbundle
  - type: dockerhub
    name: dy
    url: https://registry.hub.docker.com
    user: changeme
    pass: changeme
    org: dymurray
```

These registries were chosen because there are name collisions among the 2
registries. One such collision is on `mediawiki123-apb`.

From the `dh` registry:

```
{
    "id":"268dbc13f56297fdd3737b7d30104eb4",
    "name":"dh-mediawiki123-apb",
    "image":"docker.io/ansibleplaybookbundle/mediawiki123-apb:latest",
    ...
}
```

From the `dymurray` registry:

```
{
    "id":"be10458618a1f1e5efe472b781586ee8","name":
    "dy-mediawiki123-apb",
    "image":"docker.io/dymurray/mediawiki123-apb:latest",
    ...
}
```

## Work Items

- [ ] Update the Broker to fill in image field of APB Spec
- [ ] Update the Broker to use `${registry_name}-${apb_name}` format
- [ ] Update APB tool to remove image field
- [ ] Update existing APB examples to remove image field
