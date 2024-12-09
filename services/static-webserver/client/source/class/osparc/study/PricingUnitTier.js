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

qx.Class.define("osparc.study.PricingUnitTier", {
  extend: osparc.study.PricingUnit,

  events: {
    "editPricingUnit": "qx.event.type.Event",
  },

  properties: {
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
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
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
      }
      return control || this.base(arguments, id);
    },

    // override
    _buildLayout: function(pricingUnit) {
      this.base(arguments, pricingUnit);

      // add price info
      const price = this.getChildControl("price");
      pricingUnit.bind("cost", price, "value", {
        converter: v => qx.locale.Manager.tr("Credits/h") + ": " + v
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
      Object.entries(pricingUnit.getExtraInfo()).forEach(([key, value]) => {
        text += `${key}: ${value}<br>`;
      });
      unitExtraInfo.setValue(text);
      this.bind("showUnitExtraInfo", unitExtraInfo, "visibility", {
        converter: show => show ? "visible" : "excluded"
      });

      // add edit button
      const editButton = this.getChildControl("edit-button");
      this.bind("showEditButton", editButton, "visibility", {
        converter: show => show ? "visible" : "excluded"
      })
      editButton.addListener("execute", () => this.fireEvent("editPricingUnit"));
    }
  }
});
