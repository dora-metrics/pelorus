# Before

```
$ oc get $(oc api-resources --verbs=list -o name | awk '{printf "%s%s",sep,$0;sep=","}')  --ignore-not-found --all-namespaces -o=custom-columns=KIND:.kind,NAME:.metadata.name,NAMESPACE:.metadata.namespace --sort-by='kind' | grep pelorus
Warning: v1 ComponentStatus is deprecated in v1.19+
Warning: policy/v1beta1 PodSecurityPolicy is deprecated in v1.21+, unavailable in v1.25+
APIRequestCount                  pelorus.v1alpha1.charts.pelorus.konveyor.io                                                <none>
OAuthClientAuthorization         kube:admin:system:serviceaccount:pelorus:grafana-serviceaccount                            <none>
OAuthClientAuthorization         kube:admin:system:serviceaccount:pelorus:pelorus-prometheus                                <none>
Operator                         pelorus-operator.pelorus                                                                   <none>
Operator                         grafana-operator.pelorus                                                                   <none>
Operator                         prometheus.pelorus                                                                         <none>
PackageManifest                  pelorus-operator                                                                           openshift-marketplace
```

# Clean

```
oc delete namespace pelorus
oc logout
```
