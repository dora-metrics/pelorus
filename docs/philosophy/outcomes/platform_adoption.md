# :fontawesome-solid-person-circle-plus: Platform Adoption :material-check-circle:{ .unchecked }

Platform Adoption measures an organization’s ability to reduce waste by adopting common patterns, platforms and tools.

<div class="grid cards" markdown>

-   [:material-account-clock: __Adoption lead time__](#adoption-lead-time)
-   [:fontawesome-solid-arrow-trend-up: __Adoption rate__](#adoption-rate)
-   [:material-account-arrow-down: __Retention Rate__](#retention-rate)
-   [:fontawesome-solid-people-roof: __Operational efficiency__](#operational-efficiency)
-   [:material-account-heart-outline: __Developer Satisfaction__](#developer-satisfaction)

</div>

## Why Measure?

Lean Thinking, the grandparent of Agile, DevOps and everything else we talk about in the digital transformation realm, is centered around the idea of eliminating _muda_ -- waste in the form of human effort that produces no value.

!!! further-reading "Further Reading"

    Read more about _muda_ and the 5 principles of Lean Thinking that help to banish waste in the book [Lean Thinking](https://www.lean.org/store/book/lean-thinking-2nd-edition/) by James P. Womack and Daniel T. Jones.

A common form of waste in an IT organization is in when multiple people or teams with similar needs work separately to solve the same problem. This can happen for a number of reasons, but the culprit is always some form of communication gap. The recent trends toward decentralization of IT, agile, cloud adoption, microservices architectures and full stack development have made it increasingly difficult for teams that are independent of eachother to be able to share a common set of tools, platforms, and solutions that helps to reduce the cognitive load of the development team, while also allowing for the autonomy that teams need to do great work.

This struggle has given birth to new practices like [Platform Engineering](https://platformengineering.org/blog/what-is-platform-engineering), [Inner Sourcing](https://about.gitlab.com/topics/version-control/what-is-innersource/), and Re-commoning. The goal is to provide teams with a set of common platforms, tools, and solutions that they can consume on-demand as a way of reducing cognitive load and re-work by individual teams.

In order to acheive this, it is important to track the health of these common assets by measuring whether they are being well adopted. This is how we get the outcome of _Platform Adoption_.

## :material-ruler: Measures

### :material-account-clock: __Adoption lead time__

Measures a team’s ability to onboard into a new platform, tool or pattern and exposes constraints in the process

#### Variables

`Adoption Lead Time (aLT)`

`Adoption start event(aS)`

:   Developer/application/team requests access

    For example:

    - ticket opened
    - email sent
    - self-service onboarding workflow initiated

    Expressed as a _timestamp_

`Adoption end event(aE)`

:   Developer/application/team does something meaningful using the tool

    For example:

    - Application deployed in X environment
    - Code committed to X branch
    - Workspace spun up

    Expressed as a _timestamp_

#### Formulas

`aLT = aE - aS`

### :fontawesome-solid-arrow-trend-up: __Adoption rate__

Measures the ability of the platform or tool to scale to support multiple teams and products

#### Variables

`Adoption end event(aE)`

`Adoptions at Time T1` (At<sub>1</sub>)

`Adoptions at Time T2` (At<sub>2</sub>)

#### Formulas

At<sub>1</sub> = count(aE)[t<sub>1</sub>]

At<sub>2</sub> = count(aE)[t<sub>2</sub>]

AR = (At<sub>1</sub> - At<sub>2</sub> - 1) * 100

### :material-account-arrow-down: __Retention Rate__

Measures the sustainability of the platform and whether it continues to be used beyond initial onboarding

### :fontawesome-solid-people-roof: __Operational efficiency__

Measures the number of people needed to support the platform as it scales and exposes technical debt

### :material-account-heart-outline: __Developer Satisfaction__

Measures the extent to which the platform is meeting the needs and wants of development
