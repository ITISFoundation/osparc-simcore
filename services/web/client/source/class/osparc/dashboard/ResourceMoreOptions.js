/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.ResourceMoreOptions", {
  extend: qx.ui.tabview.TabView,

  construct: function(resourceData) {
    this.base(arguments);

    this.__resourceData = resourceData;

    this.set({
      barPosition: "left",
      contentPadding: 0
    });

    this.__addPages();
  },

  members: {
    __resourceData: null,

    __addPages: function() {
      const moreInfoPage = this.__getInfoPage();
      if (moreInfoPage) {
        this.add(moreInfoPage);
      }
    },

    __createPage: function(title, widget, icon) {
      const tabPage = new qx.ui.tabview.Page().set({
        backgroundColor: "material-button-background",
        paddingLeft: 20,
        layout: new qx.ui.layout.VBox(10),
        icon: icon + "/24"
      });

      tabPage.getButton().set({
        minWidth: 35,
        toolTipText: title,
        alignY: "middle"
      });
      tabPage.getButton().getChildControl("icon").set({
        alignX: "right"
      });

      // Page title
      tabPage.add(new qx.ui.basic.Label(title).set({
        font: "title-16"
      }));

      // Page content
      tabPage.add(widget, {
        flex: 1
      });

      return tabPage;
    },

    __getInfoPage: function() {
      const title = this.tr("Information");
      const icon = "@FontAwesome5Solid/info";
      const resourceData = this.__resourceData;
      const studyDetails = new osparc.studycard.Large(resourceData);
      const page = this.__createPage(title, studyDetails, icon);
      return page;
    }
  }
});
