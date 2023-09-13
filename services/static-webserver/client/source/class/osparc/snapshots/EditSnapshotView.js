/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.snapshots.EditSnapshotView", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__buildForm();
  },

  events: {
    "takeSnapshot": "qx.event.type.Event",
    "cancel": "qx.event.type.Event"
  },

  members: {
    __form: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "tags":
          control = new qx.ui.form.TextField();
          break;
        case "message":
          control = new qx.ui.form.TextArea().set({
            autoSize: true,
            minimalLineHeight: 3
          });
          break;
        case "cancel-button": {
          control = new qx.ui.form.Button(this.tr("Cancel")).set({
            allowGrowX: false
          });
          const commandEsc = new qx.ui.command.Command("Enter");
          control.setCommand(commandEsc);
          control.addListener("execute", () => this.fireEvent("cancel"));
          break;
        }
        case "ok-button": {
          control = new qx.ui.form.Button(this.tr("OK")).set({
            allowGrowX: false
          });
          const commandEnter = new qx.ui.command.Command("Enter");
          control.setCommand(commandEnter);
          control.addListener("execute", () => {
            // releaseCapture to make sure all changes are applied
            this.__renderer.releaseCapture();
            this.fireEvent("takeSnapshot");
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __buildForm: function() {
      const form = this.__form = new qx.ui.form.Form();
      const renderer = this.__renderer = new qx.ui.form.renderer.Single(form);
      this._add(renderer);

      const tags = this.getChildControl("tags");
      form.add(tags, "Tags", null, "tags");

      const message = this.getChildControl("message");
      form.add(message, "Message", null, "message");

      // buttons
      const cancelButton = this.getChildControl("cancel-button");
      form.addButton(cancelButton);
      const okButton = this.getChildControl("ok-button");
      form.addButton(okButton);
    },

    getTag: function() {
      return this.__form.getItem("tags").getValue();
    },

    getMessage: function() {
      return this.__form.getItem("message").getValue();
    }
  }
});
