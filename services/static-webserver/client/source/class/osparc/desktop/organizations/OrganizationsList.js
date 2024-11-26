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

qx.Class.define("osparc.desktop.organizations.OrganizationsList", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    const studiesLabel = osparc.product.Utils.getStudyAlias({plural: true});
    const msg = this.tr("\
    An organization is a group of users who can share ") + studiesLabel + this.tr(" and other resources.<br>\
    Here you can see the list of organizations you belong to, create new organizations, \
    or manage the membership by setting up the access rights of each member in the organization \
    if you are a manager or administrator.");
    const intro = new qx.ui.basic.Label().set({
      value: msg,
      alignX: "left",
      rich: true,
      font: "text-13"
    });
    this._add(intro);

    this._add(this.__getOrganizationsFilter());
    this._add(osparc.data.Roles.createRolesOrgInfo());
    this._add(this.__getOrganizationsList(), {
      flex: 1
    });

    if (osparc.data.Permissions.getInstance().canDo("user.organizations.create")) {
      this._add(this.__getCreateOrganizationSection());
    }

    this.reloadOrganizations();
  },

  events: {
    "organizationSelected": "qx.event.type.Data"
  },

  properties: {
    organizationsLoaded: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeOrganizationsLoaded"
    }
  },

  statics: {
    sortOrganizations: function(a, b) {
      const sorted = osparc.share.Collaborators.sortByAccessRights(a.getAccessRights(), b.getAccessRights());
      if (sorted !== 0) {
        return sorted;
      }
      return a.getLabel().localeCompare(b.getLabel());
    }
  },

  members: {
    __orgsUIList: null,
    __orgsModel: null,

    getOrgModel: function(orgId) {
      let org = null;
      this.__orgsModel.forEach(orgModel => {
        if (orgModel.getGroupId() === parseInt(orgId)) {
          org = orgModel;
        }
      });
      return org;
    },

    __getCreateOrganizationSection: function() {
      const createOrgBtn = new qx.ui.form.Button().set({
        appearance: "form-button",
        label: this.tr("New Organization"),
        alignX: "center",
        icon: "@FontAwesome5Solid/plus/14",
        allowGrowX: false
      });
      createOrgBtn.addListener("execute", function() {
        const title = this.tr("New Organization");
        const orgEditor = new osparc.editor.OrganizationEditor();
        const win = osparc.ui.window.Window.popUpInWindow(orgEditor, title, 400, 200);
        orgEditor.addListener("createOrg", () => {
          this.__createOrganization(win, orgEditor.getChildControl("create"), orgEditor);
        });
        orgEditor.addListener("cancel", () => win.close());
      }, this);
      return createOrgBtn;
    },

    __getOrganizationsFilter: function() {
      const filter = new osparc.filter.TextFilter("text", "organizationsList").set({
        allowStretchX: true,
        margin: [0, 10, 5, 10]
      });
      return filter;
    },

    __getOrganizationsList: function() {
      const orgsUIList = this.__orgsUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        height: 150,
        width: 150
      });
      osparc.utils.Utils.setIdToWidget(orgsUIList, "organizationsList");
      orgsUIList.addListener("changeSelection", e => this.__organizationSelected(e.getData()), this);

      const orgsModel = this.__orgsModel = new qx.data.Array();
      const orgsCtrl = new qx.data.controller.List(orgsModel, orgsUIList, "label");
      orgsCtrl.setDelegate({
        createItem: () => new osparc.ui.list.OrganizationListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("groupId", "key", null, item, id);
          ctrl.bindProperty("groupId", "model", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("label", "title", null, item, id);
          ctrl.bindProperty("description", "subtitle", null, item, id);
          ctrl.bindProperty("groupMembers", "groupMembers", null, item, id);
          ctrl.bindProperty("accessRights", "accessRights", null, item, id);
        },
        configureItem: item => {
          item.subscribeToFilterGroup("organizationsList");
          osparc.utils.Utils.setIdToWidget(item, "organizationListItem");
          const thumbnail = item.getChildControl("thumbnail");
          thumbnail.getContentElement()
            .setStyles({
              "border-radius": "16px"
            });

          item.addListener("openEditOrganization", e => {
            const orgKey = e.getData();
            this.__openEditOrganization(orgKey);
          });

          item.addListener("deleteOrganization", e => {
            const orgKey = e.getData();
            this.__deleteOrganization(orgKey);
          });
        }
      });

      const scrollContainer = new qx.ui.container.Scroll();
      scrollContainer.add(orgsUIList);

      return scrollContainer;
    },

    __organizationSelected: function(data) {
      if (data && data.length) {
        const org = data[0];
        this.fireDataEvent("organizationSelected", org.getModel());
      }
    },

    reloadOrganizations: function(orgId) {
      this.__orgsUIList.resetSelection();
      const orgsModel = this.__orgsModel;
      orgsModel.removeAll();

      const groupsStore = osparc.store.Groups.getInstance();
      const orgs = Object.values(groupsStore.getOrganizations());
      orgs.sort(this.self().sortOrganizations);
      orgs.forEach(org => orgsModel.append(org));
      this.setOrganizationsLoaded(true);
      if (orgId) {
        this.fireDataEvent("organizationSelected", orgId);
      }
    },

    __openEditOrganization: function(orgId) {
      const org = this.getOrgModel(orgId);
      if (org === null) {
        return;
      }

      const title = this.tr("Organization Details Editor");
      const orgEditor = new osparc.editor.OrganizationEditor(org);
      const win = osparc.ui.window.Window.popUpInWindow(orgEditor, title, 400, 200);
      orgEditor.addListener("updateOrg", () => {
        this.__updateOrganization(win, orgEditor.getChildControl("save"), orgEditor);
      });
      orgEditor.addListener("cancel", () => win.close());
    },

    __deleteOrganization: function(orgKey) {
      let org = null;
      this.__orgsModel.forEach(orgModel => {
        if (orgModel.getGroupId() === parseInt(orgKey)) {
          org = orgModel;
        }
      });
      if (org === null) {
        return;
      }

      const name = org.getLabel();
      const msg = this.tr("Are you sure you want to delete ") + name + "?";
      const win = new osparc.ui.window.Confirmation(msg).set({
        caption: this.tr("Delete Organization"),
        confirmText: this.tr("Delete"),
        confirmAction: "delete"
      });
      win.center();
      win.open();
      win.addListener("close", () => {
        if (win.getConfirmed()) {
          const groupsStore = osparc.store.Groups.getInstance(orgKey);
          groupsStore.deleteOrganization(orgKey)
            .then(() => {
              this.reloadOrganizations();
            })
            .catch(err => {
              osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong deleting ") + name, "ERROR");
              console.error(err);
            })
            .finally(() => {
              win.close();
            });
        }
      }, this);
    },

    __createOrganization: function(win, button, orgEditor) {
      const name = orgEditor.getLabel();
      const description = orgEditor.getDescription();
      const thumbnail = orgEditor.getThumbnail();
      const groupsStore = osparc.store.Groups.getInstance();
      groupsStore.postOrganization(name, description, thumbnail)
        .then(org => {
          osparc.FlashMessenger.getInstance().logAs(name + this.tr(" successfully created"));
          button.setFetching(false);
          // open it
          this.reloadOrganizations(org.getGroupId());
        })
        .catch(err => {
          const errorMessage = err["message"] || this.tr("Something went wrong creating ") + name;
          osparc.FlashMessenger.getInstance().logAs(errorMessage, "ERROR");
          button.setFetching(false);
          console.error(err);
        })
        .finally(() => {
          win.close();
        });
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
    }
  }
});
