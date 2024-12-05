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
      center: true,
      decorator: "rounded",
    });

    this.setUnitData(new osparc.pricing.UnitData(pricingUnit));
  },

  events: {
    "editPricingUnit": "qx.event.type.Event"
  },

  properties: {
    unitData: {
      check: "osparc.pricing.UnitData",
      nullable: false,
      init: null,
      apply: "__buildLayout"
    },

    showAwsSpecificInfo: {
      check: "Boolean",
      init: null,
      nullable: true,
      event: "changeShowAwsSpecificInfo"
    },

    showUnitExtraInfo: {
      check: "Boolean",
      init: true,
      nullable: true,
      event: "changeShowUnitExtraInfo"
    },

    showEditButton: {
      check: "Boolean",
      init: null,
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
        case "awsSpecificInfo":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control);
          break;
        case "unitExtraInfo":
          control = new qx.ui.basic.Label().set({
            font: "text-13",
            rich: true,
          });
          this._add(control);
          break;
        case "edit-button":
          control = new qx.ui.form.Button(qx.locale.Manager.tr("Edit"));
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function(pricingUnit) {
      this._removeAll();
      this._setLayout(new qx.ui.layout.VBox(5));

      const unitName = this.getChildControl("name");
      pricingUnit.bind("unitName", unitName, "value");

      // add price info
      const price = this.getChildControl("price");
      pricingUnit.bind("currentCostPerUnit", price, "value", {
        converter: v => qx.locale.Manager.tr("Credits/h") + ": " + v,
      });

      // add aws specific info
      if ("specificInfo" in pricingUnit) {
        const specificInfo = this.getChildControl("awsSpecificInfo");
        pricingUnit.bind("awsSpecificInfo", specificInfo, "value", {
          converter: v => qx.locale.Manager.tr("EC2") + ": " + v,
        });
        this.bind("showAwsSpecificInfo", specificInfo, "visibility", {
          converter: show => show ? "visible" : "excluded"
        })
      }

      // add pricing unit extra info
      const unitExtraInfo = this.getChildControl("unitExtraInfo");
      let text = "";
      Object.entries(pricingUnit.getUnitExtraInfo()).forEach(([key, value]) => {
        text += `${key}: ${value}<br>`;
      });
      unitExtraInfo.setValue(text);
      this.bind("showUnitExtraInfo", unitExtraInfo, "visibility", {
        converter: show => show ? "visible" : "excluded"
      })

      // add edit button
      const editButton = this.getChildControl("edit-button");
      this.bind("showEditButton", editButton, "visibility", {
        converter: show => show ? "visible" : "excluded"
      })
      editButton.addListener("execute", () => this.fireEvent("editPricingUnit"));
    }
  }
});
