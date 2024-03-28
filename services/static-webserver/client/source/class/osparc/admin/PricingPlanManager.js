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

qx.Class.define("osparc.admin.PricingPlanManager", {
  extend: osparc.po.BaseView,

  members: {
    _buildLayout: function() {
      const stack = new qx.ui.container.Stack();
      this.add(stack, {
        flex: 1
      });

      const pricingPlans = new osparc.admin.PricingPlans();
      stack.add(pricingPlans);

      const pricingPlanDetails = new osparc.admin.osparc.admin.PricingPlanDetails();
      stack.add(pricingPlanDetails);

      stack.setSelection([pricingPlans]);
      pricingPlans.addListener("pricingPlanSelected", e => {
        console.log("pricingPlanSelected", e.getData());
        stack.setSelection([pricingPlanDetails]);
      });
    }
  }
});
