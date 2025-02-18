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

    licenseUrl: {
      check: "String",
      init: false,
      nullable: true,
      event: "changeLicenseUrl"
    },
  },

  statics: {
    getExpirationDate: function() {
      const expirationDate = new Date();
      expirationDate.setFullYear(expirationDate.getFullYear() + 1); // hardcoded for now: rented for one year from now
      return expirationDate;
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
          control.addListener("execute", () => this.__rentUnit());
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
    },

    __rentUnit: function() {
      const nCredits = this.getUnitData().getCost();
      const expirationDate = osparc.study.PricingUnitLicense.getExpirationDate();
      let msg = this.getUnitData().getName() + this.tr(" will be available until ") + osparc.utils.Utils.formatDate(expirationDate);
      msg += "<br>";
      msg += `The rental will cost ${nCredits} credits`;
      const confirmationWin = new osparc.ui.window.Confirmation(msg).set({
        caption: this.tr("Rent"),
        confirmText: this.tr("Rent"),
      });

      if (this.getLicenseUrl()) {
        const useCacheCB = new qx.ui.form.CheckBox().set({
          value: false,
          label: this.tr("Accept <u>Terms and Conditions</u>"),
          rich: true,
        });
        useCacheCB.getChildControl("label").set({
          anonymous: false,
          cursor: "pointer",
        });
        useCacheCB.getChildControl("label").addListener("tap", () => this.__openLicense());
        confirmationWin.addWidget(useCacheCB);
        confirmationWin.getExtraWidgetsLayout().setPaddingTop(0); // reset paddingTop
        useCacheCB.bind("value", confirmationWin.getConfirmButton(), "enabled");
      }

      confirmationWin.open();
      confirmationWin.addListener("close", () => {
        if (confirmationWin.getConfirmed()) {
          this.fireEvent("rentPricingUnit");
        }
      }, this);
    },

    __openLicense: function() {
      const mdWindow = new osparc.ui.markdown.MarkdownWindow(this.getLicenseUrl()).set({
        caption: this.tr("Terms and Conditions"),
        width: 800,
        height: 600,
      });
      mdWindow.open();
    },
  }
});
