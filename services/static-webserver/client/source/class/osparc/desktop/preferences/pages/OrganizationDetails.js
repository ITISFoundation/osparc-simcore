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

qx.Class.define("osparc.desktop.preferences.pages.OrganizationDetails", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this._add(this.__getTitleLayout());
    this._add(this.__getTabs(), {
      flex: 1
    });
  },

  events: {
    "backToOrganizations": "qx.event.type.Event"
  },

  members: {
    __currentOrg: null,
    __titleLayout: null,
    __organizationListItem: null,
    __membersList: null,

    setCurrentOrg: function(orgModel) {
      if (orgModel === null) {
        return;
      }
      const organizationListItem = this.__addOrganizationListItem();
      orgModel.bind("gid", organizationListItem, "key");
      orgModel.bind("gid", organizationListItem, "model");
      orgModel.bind("thumbnail", organizationListItem, "thumbnail");
      orgModel.bind("label", organizationListItem, "title");
      orgModel.bind("description", organizationListItem, "subtitle");
      orgModel.bind("nMembers", organizationListItem, "contact");
      orgModel.bind("accessRights", organizationListItem, "accessRights");
      this.__currentOrg = organizationListItem;

      // set orgModel to the tab views
      this.__membersList.setCurrentOrg(orgModel);
    },

    __getTitleLayout: function() {
      const titleLayout = this.__titleLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));

      const prevBtn = new qx.ui.form.Button().set({
        toolTipText: this.tr("Back to Organizations list"),
        icon: "@FontAwesome5Solid/arrow-left/20",
        backgroundColor: "transparent"
      });
      prevBtn.addListener("execute", () => this.fireEvent("backToOrganizations"));
      titleLayout.add(prevBtn);

      this.__addOrganizationListItem();

      return titleLayout;
    },

    __addOrganizationListItem: function() {
      if (this.__organizationListItem) {
        this.__titleLayout.remove(this.__organizationListItem);
      }
      const organizationListItem = this.__organizationListItem = new osparc.ui.list.OrganizationListItem();
      organizationListItem.getChildControl("options").exclude();
      this.__titleLayout.add(organizationListItem);
      return organizationListItem;
    },

    __createTabPage: function(label, icon) {
      const tabPage = new qx.ui.tabview.Page().set({
        layout: new qx.ui.layout.VBox()
      });
      if (label) {
        tabPage.setLabel(label);
      }
      if (icon) {
        tabPage.setIcon(icon);
      }
      tabPage.getChildControl("button").set({
        font: "text-13"
      });
      return tabPage;
    },

    __getTabs: function() {
      const tabView = new qx.ui.tabview.TabView().set({
        contentPadding: 10
      });
      tabView.getChildControl("pane").set({
        backgroundColor: "background-main-2"
      });

      const membersListPage = this.__createTabPage(this.tr("Members"), "@FontAwesome5Solid/users/14");
      const membersList = this.__membersList = new osparc.desktop.preferences.pages.OrganizationMembersList();
      membersListPage.add(membersList, {
        flex: 1
      });
      tabView.add(membersListPage);

      return tabView;
    }
  }
});
