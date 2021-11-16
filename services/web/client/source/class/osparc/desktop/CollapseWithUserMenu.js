/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.CollapseWithUserMenu", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox());

    this.__buildLayout();
  },

  events: {
    "backToDashboardPressed": "qx.event.type.Event",
    "collapseNavBar": "qx.event.type.Event",
    "expandNavBar": "qx.event.type.Event"
  },

  members: {
    __buildLayout: function() {
      const separator = new qx.ui.toolbar.Separator().set({
        padding: 0,
        margin: 0,
        backgroundColor: "contrasted-background++"
      });
      separator.exclude();
      this._add(separator);

      const closeStudyButton = new osparc.ui.form.FetchButton(this.tr("Dashboard"), "@FontAwesome5Solid/arrow-left/16").set({
        font: "text-14",
        backgroundColor: "contrasted-background+"
      });
      osparc.utils.Utils.setIdToWidget(closeStudyButton, "dashboardBtn");
      closeStudyButton.addListener("execute", () => this.fireEvent("backToDashboardPressed"));
      closeStudyButton.exclude();
      this._add(closeStudyButton);
      const userMenuButton = new osparc.navigation.UserMenuButton().set({
        backgroundColor: "contrasted-background+"
      });
      osparc.io.WatchDog.getInstance().bind("online", userMenuButton, "backgroundColor", {
        converter: on => on ? "contrasted-background+" : "red"
      });
      userMenuButton.getChildControl("label").exclude();
      userMenuButton.getMenu().set({
        backgroundColor: "contrasted-background+"
      });
      userMenuButton.populateExtendedMenu();
      userMenuButton.exclude();
      this._add(userMenuButton);


      const collapseExpandNavBarStack = new qx.ui.container.Stack();

      const collapseNavBarBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/chevron-up/14").set({
        backgroundColor: "contrasted-background+"
      });
      collapseExpandNavBarStack.add(collapseNavBarBtn);
      collapseNavBarBtn.addListener("execute", () => {
        separator.show();
        closeStudyButton.show();
        userMenuButton.show();
        collapseExpandNavBarStack.setSelection([collapseExpandNavBarStack.getSelectables()[1]]);
        this.fireEvent("collapseNavBar");
      });

      const expandNavBarBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/chevron-down/14").set({
        backgroundColor: "contrasted-background+"
      });
      collapseExpandNavBarStack.add(expandNavBarBtn);
      expandNavBarBtn.addListener("execute", () => {
        separator.exclude();
        closeStudyButton.exclude();
        userMenuButton.exclude();
        collapseExpandNavBarStack.setSelection([collapseExpandNavBarStack.getSelectables()[0]]);
        this.fireEvent("expandNavBar");
      });

      this._add(collapseExpandNavBarStack);
    }
  }
});
