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

    this.setUnitData(new osparc.pricing.UnitData(pricingUnit));

    this.__buildLayout();
  },

  events: {
    "editPricingUnit": "qx.event.type.Event"
  },

  properties: {
    unitData: {
      check: "osparc.pricing.UnitData",
      nullable: false,
      init: null
    },

    showSpecificInfo: {
      check: "Boolean",
      init: null,
      nullable: true,
      event: "changeShowSpecificInfo"
    },

    showEditButton: {
      check: "Boolean",
      init: null,
      nullable: true,
      event: "changeShowEditButton"
    },
  },

  members: {
    __buildLayout: function() {
      const pricingUnit = this.getUnitData();

      this._removeAll();
      this._setLayout(new qx.ui.layout.VBox(5));

      const unitName = new qx.ui.basic.Label().set({
        font: "text-16"
      })
      pricingUnit.bind("unitName", unitName, "value");
      this._add(unitName);

      // add price info
      const price = new qx.ui.basic.Label().set({
        font: "text-14"
      })
      pricingUnit.bind("currentCostPerUnit", price, "value", {
        converter: v => qx.locale.Manager.tr("Credits/h") + ": " + v,
      });
      this._add(price);

      // add aws specific info
      if ("specificInfo" in pricingUnit) {
        const label = new qx.ui.basic.Label().set({
          font: "text-14"
        })
        const awsSpecificInfo = new qx.ui.basic.Label().set({
          font: "text-14"
        })
        pricingUnit.bind("awsSpecificInfo", awsSpecificInfo, "value", {
          converter: v => qx.locale.Manager.tr("EC2") + ": " + v,
        });
        this.bind("showSpecificInfo", label, "visibility", {
          converter: show => show ? "visible" : "excluded"
        })
        this._add(label);
      }

      // add pricing unit extra info
      Object.entries(pricingUnit.getUnitExtraInfo()).forEach(([key, value]) => {
        this._add(new qx.ui.basic.Label().set({
          value: key + ": " + value,
          font: "text-13"
        }));
      });

      // add edit button
      const editButton = new qx.ui.form.Button(this.tr("Edit"));
      this.bind("showEditButton", editButton, "visibility", {
        converter: show => show ? "visible" : "excluded"
      })
      this._add(editButton);
      editButton.addListener("execute", () => this.fireEvent("editPricingUnit"));
    }
  }
});
