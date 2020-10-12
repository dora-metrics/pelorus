echo "
---
apiVersion: v1
data:
  htpasswd: YWRtaW46JDJ5JDA1JHBxVFlQbkdERUcxUi9OZWlTdGc5bXVockFtdHBIQTlrbkF0LzVnNzB5N2JRby9zcTlLMW9pCg==
kind: Secret
metadata:
  name: htpass-secret
  namespace: openshift-config
type: Opaque
---
apiVersion: config.openshift.io/v1
kind: OAuth
metadata:
  name: cluster
spec:
  identityProviders:
  - name: my_htpasswd_provider 
    mappingMethod: claim 
    type: HTPasswd
    htpasswd:
      fileData:
        name: htpass-secret
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: lab-admins
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-admin
subjects:
- apiGroup: rbac.authorization.k8s.io
  kind: User
  name: admin
" | oc apply -f-