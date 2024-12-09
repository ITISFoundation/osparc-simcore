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

qx.Class.define("osparc.study.PricingUnitLicense", {
  extend: osparc.study.PricingUnit,

  events: {
    "rentPricingUnit": "qx.event.type.Event",
  },

  properties: {
    showRentButton: {
      check: "Boolean",
      init: false,
      nullable: true,
      event: "changeShowRentButton"
    },
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "rent-button":
          control = new qx.ui.form.Button(qx.locale.Manager.tr("Rent")).set({
            appearance: "strong-button",
            center: true,
          });
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    // override
    _buildLayout: function(pricingUnit) {
      this.base(arguments, pricingUnit);

      // add price info
      const price = this.getChildControl("price");
      pricingUnit.bind("cost", price, "value", {
        converter: v => qx.locale.Manager.tr("Credits") + ": " + v
      });

      // add rent button
      const rentButton = this.getChildControl("rent-button");
      this.bind("showRentButton", rentButton, "visibility", {
        converter: show => show ? "visible" : "excluded"
      })
      rentButton.addListener("execute", () => this.fireEvent("rentPricingUnit"));
    }
  }
});
