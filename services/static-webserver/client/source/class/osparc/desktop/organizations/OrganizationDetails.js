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

qx.Class.define("osparc.desktop.organizations.OrganizationDetails", {
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
    __orgModel: null,
    __titleLayout: null,
    __organizationListItem: null,
    __membersList: null,
    __templatesList: null,
    __servicesList: null,

    setCurrentOrg: function(organization) {
      if (organization === null) {
        return;
      }
      this.__orgModel = organization;

      const organizationListItem = this.__addOrganizationListItem();
      organization.bind("groupId", organizationListItem, "key");
      organization.bind("groupId", organizationListItem, "model");
      organization.bind("thumbnail", organizationListItem, "thumbnail");
      organization.bind("label", organizationListItem, "title");
      organization.bind("description", organizationListItem, "subtitle");
      organization.bind("groupMembers", organizationListItem, "groupMembers");
      organization.bind("accessRights", organizationListItem, "accessRights");
      organizationListItem.updateNMembers();
      [
        "memberAdded",
        "memberRemoved",
      ].forEach(ev => organization.addListener(ev, () => organizationListItem.updateNMembers()));

      // set orgModel to the tab views
      this.__membersList.setCurrentOrg(organization);
      this.__templatesList.setCurrentOrg(organization);
      this.__servicesList.setCurrentOrg(organization);
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
      organizationListItem.setShowDeleteButton(false);
      organizationListItem.addListener("openEditOrganization", () => this.__openEditOrganization());
      this.__titleLayout.add(organizationListItem, {
        flex: 1
      });
      return organizationListItem;
    },

    __openEditOrganization: function() {
      const org = this.__orgModel;
      const title = this.tr("Organization Details Editor");
      const orgEditor = new osparc.editor.OrganizationEditor(org);
      const win = osparc.ui.window.Window.popUpInWindow(orgEditor, title, 400, 200);
      orgEditor.addListener("updateOrg", () => {
        this.__updateOrganization(win, orgEditor.getChildControl("save"), orgEditor);
      });
      orgEditor.addListener("cancel", () => win.close());
    },

    __updateOrganization: function(win, button, orgEditor) {
      const groupId = orgEditor.getGid();
      const name = orgEditor.getLabel();
      const description = orgEditor.getDescription();
      const thumbnail = orgEditor.getThumbnail();
      osparc.store.Groups.getInstance().patchOrganization(groupId, name, description, thumbnail)
        .then(() => {
          osparc.FlashMessenger.getInstance().logAs(name + this.tr(" successfully edited"));
          button.setFetching(false);
          win.close();
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong editing ") + name, "ERROR");
          button.setFetching(false);
          console.error(err);
        });
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

      const membersListPage = this.__createTabPage(this.tr("Members"), "@FontAwesome5Solid/users/14");
      const membersList = this.__membersList = new osparc.desktop.organizations.MembersList();
      membersListPage.add(membersList, {
        flex: 1
      });
      tabView.add(membersListPage);

      const templatesText = osparc.product.Utils.getTemplateAlias({
        plural: true,
        firstUpperCase: true
      });
      const templatesListPage = this.__createTabPage(templatesText, "@FontAwesome5Solid/copy/14");
      const templatesList = this.__templatesList = new osparc.desktop.organizations.TemplatesList();
      templatesListPage.add(templatesList, {
        flex: 1
      });
      tabView.add(templatesListPage);

      const servicesListPage = this.__createTabPage(this.tr("Services"), "@FontAwesome5Solid/cogs/14");
      const servicesList = this.__servicesList = new osparc.desktop.organizations.ServicesList();
      servicesListPage.add(servicesList, {
        flex: 1
      });
      tabView.add(servicesListPage);

      return tabView;
    }
  }
});
