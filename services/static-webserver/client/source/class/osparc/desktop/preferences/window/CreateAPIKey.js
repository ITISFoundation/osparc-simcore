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
    __form: null,

    __populateWindow: function() {
      const form = this.__form = new qx.ui.form.Form();

      const keyName = new qx.ui.form.TextField().set({
        required: true
      });
      form.add(keyName, this.tr("Key Name"), null, "name");
      this.addListener("appear", () => keyName.focus());

      const dateFormat = new qx.util.format.DateFormat("dd/MM/yyyy-HH:mm:ss");
      const expirationDate = new qx.ui.form.DateField();
      form.add(expirationDate, this.tr("Expiration Date"), null, "expiration");
      expirationDate.addListener("changeValue", e => {
        const date = e.getData();
        if (date) {
          // allow only future dates
          if (new Date() > new Date(date)) {
            const msg = this.tr("Choose a future date");
            osparc.FlashMessenger.logAs(msg, "WARNING");
            expirationDate.resetValue();
          } else {
            expirationDate.setDateFormat(dateFormat);
          }
        }
      });

      const formRenderer = new qx.ui.form.renderer.Single(form);
      this.add(formRenderer);

      const hBox2 = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      hBox2.add(new qx.ui.core.Spacer(), {
        flex: 1
      });
      const confirmBtn = new qx.ui.form.Button(this.tr("Confirm"));
      confirmBtn.addListener("execute", () => {
        this.fireDataEvent("finished", {
          name: form.getItem("name").getValue(),
          expiration: form.getItem("expiration").getValue()
        });
      }, this);
      hBox2.add(confirmBtn);

      this.add(hBox2);
    }
  }
});
