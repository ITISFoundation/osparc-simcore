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

qx.Class.define("osparc.study.StudyPricingUnits", {
  extend: qx.ui.container.Composite,

  construct: function(studyData) {
    this.base(arguments);

    this.set({
      layout: new qx.ui.layout.VBox(5)
    });

    this.__studyData = studyData;

    this.__buildLayout();
  },

  events: {
    "loadingUnits": "qx.event.type.Event",
    "unitsReady": "qx.event.type.Event"
  },

  members: {
    __studyData: null,

    __buildLayout: function(nodeIds) {
      const unitsLoading = () => this.fireEvent("loadingUnits");
      const unitsAdded = () => this.fireEvent("unitsReady");
      unitsLoading();
      if ("workbench" in this.__studyData) {
        const promises = [];
        const nodes = Object.values(this.__studyData["workbench"]);
        nodes.forEach(node => {
          if (nodeIds && !nodeIds.includes(node["id"])) {
            return;
          }
          const params = {
            url: osparc.data.Resources.getServiceUrl(
              node["key"],
              node["version"]
            )
          };
          promises.push(osparc.data.Resources.fetch("services", "pricingPlans", params));
        });
        Promise.all(promises)
          .then(values => {
            if (values) {
              this._removeAll();
              const advancedCB = new qx.ui.form.CheckBox().set({
                label: this.tr("Advanced"),
                value: true
              });
              this._add(advancedCB);
              values.forEach((pricingPlans, idx) => {
                const serviceGroup = this.__createPricingUnitsGroup(nodes[idx]["label"], pricingPlans, advancedCB);
                if (serviceGroup) {
                  this._add(serviceGroup);
                  unitsAdded();
                }
              });
            }
          });
      }
    },

    __createPricingUnitsGroup: function(serviceLabel, pricingPlans, advancedCB) {
      if (pricingPlans && "pricingUnits" in pricingPlans && pricingPlans["pricingUnits"].length) {
        const machinesLayout = osparc.study.StudyOptions.createGroupBox(serviceLabel);

        const unitButtons = new osparc.study.PricingUnits(pricingPlans["pricingUnits"]);
        advancedCB.bind("value", unitButtons, "advanced");
        machinesLayout.add(unitButtons);

        return machinesLayout;
      }
      return null;
    }
  }
});
