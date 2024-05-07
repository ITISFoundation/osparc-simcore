/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.node.TierSelectionView", {
  extend: osparc.node.ServiceOptionsView,

  events: {
    "tierChanged": "qx.event.type.Event"
  },

  members: {
    _applyNode: function(node) {
      this.__populateLayout();

      this.base(arguments, node);
    },

    __populateLayout: function() {
      this._removeAll();

      this._add(new qx.ui.basic.Label(this.tr("Tiers")).set({
        font: "text-14"
      }));

      const tierBox = new qx.ui.form.SelectBox().set({
        allowGrowX: false
      });
      this._add(tierBox);

      const node = this.getNode();
      const plansParams = {
        url: osparc.data.Resources.getServiceUrl(
          node.getKey(),
          node.getVersion()
        )
      };
      osparc.data.Resources.fetch("services", "pricingPlans", plansParams)
        .then(pricingPlans => {
          if (pricingPlans && "pricingUnits" in pricingPlans && pricingPlans["pricingUnits"].length) {
            const pUnits = pricingPlans["pricingUnits"];
            pUnits.forEach(pUnit => {
              const tItem = new qx.ui.form.ListItem(pUnit.unitName, null, pUnit.pricingUnitId);
              tierBox.add(tItem);
            });
            const unitParams = {
              url: {
                studyId: node.getStudy().getUuid(),
                nodeId: node.getNodeId()
              }
            };
            osparc.data.Resources.fetch("studies", "getPricingUnit", unitParams)
              .then(preselectedPricingUnit => {
                if (preselectedPricingUnit && preselectedPricingUnit["pricingUnitId"]) {
                  const tierFound = tierBox.getSelectables().find(t => t.getModel() === preselectedPricingUnit["pricingUnitId"]);
                  tierBox.setSelection([tierFound]);
                }
              });
          }
        });
    }
  }
});
