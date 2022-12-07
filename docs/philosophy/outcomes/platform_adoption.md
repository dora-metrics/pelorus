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

## Defining the _user_ and the _adoption event_

Before we get into the measures that make up the Tech Adoption outcome, we have a decision to make. We need to define an entity that will call our _user_. Typically we would think of a user as an individual person. However, depending on the platform or tool we are trying to measure we may want to define a user differently. A user might be a team, and application, product, or service. 

__A good way to figure out what your user should be for a given system is to think about what sorts of observable actions in that systems translate most directly to value.__ For instance, if you're measuring adoption of a learning platform, then your _adoption event_ might be an employee completing a course. In this case the _user_ would be an individual employee. However, if you're measuring adoption of an application hosting platform or deployment tool, then your _adoption event_ would likely be an application getting deployed into a certain environment, or passing a particular stage of a pipeline. In this case it makes more sense to track either the application itself or the team that owns the application.

Varying systems will likely have different definitions of users and adoption events, and that's okay. What's important is to make sure that we're using the same definitions for user and adoption event across the different measures for the same system.

## :material-ruler: Measures

Here we break down the 5 _measures_ of the Tech Adoption in detail. We'll cover the raw data points that we'll need to collect from our various systems, and then the formulas we'll need in order to calculate each measure.

### :material-account-clock: Adoption lead time

_Adoption lead time_ measures the speed at which a new user or team is able to onboard into a new platform, tool or pattern. By tracking lead time to adopt an internal product, we gain insight into the quality of the user experience for new users as well as indications of constraints in the process. 

It's important with this measurement to capture, not only the time it takes to get access to a given product, but the total time it takes from when a user shows intent to use the product (usually by capturing at some sort of request submission) to the moment when that user has been able to use the product to do something valuable.

#### Data Points

The following data points must be gathered from the systems we are aiming to measure.

_Adoption start events ( $a_{S}$ )_

:   Developer/application/team requests access

    For example:

    - ticket opened
    - email sent
    - self-service onboarding workflow initiated

    Expressed as a _timestamp_

_Adoption end events ( $a_{E}$ )_

:   Developer/application/team does something valuable using the tool

    For example:

    - Deploys an application to a specific environment
    - Completes a story
    - Commits some code to a specific branch
    - Logs a certain number of hours of active use

    Expressed as a _timestamp_

#### Formulas

_Adoption Lead Time ( $LT$ )_

:   For any individual adoption event, the adoption lead time $a_{LT}$ can be calculated as follows:

    $$
    LT = a_{E} - a_{S}
    $$

**_Average Adoption Lead Time ( $\overline{x}LT$ )_**

:   Given a collection of $N$ individual adoption lead times ( $LT_{1}..LT_{N}$ ), the _average adoption lead time_ $\overline{x}LT$ can be calculated as follows:

    $$
    \overline{x}LT = \frac{sum(LT_{1}..LT_{N})}{N}
    $$

### :fontawesome-solid-arrow-trend-up: Adoption rate

Adoption Rate ($AR$) measures the ability of the platform or tool to scale to support multiple teams and products. 

#### Data Points

The following data points must be gathered from the systems we are aiming to measure.

_Adoption end events ( $a_{E}$ )_

:   Developer/application/team does something valuable using the tool

    For example:

    - Deploys an application to a specific environment
    - Completes a story
    - Commits some code to a specific branch
    - Logs a certain number of hours of active use

    Expressed as a _timestamp_

#### Formulas

_Adoptions at Time $t_{1}$ ( $a^{t_{1}}$ )_

:   The number of Adoption end events $a_{E}$ that have taken place as of timestamp $t_{1}$. Calculated as follows:

    $$
    a^{t_{1}} = count(aE)[t_{1}]
    $$

_Adoptions at Time $t_{2}$ ( $a^{t_{2}}$)_

:   The number of adoption end events $a_{E}$ that have taken place as of timestamp $t_{2}$ where $t_{2} > t_{1}$. Calculated as follows:

    $$
    a^{t_{2}} = count(aE)[t_{2}]
    $$

**_Adoption Rate $AR$_**

$$
AR = (a^{t_{2}} - a^{t_{2}} - 1) * 100
$$

### :material-account-arrow-down: __Retention Rate__

