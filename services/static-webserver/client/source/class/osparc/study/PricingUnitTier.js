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
    "selectPricingUnit": "qx.event.type.Event",
  },

  properties: {
    showAwsSpecificInfo: {
      check: "Boolean",
      init: false,
      nullable: true,
      event: "changeShowAwsSpecificInfo"
    },

    showUnitExtraInfo: {
      check: "Boolean",
      init: true,
      nullable: true,
      event: "changeShowUnitExtraInfo"
    },

    showSelectButton: {
      check: "Boolean",
      init: false,
      nullable: true,
      event: "changeShowSelectButton"
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
          this.bind("showAwsSpecificInfo", control, "visibility", {
            converter: show => show ? "visible" : "excluded"
          })
          this._add(control);
          break;
        case "unitExtraInfoLayout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(2));
          this.bind("showUnitExtraInfo", control, "visibility", {
            converter: show => show ? "visible" : "excluded"
          });
          this._add(control);
          break;
        case "select-button":
          control = new qx.ui.form.Button().set({
            appearance: "strong-button",
            center: true,
          });
          this.bind("selected", control, "label", {
            converter: selected => selected ? "Selected" : "Select"
          });
          this.bind("selected", control, "icon", {
            converter: selected => selected ? "@FontAwesome5Solid/check/12" : null
          });
          this.bind("showSelectButton", control, "visibility", {
            converter: show => show ? "visible" : "excluded"
          });
          control.addListener("execute", () => this.fireEvent("selectPricingUnit"));
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
      }

      // add pricing unit extra info
      const unitExtraInfoLayout = this.getChildControl("unitExtraInfoLayout");
      Object.entries(pricingUnit.getExtraInfo()).forEach(([key, value]) => {
        let icon = "";
        let toolTipText = "";
        switch (key) {
          case "CPU":
            icon = "@FontAwesome5Solid/microchip/13";
            toolTipText = qx.locale.Manager.tr("CPU");
            break;
          case "RAM":
            icon = "@FontAwesome5Solid/server/13";
            toolTipText = qx.locale.Manager.tr("RAM");
            break;
          case "VRAM":
            icon = "@FontAwesome5Solid/desktop/13";
            toolTipText = qx.locale.Manager.tr("VRAM");
            break;
          case "SSD":
            icon = "@FontAwesome5Solid/hdd/13";
            toolTipText = qx.locale.Manager.tr("SSD");
            break;
        }
        const atom = new qx.ui.basic.Atom().set({
          label: String(value),
          icon,
          toolTipText,
          font: "text-13",
          gap: 5,
        });
        unitExtraInfoLayout.add(atom);
      });

      // add select button
      this.getChildControl("select-button");

      // add edit button
      this.getChildControl("edit-button");
    }
  }
});
