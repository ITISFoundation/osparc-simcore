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

    this.setPricingUnitId(pricingUnit["pricingUnitId"]);
    this.__pricingUnit = pricingUnit;

    this.__buildLayout();
  },

  events: {
    "editPricingUnit": "qx.event.type.Event"
  },

  properties: {
    pricingUnitId: {
      check: "Number",
      nullable: false,
      init: null
    },

    showSpecificInfo: {
      check: "Boolean",
      init: null,
      nullable: true,
      apply: "__buildLayout"
    },

    showEditButton: {
      check: "Boolean",
      init: null,
      nullable: true,
      apply: "__buildLayout"
    },
  },

  members: {
    __pricingUnit: null,

    __buildLayout: function() {
      const pricingUnit = this.__pricingUnit;

      this._removeAll();
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

      // add aws specific info
      if (this.isShowSpecificInfo()) {
        if ("specificInfo" in pricingUnit) {
          Object.values(pricingUnit.specificInfo).forEach(value => {
            this._add(new qx.ui.basic.Label().set({
              value: "EC2: " + value,
              font: "text-14"
            }));
          });
        }
      }

      // add pricing unit extra info
      if ("unitExtraInfo" in pricingUnit) {
        Object.entries(pricingUnit.unitExtraInfo).forEach(([key, value]) => {
          this._add(new qx.ui.basic.Label().set({
            value: key + ": " + value,
            font: "text-13"
          }));
        });
      }

      if (this.isShowEditButton()) {
        const editButton = new qx.ui.form.Button(this.tr("Edit"));
        this._add(editButton);
        editButton.addListener("execute", () => this.fireEvent("editPricingUnit"));
      }
    },

    getPricingUnit: function() {
      return this.__pricingUnit;
    }
  }
});
