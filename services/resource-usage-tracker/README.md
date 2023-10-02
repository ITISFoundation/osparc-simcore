# resource usage tracker


Service that collects and stores computational resources usage used in osparc-simcore. Also takes care of computation of used osparc credits.


## Credit computation (Collections)
- **PricingPlan**:
  Describe the overall billing plan/package. The pricing plan can be connected to one or more services. A specific pricing plan might be defined also for billing storage costs.
- **PricingUnit**:
  Specifies the various units/tiers within a pricing plan, that denote different options (resources and costs) for running services/storage costs. For example: a specific pricing plan might offer three tiers based on resources: SMALL, MEDIUM, and LARGE.
- **PricingUnitCreditCost**:
  Defines the credit cost for each unit, which can change over time, allowing for pricing flexibility.
