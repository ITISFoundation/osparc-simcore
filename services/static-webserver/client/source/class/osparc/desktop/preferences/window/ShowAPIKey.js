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

qx.Class.define("osparc.desktop.preferences.window.ShowAPIKey", {
  extend: osparc.desktop.preferences.window.APIKeyBase,

  construct: function(key, secret, baseUrl) {
    const caption = this.tr("API Key");
    const infoText = this.tr("For your protection, store your access keys securely and do not share them. You will not be able to access the key again once this window is closed.");
    this.base(arguments, caption, infoText);

    this.set({
      clickAwayClose: false
    });

    this.__populateTokens(key, secret, baseUrl);
  },

  members: {
    __populateTokens: function(key, secret, baseUrl) {
      const hBox1 = this.__createEntry(this.tr("<b>Key:</b>"), key);
      this._add(hBox1);

      const hBox2 = this.__createEntry(this.tr("<b>Secret:</b>"), secret);
      this._add(hBox2);

      const hBox3 = this.__createEntry(this.tr("<b>Base url:</b>"), baseUrl);
      this._add(hBox3);

      const buttonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
        appearance: "margined-layout"
      });
      const copyAPIKeyBtn = new qx.ui.form.Button(this.tr("Copy API Key"));
      copyAPIKeyBtn.addListener("execute", e => {
        if (osparc.utils.Utils.copyTextToClipboard(key)) {
          copyAPIKeyBtn.setIcon("@FontAwesome5Solid/check/12");
        }
      });
      buttonsLayout.add(copyAPIKeyBtn, {
        width: "50%"
      });
      const copyAPISecretBtn = new qx.ui.form.Button(this.tr("Copy API Secret"));
      copyAPISecretBtn.addListener("execute", e => {
        if (osparc.utils.Utils.copyTextToClipboard(secret)) {
          copyAPISecretBtn.setIcon("@FontAwesome5Solid/check/12");
        }
      });
      buttonsLayout.add(copyAPISecretBtn, {
        width: "50%"
      });
      this._add(buttonsLayout);
    },

    __createEntry: function(title, label) {
      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
        padding: 5
      });
      const sTitle = new qx.ui.basic.Label(title).set({
        rich: true,
        width: 40
      });
      hBox.add(sTitle);
      const sLabel = new qx.ui.basic.Label();
      if (label) {
        // partially hide the key and secret
        sLabel.setValue(label.substring(1, 8) + "****")
      }
      hBox.add(sLabel);
      return hBox;
    }
  }
});
