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
      var remoteUrl = qx.core.Environment.get("osparc.vcsOriginUrl");

      if (remoteUrl) {
        remoteUrl = remoteUrl.replace("git@github.com:", "https://github.com/")
        remoteUrl = remoteUrl.replace(".git", "");
      } else {
        remoteUrl = "https://github.com/ITISFoundation/osparc-simcore";
      }

      var name = "oSPARC";
      var commitId = qx.core.Environment.get("osparc.vcsRef");
      var url = remoteUrl;

      if (commitId) {
        url = remoteUrl + "/tree/" + String(commitId) + "/";
      }
      this.add(this.__createEntry(name, commitId, url));

      name = "oSPARC UI";
      commitId = qx.core.Environment.get("osparc.vcsRefClient");
      if (commitId) {
        url = remoteUrl + "/tree/" + String(commitId) + "/services/web/client/";
      }
      var status = qx.core.Environment.get("osparc.vcsStatusClient");
      if (status) {
        name = name + " [" + status + "]";
      }
      this.add(this.__createEntry(name, commitId, url));

      // this.add(new qx.ui.core.Spacer(null, 10));

      this.add(this.__createEntry("qooxdoo-compiler", qx.core.Environment.get("qx.compilerVersion"), "https://github.com/qooxdoo/qooxdoo-compiler"));

      let libInfo = qx.core.Environment.get("qx.libraryInfoMap");
      if (libInfo) {
        this.assert(libInfo, "remove harcoded part");
        for (let key in libInfo) {
          let lib = libInfo[key];
          this.add(this.__createEntry(lib.name, lib.version, lib.homepage));
        }
      } else {
        // TODO: as soon as we upgrade the qooxdoo compiler (v0.2.31) all this info will be in qx.libraryInfoMap
        this.add(this.__createEntry("qooxdoo-sdk", "6.0.0-alpha-20181212"));
        this.add(this.__createEntry("contrib/qx-osparc-theme", "0.3.0"));
        this.add(this.__createEntry("contrib/qx-iconfont-material", "0.1.0"));
        this.add(this.__createEntry("contrib/qx-iconfont-fontawesome5", "0.0.4"));
      }

      this.add(new qx.ui.core.Spacer(null, 10));

      Object.keys(qxapp.wrappers).forEach(className => {
        const wrapper = qxapp.wrappers[className];
        this.add(this.__createEntry(wrapper.NAME, wrapper.VERSION, wrapper.URL));
      });
    },

    __createEntry: function(item = "unknown-library", version = "unknown-version", url) {
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
