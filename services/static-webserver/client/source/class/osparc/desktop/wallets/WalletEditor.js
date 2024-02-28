/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.wallets.WalletEditor", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(8));

    this.__validator = new qx.ui.form.validation.Manager();

    this.__buildLayout()
  },

  properties: {
    walletId: {
      check: "Number",
      init: 0,
      nullable: false,
      event: "changeWalletId"
    },

    name: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeName"
    },

    description: {
      check: "String",
      init: "",
      nullable: true,
      event: "changeDescription"
    },

    isFetching: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeIsFetching"
    }
  },

  events: {
    "updateWallet": "qx.event.type.Event",
    "cancel": "qx.event.type.Event"
  },

  members: {
    __buildLayout: function() {
      this._removeAll()
      this._add(new qx.ui.basic.Label(this.tr("Title")).set({
        font: "text-14"
      }));
      const title = new qx.ui.form.TextField().set({
        font: "text-14",
        backgroundColor: "background-main",
        placeholder: this.tr("Title"),
        height: 35,
        required: true
      });
      this.bind("name", title, "value");
      title.bind("value", this, "name");
      this._add(title);
      this.__validator.add(title)

      this._add(new qx.ui.basic.Label(this.tr("Description")).set({
        font: "text-14",
        marginTop: 10
      }));
      const description = new qx.ui.form.TextArea().set({
        font: "text-14",
        placeholder: this.tr("Description"),
        autoSize: true,
        minHeight: 70,
        maxHeight: 140
      });
      this.bind("description", description, "value");
      description.bind("value", this, "description");
      this._add(description);

      const buttons = new qx.ui.container.Composite(new qx.ui.layout.HBox(8).set({
        alignX: "right"
      }));
      const cancelButton = new qx.ui.form.Button(this.tr("Cancel"));
      cancelButton.addListener("execute", () => this.fireEvent("cancel"), this);
      buttons.add(cancelButton);

      const saveButton = new osparc.ui.form.FetchButton(this.tr("Save"));
      saveButton.addListener("execute", () => {
        if (this.__validator.validate()) {
          this.fireEvent("updateWallet");
        }
      }, this);
      this.bind("isFetching", saveButton, "fetching")
      buttons.addAt(saveButton, 0);
      this._add(buttons);
    }
  }
});