So we've got a platform up and running, onboarding is really fast and we've been able to attract a bunch of new users. Now we need to ask a new set of questions. Is the platform meeting the needs of its users? Are people continually using it? Measuring _retention rate_ tells us whether users that have adopted our platform continue to use it over time to do valuable work. It is the yin to _adoption rate's_ yang.

Use time since last adoption on a varying time scale to determine active users.

To determine your retention rate, first identify the time frame you want to study
Next, collect the number of existing customers at the start of the time period ($u_{S}$)
Then find the number of total customers at the end of the time period ($u_{E}$)
Finally, determine the number of new customers added within the time period ($u_{N}$)

#### Data Points

_Time range ( $T$ )_

:   The range of time in which you want to evaluate retention. For example:

    * One month
    * 3 months
    * 6 months

    Using this time range, we also need to set three timestamps:

    1. The end of the time period we are measuring; $T_{0}$ (typically $T_{0} = now()$)
    2. The start time of the time period; $T_{1} = T_{0} - T$
    3. The start time of the previous time period; $T_{2} = T_{0} - 2T$

_Adoption events by user ( $a_{E}\{u\}$ )_

:   The set of all adoption events for each user

#### Formulas

_Latest adoption event by user ( $la_{E}\{u\}$ )_

:   Given the set of all adoption events $a_{E}\{u\}$ for a given user, we simply select the latest timestamp

    $$
    la_{E}\{u\} = max(a_{E}\{u\})
    $$

_Active users_

:   Given the set of all _latest adoption events by user ( $la_{E}\{u\}$ )_ above and the timestamp of the start of the time period we are measuring ( $T_{1}$ ), we then evaluate a binary expression to determine whether the user is "active":

    $$
    la_{E}\{u\} > T_{1}
    $$

    We can then count the total _existing active users_ based on the above filter:

    $$
    u_{E} = count(la_{E}\{u\} > T_{1})
    $$

**_Retention Rate_**

:   Explain

    $$
    RR = \left(\frac{u_{E} - u_{N}}{u_{S}}\right) * 100
    $$

### :fontawesome-solid-people-roof: __Operational efficiency__

As our platforms get adopted and we start seeing success from a user perspective, it becomes important to monitor the financial sustainability of maintaining and evolving the platforms as they grow. This helps ensure that we are actually getting a _return on investment_ as the platform scales. To track this, we measure _operational efficiency_ -- the ratio of effort required to maintain and evolve the platform to level of active adoption of the platform.

The simplest way to calculate _operational efficiency_ is by comparing the number of people maintaining the platform to the number of active _users_ the platform has.

#### Data Points

#### Formulas

_Active users_

:   Given the set of all _latest adoption events by user ( $la_{E}\{u\}$ )_ above and the timestamp of the start of the time period we are measuring ( $T_{1}$ ), we then evaluate a binary expression to determine whether the user is "active":

    $$
    la_{E}\{u\} > T_{1}
    $$

    We can then count the total _existing active users_ based on the above filter:

    $$
    u_{E} = count(la_{E}\{u\} > T_{1})
    $$

**_Operational Efficiency_**

:   Given the number of currently active users ( $u_{E}$ ) and the number of full time employees ( $S_{fte}$ ) supporting the tech, we calculate operational efficiency ( $OR$ ) using a simple ratio:

    $$
    OR = \frac{S_{fte}}{u_{E}}
    $$

### :material-account-heart-outline: __Developer Satisfaction__

Measures the extent to which the platform is meeting the needs and wants of development

## What does "good" look like?

As with most of our [outcomes](index.md), there is no universal definition of "good" and "bad" tech adoption metrics. The expectation is simply that:

a. We are measuring them consistently for our platforms
b. The metrics improve over time

### Emerging vs Established Tech

In the spirit of lean, these bridge outcomes are all about helping organizations in the pursuit of perfectiuon, knowling full well that we'll likely never acheive it. With that, we believe that adoption and reuse of technology can always be improved. However, as certain tools and platforms mature, the areas that are easiest to improve will likely shift. At the beginning of the product lifecycle, it will be all about driving adoption of new users. That means that _adoption lead time_ and _adoption rate_ will be where we are likely to focus. However, as these products mature and we succeed in driving adoption, we may hit plateaus in lead times and adoption rates, as we might eventually capture the entire target audience, and improve the onboarding experience as much as we reasonably can. At that point, it might be time to focus on retaining those users, making sure that they are happy, and then driving extra value out of the platform through maintenance efficiency.