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
      const platformVersion = qxapp.utils.LibVersions.getPlatformVersion();
      this.__createEntries([platformVersion]);

      const uiVersion = qxapp.utils.LibVersions.getUIVersion();
      this.__createEntries([uiVersion]);

      this.add(new qx.ui.core.Spacer(null, 10));

      const qxCompiler = qxapp.utils.LibVersions.getQxCompiler();
      this.__createEntries([qxCompiler]);

      const libsInfo = qxapp.utils.LibVersions.getQxLibraryInfoMap();
      this.__createEntries(libsInfo);

      this.add(new qx.ui.core.Spacer(null, 10));

      const libs = qxapp.utils.LibVersions.get3rdPartyLibs();
      this.__createEntries(libs);
    },

    __createEntries: function(libs) {
      for (let i=0; i<libs.length; i++) {
        const lib = libs[i];
        this.add(this.__createEntry(lib.name, lib.version, lib.url));
      }
    },

    __createEntry: function(item = "unknown-library", vers = "unknown-version", url) {
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
      let entryVersion = new qx.ui.basic.Label(vers).set({
        font: text14Font
      });
      entryLayout.add(entryVersion);

      return entryLayout;
    }
  }
});
