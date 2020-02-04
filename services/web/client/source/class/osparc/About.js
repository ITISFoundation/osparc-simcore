/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Pedro Crespo (pcrespov)

************************************************************************ */

qx.Class.define("osparc.About", {
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
      centerOnAppear: true,
      appearance: "service-window"
    });
    const closeBtn = this.getChildControl("close-button");
    osparc.utils.Utils.setIdToWidget(closeBtn, "aboutWindowCloseBtn");
    this.__populateEntries();
  },

  members: {
    __populateEntries: function() {
      const platformVersion = osparc.utils.LibVersions.getPlatformVersion();
      this.__createEntries([platformVersion]);

      const uiVersion = osparc.utils.LibVersions.getUIVersion();
      this.__createEntries([uiVersion]);

      this.add(new qx.ui.core.Spacer(null, 10));

      const qxCompiler = osparc.utils.LibVersions.getQxCompiler();
      this.__createEntries([qxCompiler]);

      const libsInfo = osparc.utils.LibVersions.getQxLibraryInfoMap();
      this.__createEntries(libsInfo);

      this.add(new qx.ui.core.Spacer(null, 10));

      const libs = osparc.utils.LibVersions.get3rdPartyLibs();
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
        entryLabel = new osparc.ui.basic.LinkLabel(item, url);
      } else {
        entryLabel = new qx.ui.basic.Label(item);
      }
      entryLayout.set({
        font: osparc.utils.Utils.getFont(14, true)
      });
      entryLayout.add(entryLabel);

      let entryVersion = new qx.ui.basic.Label().set({
        value: vers,
        font: osparc.utils.Utils.getFont(14)
      });
      entryLayout.add(entryVersion);

      return entryLayout;
    }
  }
});
