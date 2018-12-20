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
      this.add(this.__createEntry("oSPARC UI", "3.38", "https://github.com/ITISFoundation/osparc-simcore"));
      this.add(new qx.ui.core.Spacer(null, 10));
      this.add(this.__createEntry("qooxdoo-compiler", qx.core.Environment.get("qx.compilerVersion"), "https://github.com/qooxdoo/qooxdoo-compiler"));
      let libInfo = qx.core.Environment.get("qx.libraryInfoMap");
      if (libInfo) {
        for (let key in libInfo) {
          let lib = libInfo[key];
          this.add(this.__createEntry(lib.name || "unknown library", lib.version || "unknown-version"));
        }
      } else {
        // as soon as we upgrade the qooxdoo compiler (v0.2.31) all this info will be in qx.libraryInfoMap
        this.add(this.__createEntry("qooxdoo-sdk", "6.0.0-alpha-20181212"));
        this.add(this.__createEntry("contrib/qx-osparc-theme", "0.3.0"));
        this.add(this.__createEntry("contrib/qx-iconfont-material", "0.1.0"));
        this.add(this.__createEntry("contrib/qx-iconfont-fontawesome5", "0.0.4"));
      }
      this.add(new qx.ui.core.Spacer(null, 10));
      [
        ["Ajv", "6.5.0", "https://github.com/epoberezkin/ajv"],
        ["svg.js", "2.6.4", "https://github.com/svgdotjs/svg.js"],
        ["socket.io", "2.1.2", "https://github.com/socketio/socket.io"],
        ["jsondiffpatch", "0.3.11", "https://github.com/benjamine/jsondiffpatch"]
      ].forEach(r => this.add(this.__createEntry(r[0], r[1], r[2])));
    },

    __createEntry: function(item, version, url) {
      let entryLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
        marginBottom: 4
      });

      let entryLabel = null;
      if (url) {
        entryLabel = new qxapp.component.widget.LabelLink(item, url);
      } else {
        entryLabel = new qx.ui.basic.Label(item);
      }
      const title14Font = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["title-14"]);
      entryLayout.set({
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
