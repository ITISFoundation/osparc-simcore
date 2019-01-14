/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.desktop.Dashboard", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base(arguments, new qx.ui.layout.HBox());

    qxapp.wrappers.JsonDiffPatch.getInstance().init();

    let leftSpacer = new qx.ui.core.Spacer(120);
    let mainView = this.__createMainViewLayout();
    let rightSpacer = new qx.ui.core.Spacer(120);

    this.add(leftSpacer);
    this.add(mainView, {
      flex: 1
    });
    this.add(rightSpacer);
  },

  members: {
    __prjBrowser: null,

    getPrjBrowser: function() {
      return this.__prjBrowser;
    },

    __createMainViewLayout: function() {
      let tabView = new qx.ui.tabview.TabView();

      [
        [this.tr("Studies"), this.__createStudiesView],
        [this.tr("Services"), this.__createServicesLayout],
        [this.tr("File Manager"), this.__createFileManagerLayout]
      ].forEach(tuple => {
        let tabPage = new qx.ui.tabview.Page(tuple[0]);
        tabPage.setLayout(new qx.ui.layout.VBox());

        let viewLayout = tuple[1].call(this);
        let scrollerMainView = new qx.ui.container.Scroll();
        scrollerMainView.add(viewLayout);
        tabPage.add(scrollerMainView, {
          flex: 1
        });

        tabView.add(tabPage);
      }, this);

      return tabView;
    },

    __createStudiesView: function() {
      let studiesView = this.__prjBrowser = new qxapp.desktop.PrjBrowser();
      return studiesView;
    },

    __createServicesLayout: function() {
      let servicesView = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      const navBarLabelFont = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]);
      let servicesLabel = new qx.ui.basic.Label(this.tr("Services")).set({
        font: navBarLabelFont,
        minWidth: 150
      });
      servicesView.add(servicesLabel);

      return servicesView;
    },

    __createFileManagerLayout: function() {
      let fileManagerView = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      const navBarLabelFont = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]);
      let fileManagerLabel = new qx.ui.basic.Label(this.tr("File Manager")).set({
        font: navBarLabelFont,
        minWidth: 150
      });
      fileManagerView.add(fileManagerLabel);

      return fileManagerView;
    }
  }
});
