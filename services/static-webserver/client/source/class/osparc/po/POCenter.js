/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.po.POCenter", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.set({
      padding: 20,
      paddingLeft: 10
    });

    const tabViews = this.__tabsView = new qx.ui.tabview.TabView().set({
      barPosition: "left",
      contentPadding: 0
    });
    tabViews.getChildControl("bar").add(this.__getMiniProfileView());

    const overviewPage = this.__overviewPage = this.__getOverviewPage();
    tabViews.add(overviewPage);

    this._add(tabViews);
  },

  members: {
    __walletsEnabled: null,
    __tabsView: null,
    __overviewPage: null,

    __getMiniProfileView: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(8)).set({
        alignX: "center",
        minWidth: 120,
        maxWidth: 150
      });

      const authData = osparc.auth.Data.getInstance();
      const email = authData.getEmail();
      const img = new qx.ui.basic.Image().set({
        source: osparc.utils.Avatar.getUrl(email, 100),
        maxWidth: 80,
        maxHeight: 80,
        scale: true,
        decorator: new qx.ui.decoration.Decorator().set({
          radius: 30
        }),
        alignX: "center"
      });
      layout.add(img);

      const name = new qx.ui.basic.Label().set({
        font: "text-14",
        alignX: "center"
      });
      layout.add(name);
      authData.bind("firstName", name, "value", {
        converter: firstName => firstName + " " + authData.getLastName()
      });
      authData.bind("lastName", name, "value", {
        converter: lastName => authData.getFirstName() + " " + lastName
      });

      const emailLabel = new qx.ui.basic.Label(email).set({
        font: "text-13",
        alignX: "center"
      });
      layout.add(emailLabel);

      layout.add(new qx.ui.core.Spacer(15, 15), {
        flex: 1
      });

      return layout;
    },

    __getOverviewPage: function() {
      const title = this.tr("Overview");
      const iconSrc = "@FontAwesome5Solid/table/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      page.showLabelOnTab();
      const overview = new osparc.po.Overview();
      overview.set({
        margin: 10
      });
      page.add(overview);
      return page;
    }
  }
});
