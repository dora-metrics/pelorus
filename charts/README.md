# Transition Plan

## Limitations of helm operator-sdk:
- charts cannot be nested

## Helm features to keep in mind

- [Helm "Library" Charts](https://helm.sh/docs/topics/library_charts/)
  - these can just be sets of templates that are pulled in by other charts.
  - This means we can have shared logic that is used by both traditional helm and the operator-sdk (in case we need to do slightly different approaches)

## Dependencies

 - At first only Pelorus exporters will become operators and other dependencies such as Grafana and Prometheus will be managed later possibly via OLM.
 
## Phases

1. Charts are separated in /charts in a way that operator-sdk can understand.  
  We will symlink to these charts from the operator directory for now.  
  These charts will need to be compatible with _both_ the existing helm workflow and the operator sdk workflow.  
  If we need to diverge, we can use the library chart approach above.  
2. We add notes to the `/charts` that say they are deprecated, users should use the operator, and link to the docs for it.
3. We remove `/charts` support.
4. Custom operator? (in python) (not go) (okay fine maybe go)

## Steps

1. Move exporters under /charts
2. Create new set of framework files from helm charts using latest version of operator sdk and merge it to master untouched.
3. Find a way to deploy operator out of the source tree and automate process to easy development.
4. Start simple: just have a "Pelorus" CRD and reuse existing values.yml structure
5. Once we know the above works, make 1 CRD per exporter type (not backend)
   1. Change the "exporters" chart to be a singular exporter (caveat: right now the RBAC is scoped across all exporters. Maybe we make that part of a common "pelorus core" resource (or whatever we call it))
6. consider if any configuration would be more ergonomic in a different structure
7. Write OpenAPI spec to validate the CRDs

## Notes to put somewhere

- we should modify values.yml to create the structure we want instead of customizing what it generates (helps us keep up to date with operator-sdk)
- since that would affect users of the existing workflow, we push as much as we can into library charts and have two very small pelorus charts: the existing one, and "pelorus-operator".
- we should have script or manual process documented to ensure update of the SDK is not breaking us / talk to somone from the SDK team on that subject.

## Open Questions

-  [ ] How much do we separate prometheus / grafana configuration from exporter configuration?