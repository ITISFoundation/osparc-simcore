/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.pricing.PlanManager", {
  extend: osparc.po.BaseView,

  members: {
    _buildLayout: function() {
      const stack = new qx.ui.container.Stack();
      this._add(stack, {
        flex: 1
      });

      const pricingPlans = new osparc.pricing.Plans();
      stack.add(pricingPlans);

      const pricingPlanDetails = new osparc.pricing.PlanDetails();
      stack.add(pricingPlanDetails);

      stack.setSelection([pricingPlans]);
      pricingPlans.addListener("pricingPlanSelected", e => {
        const pricingPlanModel = e.getData();
        if (pricingPlanModel) {
          stack.setSelection([pricingPlanDetails]);
          pricingPlanDetails.setCurrentPricingPlan(pricingPlanModel);
        }
      });

      pricingPlanDetails.addListener("backToPricingPlans", () => {
        stack.setSelection([pricingPlans]);
      });
    }
  }
});
