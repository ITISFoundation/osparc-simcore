/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.admin.PricingPlanDetails", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.getChildControl("back-to-pp-button");
    this.getChildControl("pricing-plan-details");
    this.getChildControl("tab-view");
  },

  events: {
    "backToPricingPlans": "qx.event.type.Event"
  },

  members: {
    __pricingPlanModel: null,
    __pricingPlanListItem: null,
    __pricingUnitsList: null,
    __servicesList: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "title-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
          this._addAt(control, 0);
          break;
        case "back-to-pp-button":
          control = new qx.ui.form.Button().set({
            toolTipText: this.tr("Back to Organizations list"),
            icon: "@FontAwesome5Solid/arrow-left/20",
            backgroundColor: "transparent"
          });
          control.addListener("execute", () => this.fireEvent("backToOrganizations"));
          this.getChildControl("title-layout").add(control);
          break;
        case "pricing-plan-details":
          control = new osparc.admin.PricingPlanListItem();
          this.getChildControl("title-layout").add(control);
          break;
        case "tab-view":
          control = new qx.ui.tabview.TabView().set({
            contentPadding: 10
          });
          this._addAt(control, 1, {
            flex: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    setCurrentPricingPlan: function(pricingPlanModel) {
      if (pricingPlanModel === null) {
        return;
      }
      this.__pricingPlanModel = pricingPlanModel;

      const pricingPlanListItem = this.getChildControl("pricing-plan-details");
      pricingPlanModel.bind("gid", pricingPlanListItem, "key");
      pricingPlanModel.bind("gid", pricingPlanListItem, "model");
      pricingPlanModel.bind("thumbnail", pricingPlanListItem, "thumbnail");
      pricingPlanModel.bind("label", pricingPlanListItem, "title");
      pricingPlanModel.bind("description", pricingPlanListItem, "subtitle");
      pricingPlanModel.bind("nMembers", pricingPlanListItem, "contact");
      pricingPlanModel.bind("accessRights", pricingPlanListItem, "accessRights");

      // set orgModel to the tab views
      this.__pricingUnitsList.setCurrentOrg(pricingPlanModel);
      this.__templatesList.setCurrentOrg(pricingPlanModel);
      this.__servicesList.setCurrentOrg(pricingPlanModel);
    },

    __addOrganizationListItem: function() {
      if (this.__pricingPlanListItem) {
        this.__titleLayout.remove(this.__pricingPlanListItem);
      }
      const organizationListItem = this.__pricingPlanListItem = new osparc.ui.list.OrganizationListItem();
      organizationListItem.getChildControl("options").exclude();
      organizationListItem.setShowDeleteButton(false);
      organizationListItem.addListener("openEditOrganization", () => this.__openEditOrganization());
      this.__titleLayout.add(organizationListItem, {
        flex: 1
      });
      return organizationListItem;
    },

    __openEditOrganization: function() {
      const org = this.__pricingPlanModel;

      const newOrg = false;
      const orgEditor = new osparc.editor.OrganizationEditor(newOrg);
      org.bind("gid", orgEditor, "gid");
      org.bind("label", orgEditor, "label");
      org.bind("description", orgEditor, "description");
      org.bind("thumbnail", orgEditor, "thumbnail", {
        converter: val => val ? val : ""
      });
      const title = this.tr("Organization Details Editor");
      const win = osparc.ui.window.Window.popUpInWindow(orgEditor, title, 400, 250);
      orgEditor.addListener("updateOrg", () => {
        this.__updateOrganization(win, orgEditor.getChildControl("save"), orgEditor);
      });
      orgEditor.addListener("cancel", () => win.close());
    },

    __updateOrganization: function(win, button, orgEditor) {
      const orgKey = orgEditor.getGid();
      const name = orgEditor.getLabel();
      const description = orgEditor.getDescription();
      const thumbnail = orgEditor.getThumbnail();
      const params = {
        url: {
          "gid": orgKey
        },
        data: {
          "label": name,
          "description": description,
          "thumbnail": thumbnail || null
        }
      };
      osparc.data.Resources.fetch("organizations", "patch", params)
        .then(() => {
          osparc.FlashMessenger.getInstance().logAs(name + this.tr(" successfully edited"));
          button.setFetching(false);
          win.close();
          osparc.store.Store.getInstance().reset("organizations");
          this.__pricingPlanModel.set({
            label: name,
            description: description,
            thumbnail: thumbnail || null
          });
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
      tabView.getChildControl("pane");

      const membersListPage = this.__createTabPage(this.tr("Members"), "@FontAwesome5Solid/users/14");
      const membersList = this.__pricingUnitsList = new osparc.desktop.organizations.MembersList();
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
