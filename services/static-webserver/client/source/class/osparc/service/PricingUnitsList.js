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

qx.Class.define("osparc.service.PricingUnitsList", {
  extend: qx.ui.core.Widget,

  construct: function(serviceMetadata) {
    this.base(arguments);

    this.__serviceMetadata = serviceMetadata;

    this._setLayout(new qx.ui.layout.VBox(5));

    this.getChildControl("pricing-units-container");

    this.__fetchUnits();
  },

  members: {
    __serviceMetadata: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "pricing-units-container":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
          this._addAt(control, 0, {
            flex: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __fetchUnits: function() {
      const plansParams = {
        url: osparc.data.Resources.getServiceUrl(
          this.__serviceMetadata["key"],
          this.__serviceMetadata["version"]
        )
      };
      osparc.data.Resources.fetch("services", "pricingPlans", plansParams)
        .then(data => this.__populateList(data["pricingUnits"]))
        .catch(err => {
          console.error(err);
          this.__populateList([]);
        });
    },

    __populateList: function(pricingUnits) {
      this.getChildControl("pricing-units-container").removeAll();

      if (pricingUnits.length) {
        const pUnits = new osparc.study.PricingUnits(pricingUnits, null, false);
        this.getChildControl("pricing-units-container").add(pUnits);
      } else {
        const notFound = new qx.ui.basic.Label().set({
          value: this.tr("No Tiers found"),
          font: "text-14"
        });
        this.getChildControl("pricing-units-container").add(notFound);
      }
    }
  }
});
