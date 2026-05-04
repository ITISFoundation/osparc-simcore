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

  /**
   * @param {Object} serviceMetadata
   */
  construct: function(serviceMetadata) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.getChildControl("pricing-units-container");

    this.setServiceMetadata(serviceMetadata);
  },

  properties: {
    serviceMetadata: {
      check: "Object",
      init: null,
      apply: "__fetchUnits",
    },
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "intro-label":
          control = osparc.dashboard.ResourceDetails.createIntroLabel(this.tr("Below is an overview of the available tiers, including their hourly credit cost and hardware specifications. The highlighted tier indicates the default configuration for new projects."));
          this._addAt(control, 0);
          break;
        case "pricing-units-container":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
          this._addAt(control, 1, {
            flex: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __fetchUnits: function() {
      const serviceMetadata = this.getServiceMetadata();
      if (!serviceMetadata) {
        return;
      }
      osparc.store.Services.getPricingPlan(serviceMetadata["key"], serviceMetadata["version"])
        .then(data => this.__populateList(data["pricingUnits"]))
        .catch(err => {
          console.error(err);
          this.__populateList([]);
        });
    },

    __populateList: function(pricingUnitsData) {
      const introLabel = this.getChildControl("intro-label");
      const container = this.getChildControl("pricing-units-container");
      container.removeAll();

      if (pricingUnitsData.length) {
        introLabel.show();
        const pUnits = new osparc.study.PricingUnitTiers(pricingUnitsData, null, false);
        container.add(pUnits);
      } else {
        introLabel.exclude();
        const notFound = new qx.ui.basic.Label().set({
          value: this.tr("No Tiers found"),
          font: "text-14"
        });
        container.add(notFound);
      }
    },
  }
});
