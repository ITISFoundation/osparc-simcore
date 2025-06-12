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
    const infoText = this.tr("For your security, store your access keys safely. You will not be able to access them again after closing this window.");
    this.base(arguments, caption, infoText);

    this.set({
      clickAwayClose: false
    });

    this.__populateTokens(key, secret, baseUrl);
  },

  members: {
    __populateTokens: function(key, secret, baseUrl) {
      const hBox1 = this.__createStarredEntry(this.tr("<b>Key:</b>"), key);
      this._add(hBox1);

      const hBox2 = this.__createStarredEntry(this.tr("<b>Secret:</b>"), secret);
      this._add(hBox2);

      const hBox3 = this.__createEntry(this.tr("<b>Base url:</b>"), baseUrl);
      this._add(hBox3);

      const buttonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
        appearance: "margined-layout"
      });
      const copyAPIKeyBtn = new qx.ui.form.Button(this.tr("API Key"), "@FontAwesome5Solid/copy/12");
      copyAPIKeyBtn.addListener("execute", e => {
        if (osparc.utils.Utils.copyTextToClipboard(key)) {
          copyAPIKeyBtn.setIcon("@FontAwesome5Solid/check/12");
        }
      });
      buttonsLayout.add(copyAPIKeyBtn, {
        flex: 1
      });
      const copyAPISecretBtn = new qx.ui.form.Button(this.tr("API Secret"), "@FontAwesome5Solid/copy/12");
      copyAPISecretBtn.addListener("execute", e => {
        if (osparc.utils.Utils.copyTextToClipboard(secret)) {
          copyAPISecretBtn.setIcon("@FontAwesome5Solid/check/12");
        }
      });
      buttonsLayout.add(copyAPISecretBtn, {
        flex: 1
      });
      const copyBaseUrlBtn = new qx.ui.form.Button(this.tr("Base URL"), "@FontAwesome5Solid/copy/12");
      copyBaseUrlBtn.addListener("execute", e => {
        if (osparc.utils.Utils.copyTextToClipboard(baseUrl)) {
          copyBaseUrlBtn.setIcon("@FontAwesome5Solid/check/12");
        }
      });
      buttonsLayout.add(copyBaseUrlBtn, {
        flex: 1
      });
      this._add(buttonsLayout);
    },

    __createStarredEntry: function(title, label) {
      const hBox = this.__createEntry(title);
      if (label) {
        // partially hide the key and secret
        hBox.getChildren()[1].setValue(label.substring(0, 8) + "****")
      }
      return hBox;
    },

    __createEntry: function(title, label) {
      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
        padding: 5
      });
      const sTitle = new qx.ui.basic.Label(title).set({
        rich: true,
        width: 60
      });
      hBox.add(sTitle);
      const sLabel = new qx.ui.basic.Label();
      if (label) {
        // partially hide the key and secret
        sLabel.setValue(label);
      }
      hBox.add(sLabel);
      return hBox;
    }
  }
});
