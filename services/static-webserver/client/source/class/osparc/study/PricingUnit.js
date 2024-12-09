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

  events: {
    "editPricingUnit": "qx.event.type.Event",
  },

  properties: {
    unitData: {
      check: "osparc.data.model.PricingUnit",
      nullable: false,
      init: null,
      apply: "_buildLayout"
    },

    showEditButton: {
      check: "Boolean",
      init: false,
      nullable: true,
      event: "changeShowEditButton"
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
        case "edit-button":
          control = new qx.ui.form.Button(qx.locale.Manager.tr("Edit"));
          this.bind("showEditButton", control, "visibility", {
            converter: show => show ? "visible" : "excluded"
          });
          control.addListener("execute", () => this.fireEvent("editPricingUnit"));
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
