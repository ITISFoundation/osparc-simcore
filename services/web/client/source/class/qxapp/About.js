/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Pedro Crespo (pcrespov)

************************************************************************ */

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
      let remoteUrl = qx.core.Environment.get("osparc.vcsOriginUrl");

      if (remoteUrl) {
        remoteUrl = remoteUrl.replace("git@github.com:", "https://github.com/");
        remoteUrl = remoteUrl.replace(".git", "");
      } else {
        remoteUrl = "https://github.com/ITISFoundation/osparc-simcore";
      }

      let name = "osparc-simcore";
      let commitId = qx.core.Environment.get("osparc.vcsRef");
      let url = remoteUrl;

      if (commitId) {
        url = remoteUrl + "/tree/" + String(commitId) + "/";
      }
      this.add(this.__createEntry(name, commitId, url));

      name = "osparc-simcore UI";
      commitId = qx.core.Environment.get("osparc.vcsRefClient");
      if (commitId) {
        url = remoteUrl + "/tree/" + String(commitId) + "/services/web/client/";
      }
      let status = qx.core.Environment.get("osparc.vcsStatusClient");
      if (status) {
        name = name + " [" + status + "]";
      }
      this.add(this.__createEntry(name, commitId, url));

      this.add(new qx.ui.core.Spacer(null, 10));

      this.add(this.__createEntry("qooxdoo-compiler", qx.core.Environment.get("qx.compilerVersion"), "https://github.com/qooxdoo/qooxdoo-compiler"));

      let libInfo = qx.core.Environment.get("qx.libraryInfoMap");
      if (libInfo) {
        for (let key in libInfo) {
          let lib = libInfo[key];
          this.add(this.__createEntry(lib.name, lib.version, lib.homepage));
        }
      }

      this.add(new qx.ui.core.Spacer(null, 10));

      Object.keys(qxapp.wrapper).forEach(className => {
        const wrapper = qxapp.wrapper[className];
        this.add(this.__createEntry(wrapper.NAME, wrapper.VERSION, wrapper.URL));
      });
    },

    __createEntry: function(item = "unknown-library", version = "unknown-version", url) {
      let entryLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
        marginBottom: 4
      });

      let entryLabel = null;
      if (url) {
        entryLabel = new qxapp.component.widget.LinkLabel(item, url);
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
