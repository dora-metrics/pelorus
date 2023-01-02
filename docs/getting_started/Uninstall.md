# Uninstalling

Cleaning up Pelorus is very simple. Just run

```
helm uninstall pelorus --namespace pelorus
helm uninstall operators --namespace pelorus
oc delete namespace pelorus
```

If Pelorus was deployed with PVCs, you may want to delete them, because helm uninstall will not remove PVCs. To delete them run
```
oc delete pvc --namespace pelorus $(oc get pvc --namespace pelorus -o name)
```
