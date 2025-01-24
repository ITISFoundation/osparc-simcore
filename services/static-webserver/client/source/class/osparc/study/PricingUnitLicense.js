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
        case "rental-period":
          control = new qx.ui.basic.Label().set({
            value: this.tr("Duration: 1 year"), // hardcoded for now
            font: "text-14",
          });
          this._add(control);
          break;
        case "rent-button":
          control = new qx.ui.form.Button(this.tr("Rent")).set({
            appearance: "strong-button",
            center: true,
          });
          this.bind("showRentButton", control, "visibility", {
            converter: show => show ? "visible" : "excluded"
          });
          control.addListener("execute", () => this.fireEvent("rentPricingUnit"));
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    // override
    _buildLayout: function(pricingUnit) {
      this.base(arguments, pricingUnit);

      this.getChildControl("rental-period");

      // add price info
      const price = this.getChildControl("price");
      pricingUnit.bind("cost", price, "value", {
        converter: v => this.tr("Credits") + ": " + v
      });

      // add edit button
      this.getChildControl("edit-button");

      // add rent button
      this.getChildControl("rent-button");
    }
  }
});
