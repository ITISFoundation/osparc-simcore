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

/**
 *
 */

qx.Class.define("osparc.desktop.preferences.window.CreateAPIKey", {
  extend: osparc.desktop.preferences.window.APIKeyBase,

  construct: function() {
    const caption = this.tr("Create API Key");
    const infoText = this.tr("Key names must be unique.");
    this.base(arguments, caption, infoText);

    this.__populateWindow();
  },

  events: {
    "finished": "qx.event.type.Data"
  },

  members: {
    __populateWindow: function() {
      const hBox1 = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      const sTitle = new qx.ui.basic.Label(this.tr("API Key")).set({
        width: 50,
        alignY: "middle"
      });
      hBox1.add(sTitle);
      const labelEditor = new qx.ui.form.TextField();
      this.add(labelEditor, {
        flex: 1
      });
      hBox1.add(labelEditor, {
        flex: 1
      });
      this.add(hBox1);

      const hBox2 = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      hBox2.add(new qx.ui.core.Spacer(), {
        flex: 1
      });
      const confirmBtn = new qx.ui.form.Button(this.tr("Confirm"));
      confirmBtn.addListener("execute", e => {
        const keyLabel = labelEditor.getValue();
        this.fireDataEvent("finished", keyLabel);
      }, this);
      hBox2.add(confirmBtn);

      this.add(hBox2);
    }
  }
});
