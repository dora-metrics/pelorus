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

## Steps

1. Move exporters under /charts
2. Create new set of framework files from helm charts using latest version of operator sdk and merge it to master untouched.
3. Find a way to deploy operator out of the source tree and automate process to easy development.
4. Start simple: just have a "Pelorus" CRD and reuse existing values.yml structure
5. Once we know the above works, make 1 CRD per exporter