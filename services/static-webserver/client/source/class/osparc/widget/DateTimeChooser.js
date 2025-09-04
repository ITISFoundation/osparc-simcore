/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.widget.DateTimeChooser", {
  extend: osparc.ui.window.Window,

  construct: function(winTitle, value) {
    this.base(arguments, winTitle || this.tr("Choose a Date and Time"));

    const width = 260;
    const height = 26;
    this.set({
      layout: new qx.ui.layout.VBox(10),
      autoDestroy: true,
      modal: true,
      width,
      height,
      showMaximize: false,
      showMinimize: false,
      showClose: true,
      resizable: false,
      clickAwayClose: false,
    });

    const dateTimeField = this.getChildControl("date-time-field");
    if (value) {
      dateTimeField.setValue(value);
    }
    this.getChildControl("cancel-button");
    this.getChildControl("save-button");

    this.center();

    this.__attachEventHandlers();
  },

  events: {
    "dateChanged": "qx.event.type.Data",
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "date-time-field":
          control = new osparc.ui.form.DateTimeField();
          this.add(control);
          break;
        case "buttons-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignX: "right"
          }));
          this.add(control);
          break;
        case "cancel-button":
          control = new qx.ui.form.Button(this.tr("Cancel")).set({
            appearance: "form-button-text",
          });
          control.addListener("execute", () => this.close(), this);
          this.getChildControl("buttons-layout").add(control);
          break;
        case "save-button": {
          control = new qx.ui.form.Button(this.tr("Save")).set({
            appearance: "form-button",
          });
          control.addListener("execute", e => {
            const dateTimeField = this.getChildControl("date-time-field");
            const data = {
              newValue: dateTimeField.getValue()
            };
            this.fireDataEvent("dateChanged", data);
          }, this);
          this.getChildControl("buttons-layout").add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __attachEventHandlers: function() {
      let command = new qx.ui.command.Command("Enter");
      command.addListener("execute", () => {
        this.getChildControl("save-button").execute();
        command.dispose();
        command = null;
      });

      let commandEsc = new qx.ui.command.Command("Esc");
      commandEsc.addListener("execute", () => {
        this.close();
        commandEsc.dispose();
        commandEsc = null;
      });
    }
  }
});
