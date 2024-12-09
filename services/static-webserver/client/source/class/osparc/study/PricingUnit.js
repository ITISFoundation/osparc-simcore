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
  type: "abstract",

  construct: function(pricingUnit) {
    this.base(arguments);

    this.set({
      padding: 10,
      center: true,
      decorator: "rounded",
    });

    this.setUnitData(pricingUnit);
  },

  properties: {
    unitData: {
      check: "osparc.data.model.PricingUnit",
      nullable: false,
      init: null,
      apply: "_buildLayout"
    },
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "name":
          control = new qx.ui.basic.Label().set({
            font: "text-16"
          });
          this._add(control);
          break;
        case "price":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function(pricingUnit) {
      this._removeAll();
      this._setLayout(new qx.ui.layout.VBox(5));

      const name = this.getChildControl("name");
      pricingUnit.bind("name", name, "value");
    }
  }
});
