/* eslint no-warning-comments: "off" */
qx.Class.define("qxapp.About", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    let versionsLayout = new qx.ui.layout.VBox();
    this._setLayout(versionsLayout);

    this.__populateEntries();
  },

  members: {
    __populateEntries: function() {
      // All these items and versions should be red from a file
      this._add(this.__createEntry("oSPARC UI", "3.38"));
      this._add(new qx.ui.core.Spacer(null, 10));
      this._add(this.__createEntry("qx-compiler", "0.2.22"));
      this._add(this.__createEntry("qooxdoo-sdk", "6.0.0-alpha-20181212"));
      this._add(this.__createEntry("contrib/qx-osparc-theme", "0.3.0"));
      this._add(this.__createEntry("contrib/qx-iconfont-material", "0.1.0"));
      this._add(this.__createEntry("contrib/qx-iconfont-fontawesome5", "0.0.4"));
      this._add(new qx.ui.core.Spacer(null, 10));
      this._add(this.__createEntry("Ajv", "6.5.0"));
      this._add(this.__createEntry("svg.js", "2.6.4"));
      this._add(this.__createEntry("socket.io", "2.1.2"));
    },

    __createEntry: function(item, version) {
      let entryLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

      const title14Font = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["title-14"]);
      let entryLabel = new qx.ui.basic.Label(item).set({
        font: title14Font
      });
      entryLayout.add(entryLabel);

      const text14Font = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["text-14"]);
      let entryVersion = new qx.ui.basic.Label(version).set({
        font: text14Font
      });
      entryLayout.add(entryVersion);

      return entryLayout;
    }
  }
});
