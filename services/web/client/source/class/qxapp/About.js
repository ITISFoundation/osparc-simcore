/* eslint no-warning-comments: "off" */
qx.Class.define("qxapp.About", {
  extend: qx.ui.window.Window,
  type: "singleton",

  construct: function() {
    this.base(arguments, this.tr("About"));
    this.set({
      layout: new qx.ui.layout.VBox(),
      contentPadding: 20,
      showMaximize: false,
      showMinimize: false,
      resizable: false,
      centerOnAppear: true
    });
    this.__populateEntries();
  },

  members: {
    __populateEntries: function() {
      // All these items and versions should be red from a file
      this.add(this.__createEntry("oSPARC UI", "3.38"));
      this.add(new qx.ui.core.Spacer(null, 10));
      let libInfo = qx.core.Environment.get("qx.libraryInfoMap");
      if (libInfo) {
        for (let key in libInfo) {
          let lib = libInfo[key];
          this.add(this.__createEntry(lib.name || "unknown library", lib.version || "unknown-version"));
        }
        this.add(new qx.ui.core.Spacer(null, 10));
      }
      [
        ["Ajv", "6.5.0"],
        ["svg.js", "2.6.4"],
        ["socket.io", "2.1.2"],
        ["jsondiffpatch", "0.3.11"]
      ].forEach(r => this.add(this.__createEntry(r[0], r[1])));
      this.add(new qx.ui.core.Spacer(null, 10));
      this.add(this.__createEntry("qooxdoo-compiler", qx.core.Environment.get("qx.compilerVersion")));
    },

    __createEntry: function(item, version) {
      let entryLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
        marginBottom: 4
      });

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
