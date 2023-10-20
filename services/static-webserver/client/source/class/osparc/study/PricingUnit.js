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

qx.Class.define("osparc.study.PricingUnit", {
  extend: qx.ui.form.ToggleButton,

  construct: function(pricingUnit) {
    this.base(arguments);

    this.set({
      padding: 10,
      center: true
    });
    this.getContentElement().setStyles({
      "border-radius": "4px"
    });

    this.__pricingUnit = pricingUnit;

    this.__buildLayout();
  },

  properties: {
    advanced: {
      check: "Boolean",
      init: null,
      nullable: true,
      event: "changeAdvanced",
      apply: "__buildLayout"
    }
  },

  members: {
    __pricingUnit: null,

    __buildLayout: function() {
      const pricingUnit = this.__pricingUnit;

      this._removeAll();
      if (this.isAdvanced()) {
        this._setLayout(new qx.ui.layout.VBox(5));

        this._add(new qx.ui.basic.Label().set({
          value: pricingUnit.unitName,
          font: "text-16"
        }));
        // add price info
        this._add(new qx.ui.basic.Label().set({
          value: qx.locale.Manager.tr("Credits/h") + ": " + pricingUnit.currentCostPerUnit,
          font: "text-14"
        }));
        // add pricing unit extra info
        if ("unitExtraInfo" in pricingUnit) {
          Object.entries(pricingUnit.unitExtraInfo).forEach(([key, value]) => {
            this._add(new qx.ui.basic.Label().set({
              value: key + ": " + value,
              font: "text-13"
            }));
          });
        }
      } else {
        this._setLayout(new qx.ui.layout.HBox(5));
        this._add(new qx.ui.basic.Label().set({
          value: pricingUnit.unitName + ": " + pricingUnit.currentCostPerUnit + " C/h",
          font: "text-16"
        }));
      }
    },

    getPricingUnit: function() {
      return this.__pricingUnit;
    }
  }
});
