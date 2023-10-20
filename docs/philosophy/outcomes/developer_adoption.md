# :fontawesome-solid-person-circle-plus: Developer Adoption :material-check-circle:{ .unchecked }

_Developer Adoption_ captures an organization’s ability to reduce waste by adopting common patterns, platforms and tools.

<div class="grid cards" markdown>

-   [:fontawesome-solid-arrow-trend-up: __Adoption rate__](#adoption-rate)
-   [:material-account-arrow-down: __Retention Rate__](#retention-rate)
-   [:material-account-clock: __Adoption lead time__](#adoption-lead-time)
-   [:material-counter: __Adoption Density__](#adoption-density)
-   [:fontawesome-solid-people-roof: __Operational efficiency__](#operational-efficiency)
-   [:material-account-heart-outline: __Developer Satisfaction__](#developer-satisfaction)

</div>

## Why Measure?

Lean Thinking, the grandparent of Agile, DevOps and everything else we talk about in the digital transformation realm, is centered around the idea of eliminating _muda_ -- waste in the form of human effort that produces no value.

!!! further-reading "Further Reading"

    Read more about _muda_ and the 5 principles of Lean Thinking that help to banish waste in the book [Lean Thinking](https://www.lean.org/store/book/lean-thinking-2nd-edition/){:target="_blank"} by James P. Womack and Daniel T. Jones.

A common form of waste in an IT organization is when multiple people or teams with similar needs work separately to solve the same problem. This can happen for a number of reasons, but the culprit is always some form of communication gap. The recent trends toward decentralization of IT, agile, cloud adoption, microservices architectures and full stack development have made it increasingly difficult for teams that are independent of each other to be able to share a common set of tools, platforms, and solutions that helps to reduce the cognitive load of the development team, while also allowing for the autonomy that teams need to do great work.

This struggle has given birth to new practices like [Platform Engineering](https://platformengineering.org/blog/what-is-platform-engineering){:target="_blank"}, [Inner Sourcing](https://about.gitlab.com/topics/version-control/what-is-innersource/){:target="_blank"}, and [Re-commoning](https://www.youtube.com/watch?v=mGNEbDhT1Hw){:target="_blank"}. The goal is to provide teams with a set of common components (platforms, tools, and solutions) that they can consume on-demand as a way of reducing cognitive load and re-work by individual teams.

{==

Successful adoption of the right combination of components should lead to an improved developer experience, allowing developers more focus on value-related work, therefore reducing waste and increasing value potential to the organization.  To achieve this, it is important to track the value that each component available to developers provides by measuring whether they are being well adopted. This is how we get the outcome of _Developer Adoption_.

==}

## Parameters of success

Before we get into the measures that make up the Developer Adoption outcome, we have a few decisions to make and some shared understanding to build.  Across each of the measures in Developer Adoption, we have three parameters of success that need to be defined and agreed upon: _target user_, _adoption event_, and _active user_.  __A good way to figure out what success looks like for the component, think about who has to conduct what sorts of observable actions in that component to translate most directly to value.__

We need to define an entity that will call our _target user_. Typically we would think of a user as an individual person. However, depending on the platform or tool we are trying to measure we may want to define a user differently. A user might be a team, an application, a product, or a service.

Getting more specific about the type of user can help us create a stronger product and will help us define the _adoption event_.  For instance, if you're measuring adoption of a learning platform, then your _adoption event_ might be an employee completing a course. In this case the _target user_ would be an individual employee. However, if you're measuring adoption of an application hosting platform or deployment tool, then your _adoption event_ would likely be an application getting deployed into a certain environment, or passing a particular stage of a pipeline. In this case it makes more sense to track either the application itself or the team that owns the application.

Different components will likely have different definitions of target users and adoption events, and that's okay. What's important is to make sure that within a component and its measures, we're consistent in our definitions for target user and adoption event.

Once we have identified who our target user is and the adoption event we want to track, we can then use those to define what we consider to be an _active user_ of a given component. An _active user_ would be a user who has achieved an adoption event within a certain period of time, let's say the past week.


| Parameter      | Description                                                      | Examples                                |
| -------------- | ---------------------------------------------------------------- | --------------------------------------- |
| :fontawesome-solid-users-viewfinder: Target user    | The type of user that the component provides value to (individual, team, application, product or a service) | Front-end developers, business-to-business APIs, customer-facing apps |
| :material-timeline-check: Adoption event | The observable action in the component that translate most directly to value | Deploys an application to a specific environment, completes a story, commits some code to a specific branch, logs a certain number of hours of active use |
| :fontawesome-solid-user-clock: Active user    | Combines a target user and an adoption event with a time scope and frequency to determine what it means to be "active" in the component | A developer who has committed code from their cloud workspace within the past week |

## :material-ruler: Measures

Here we break down the 6 _measures_ of the Developer Adoption outcome in detail. We'll cover the raw data points that we'll need to collect from our various components and then the formulas to calculate each measure.

### Common knowledge

Data points and formulas used by more than one _measure_.

#### Data Points

##### Adoption events

:   _Adoption events $(E)$_: A set of valuable users interactions with the tool

    Expressed as a set of tuples (string, timestamp), where

    - the first element is the target user's username
    - the second element is the timestamp when the interaction occurred

#### Formulas

##### Active users at a given time interval

:   _Active users at a given time interval $(A(t,\Delta t))$_: Given a timestamp $t$ and a time interval $t-\Delta t$, the unique target users who have at least one adoption event between $t$ and $t-\Delta t$, is the set:

    $$
    A(t,\Delta t) = \{\text{username} : \exists\ x,t -\Delta t \leq x \leq t, (\text{username},x) \in E\}
    $$

##### Number of active users at a given time interval

:   _Number of active users at a given time interval $(U(t,\Delta t))$_: Given a timestamp $t$ and a time interval $t-\Delta t$, the number of unique target users who have at least one adoption event between $t$ and $t-\Delta t$, is calculated as follows:

    $$
    U(t,\Delta t) = \text{count}(A(t,\Delta t))
    $$

##### Number of adoption events at a given time interval

:   _Number of adoption events at a given time interval $(E(t,\Delta t))$_: Given a timestamp $t$ and a time interval $t-\Delta t$, the number of adoption events between $t$ and $t-\Delta t$ is calculated as follows:

    $$
    E(t,\Delta t) = \text{count}(\{(\text{username},x) : \exists\ x,t -\Delta t \leq x \leq t, (\text{username},x) \in E\})
    $$

### :fontawesome-solid-arrow-trend-up: __Adoption rate__

Adoption Rate ($AR$) is the rate at which a component is acquiring new users. This serves as an indicator of the ability of the component to scale to support multiple teams and products, as well as whether or not the component is compelling developers to want to try it out.

#### Data Points

[_Adoption events $(E)$_](#adoption-events)

#### Formulas

[_Number of active users at a given time interval $(U(t,\Delta t))$_](#number-of-active-users-at-a-given-time-interval)

!!! formula ""

    _Adoption Rate $(AR(t,\Delta t))$_

    :   The rate of change of users adoption the tool at timestamp $t$ over time interval $\Delta t$

    $$
    AR(t,\Delta t) = \left(\frac{U(t,\Delta t) - U(t-\Delta t,\Delta t)}{U(t-\Delta t,\Delta t)}\right) \cdot 100
    $$

### :material-account-arrow-down: __Retention rate__

So we've got a platform up and running, onboarding is really fast and we've been able to attract a bunch of new users. Now we need to ask a new set of questions. Is the platform meeting the needs of its users? Are people continually using it? Measuring _retention rate_ tells us whether users that have adopted our platform continue to use it over time to do valuable work. It is the yin to _adoption rate's_ yang.

#### Data Points

[_Adoption events $(E)$_](#adoption-events)

#### Formulas

[_Active users at a given time interval $(A(t,\Delta t))$_](#active-users-at-a-given-time-interval)

[_Number of active users at a given time interval $(U(t,\Delta t))$_](#number-of-active-users-at-a-given-time-interval)

_Number of new users at a given time interval $(N(t,\Delta t))$_

:   Given a timestamp $t$ and a time interval $t-\Delta t$, the number of new target users between $t$ and $t-\Delta t$, is calculated as follows:

    $$
    N(t,\Delta t) = \text{count}(A(t,\Delta t) - A(t-\Delta t,\Delta t))
    $$

!!! formula ""

    _Retention Rate $(RR(t,\Delta t))$_

    :   The percentage of users that were active at timestamp $t$ over time interval $\Delta t$

        $$
        RR(t,\Delta t) = \left(\frac{U(t,\Delta t) - N(t,\Delta t)}{U(t-\Delta t,\Delta t)}\right) \cdot 100
        $$

### :material-account-clock: __Adoption lead time__

_Adoption lead time_ is the speed at which a new user or team is able to onboard to a new component. By tracking lead time to adopt an internal product, we gain insight into the quality of the user experience for new users as well as indications of constraints in the process.

It's important with this measurement to capture, not only the time it takes to get access to a given product, but the total time it takes from when a user shows intent to use the product (usually by capturing a request made) to the moment when that user has been able to use the product to do something valuable.

#### Data Points

[_Adoption events $(E)$_](#adoption-events)

#### Formulas

_Adoption lead time at a given time $(L(t))$_

:   Given a timestamp $t$, the adoption lead time for any individual adoption event at time $t$, is calculated as follows:

    $$
    L(t) = \min(\{x:(\text{username},x) \in E\}) - t
    $$

TODO still confused

!!! formula ""

    _Average Adoption Lead Time $(\bar{L}(t))$_

    :   The average adoption lead time at timestamp $t$ collection of $N$ individual adoption lead times

        $$
        \bar{L}(t) = \frac{\sum_{1}^{N}L(t_{i})}{N}
        $$

### :material-counter: __Adoption density__

So far we've focused most of our measurement on identifying active users -- those who meet a minimum criteria to be considered active. This treats users who use a component once the same as those who use it 100 times. Since we've identified our _adoption events_ as being instances of a user doing something valuable, we should naturally want to see more and more of those events over time. This is what we want to capture with _Adoption Density_.

#### Data Points

[_Adoption events $(E)$_](#adoption-events)

#### Formulas

[_Number of adoption events at a given time interval $(E(t,\Delta t))$_](#number-of-adoption-events-at-a-given-time-interval)

!!! formula ""
    _Adoption Density $(AD(t,\Delta t))$_

    :   The density growth of adoption events at timestamp $t$ over time interval $\Delta t$

    $$
    AD(t,\Delta t) = \left(\frac{E(t,\Delta t) - E(t-\Delta t,\Delta t)}{E(t-\Delta t,\Delta t)}\right) \cdot 100
    $$

### :fontawesome-solid-people-roof: __Operational efficiency__

As our reusable components get adopted and we start seeing success from a user perspective, it becomes important to monitor the financial sustainability of maintaining and evolving these components. This helps ensure that we are actually getting a _return on investment_ as we scale. To track this, we measure _operational efficiency_ -- the ratio of effort required to maintain and evolve the platform to level of active adoption of the platform.

The simplest way to calculate _operational efficiency_ is by comparing the number of people maintaining the component to the _total adoption events_  the platform has.

#### Data Points

[_Adoption events $(E)$_](#adoption-events)

_Component Maintainers ($M$)_

:   The number of people it takes to maintain the component

    Expressed as a number

    TODO this is constant or can increase/decrease over time?

#### Formulas

[_Number of adoption events at a given time interval $(E(t,\Delta t))$_](#number-of-adoption-events-at-a-given-time-interval)

_Number of maintainers at a given time interval $(M(t,\Delta t))$_

:   Given a timestamp $t$ and a time interval $t-\Delta t$, the number maintainers between $t$ and $t-\Delta t$, is calculated as follows:

    $$
    M(t,\Delta t) = \text{count}(\{(\text{maintainer},x) : \exists\ x,t -\Delta t \leq x \leq t, (\text{maintainer},x) \in M\})
    $$

!!! formula ""

    _Operational Efficiency $(OE(t,\Delta t))$_

    :   The operational efficiency at timestamp $t$ over time interval $\Delta t$

        $$
        OE(t) = \frac{E(t,\Delta t)}{M(t,\Delta t)}
        $$

### :material-account-heart-outline: __Developer Satisfaction__

Measures the extent to which the platform is meeting the needs and wants of developers.

#### Data Points

[_Number of active users at a given time interval $(U(t,\Delta t))$_](#number-of-active-users-at-a-given-time-interval)

_Net Promoter Score survey $(S)$_

:   The set of scores returned from a net promoter score survey

    Expressed as a set of integers between 0 and 10

#### Formulas

_Survey response rate $(SR(t,\Delta t))$_

:   The percentage of the active users between $t$ and $t-\Delta t$ whose experiences were captured by the survey, is calculated as follows:

    $$
    SR(t,\Delta t) = \frac{\text{count}(S)}{U(t,\Delta t)} \cdot 100
    $$

TODO Net Promoter Score survey (S) results is constant or can increase/decrease over time?

!!! formula ""

    _Net Promoter Score ($NPS$)_

    :   The Net Promoter Score

        $$
        NPS = \frac{ \text{count}(S_P) - \text{count}(S_D) }{\text{count}(S)}
        $$

    :   where ${S_P}$ is the subset of $S$ of scores 9 or 10 and ${S_D}$ is the subset of $S$ of scores 6 or below
