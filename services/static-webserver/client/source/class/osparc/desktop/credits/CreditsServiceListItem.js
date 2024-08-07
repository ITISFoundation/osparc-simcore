/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.credits.CreditsServiceListItem", {
  extend: osparc.ui.list.ListItem,

  construct: function() {
    this.base(arguments);

    const layout = this._getLayout();
    layout.setSpacingX(10);
    layout.setSpacingY(5);
    layout.setColumnFlex(this.self().GRID.ICON.column, 0);
    layout.setColumnFlex(this.self().GRID.NAME.column, 1);
    layout.setColumnFlex(this.self().GRID.CREDITS.column, 0);
  },

  properties: {
    service: {
      check: "Object",
      init: null,
      nullable: true,
      apply: "__applyService"
    },

    credits: {
      check: "Number",
      init: null,
      nullable: true,
      apply: "__applyCredits"
    }
  },

  statics: {
    GRID: {
      ICON: {
        column: 0,
        row: 0,
        rowSpan: 2
      },
      NAME: {
        column: 1,
        row: 0,
        rowSpan: 1
      },
      PERCENTAGE: {
        column: 1,
        row: 1,
        rowSpan: 1
      },
      CREDITS: {
        column: 2,
        row: 0,
        rowSpan: 2
      }
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "card-holder-name":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: this.self().GRID.NAME
          });
          break;
        case "card-type":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: this.self().GRID.TYPE
          });
          break;
        case "card-number-masked":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: this.self().GRID.MASKED_NUMBER
          });
          break;
        case "expiration-date":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this._add(control, {
            row: 0,
            column: this.self().GRID.EXPIRATION_DATE
          });
          break;
        case "details-button":
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/info/14"
          });
          control.addListener("execute", () => this.fireDataEvent("openPaymentMethodDetails", this.getKey()));
          this._add(control, {
            row: 0,
            column: this.self().GRID.INFO_BUTTON
          });
          break;
        case "delete-button":
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/trash/14"
          });
          control.addListener("execute", () => this.__deletePressed());
          this._add(control, {
            row: 0,
            column: this.self().GRID.DELETE_BUTTON
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __deletePressed: function() {
      const msg = this.tr("Are you sure you want to delete the Payment Method?");
      const win = new osparc.ui.window.Confirmation(msg).set({
        confirmText: this.tr("Delete"),
        confirmAction: "delete"
      });
      win.center();
      win.open();
      win.addListener("close", () => {
        if (win.getConfirmed()) {
          this.fireDataEvent("deletePaymentMethod", this.getKey());
        }
      });
    }
  }
});
