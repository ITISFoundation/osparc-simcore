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

    const rolesLayout = osparc.data.Roles.createRolesOrgInfo();
    const orgsFilter = this.__getOrganizationsFilter();
    orgsFilter.setPaddingRight(10);
    osparc.data.Roles.replaceSpacerWithWidget(rolesLayout, orgsFilter);
    this._add(rolesLayout);

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
      const collabTypeOrder = osparc.store.Groups.COLLAB_TYPE_ORDER;
      const typeDiff = collabTypeOrder.indexOf(a.getGroupType()) - collabTypeOrder.indexOf(b.getGroupType());
      if (typeDiff !== 0) {
        return typeDiff;
      }
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
        if ("getGroupId" in orgModel && orgModel.getGroupId() === parseInt(orgId)) {
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
        const win = new osparc.editor.OrganizationEditor();
        win.addListener("createOrg", () => {
          this.__createOrganization(win, win.getChildControl("create-button"));
        });
        win.addListener("cancel", () => win.close());
        win.open();
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
        appearance: "listing",
        height: 150,
        width: 150,
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
          // handle separator
          ctrl.bindProperty("isSeparator", "enabled", {
            converter: val => !val // disable clicks on separator
          }, item, id);
        },
        configureItem: item => {
          item.subscribeToFilterGroup("organizationsList");
          osparc.utils.Utils.setIdToWidget(item, "organizationListItem");
          item.getChildControl("thumbnail").setDecorator("circled");

          item.addListener("openEditOrganization", e => {
            const orgKey = e.getData();
            this.__openEditOrganization(orgKey);
          });

          item.addListener("deleteOrganization", e => {
            const orgKey = e.getData();
            this.__deleteOrganization(orgKey);
          });
          item.addListener("changeEnabled", e => {
            if (!e.getData()) {
              item.set({
                minHeight: 1,
                maxHeight: 1,
                backgroundColor: "transparent",
                decorator: "separator-strong",
              });
            }
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

      // insert a separator between product and non-product groups
      const productGroup = [
        osparc.store.Groups.COLLAB_TYPE.EVERYONE,
        osparc.store.Groups.COLLAB_TYPE.SUPPORT,
      ];
      const hasProductGroup = orgs.some(org => productGroup.includes(org.getGroupType()));
      const hasNonProductGroup = orgs.some(org => !productGroup.includes(org.getGroupType()));
      let separatorInserted = false;
      orgs.forEach(org => {
        const isProductGroup = productGroup.includes(org.getGroupType());
        // Only insert separator if both sides exist
        if (!isProductGroup && hasProductGroup && hasNonProductGroup && !separatorInserted) {
          const separator = {
            isSeparator: true
          };
          orgsModel.append(qx.data.marshal.Json.createModel(separator));
          separatorInserted = true;
        }
        orgsModel.append(org);
      });

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

      const win = new osparc.editor.OrganizationEditor(org);
      win.addListener("updateOrg", () => {
        this.__updateOrganization(win, win.getChildControl("save-button"));
      });
      win.addListener("cancel", () => win.close());
      win.open();
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
              const errorMsg = this.tr("Something went wrong while deleting ") + name;
              osparc.FlashMessenger.logError(err, errorMsg);
            })
            .finally(() => {
              win.close();
            });
        }
      }, this);
    },

    __createOrganization: function(orgEditor, button) {
      const name = orgEditor.getLabel();
      const description = orgEditor.getDescription();
      const thumbnail = orgEditor.getThumbnail();
      const groupsStore = osparc.store.Groups.getInstance();
      groupsStore.postOrganization(name, description, thumbnail)
        .then(org => {
          osparc.FlashMessenger.logAs(name + this.tr(" successfully created"));
          // open it
          this.reloadOrganizations(org.getGroupId());
        })
        .catch(err => {
          const msg = this.tr("Something went wrong while creating ") + name;
          osparc.FlashMessenger.logError(err, msg);
        })
        .finally(() => {
          button.setFetching(false);
          orgEditor.close();
        });
    },

    __updateOrganization: function(orgEditor, button) {
      const groupId = orgEditor.getGid();
      const name = orgEditor.getLabel();
      const description = orgEditor.getDescription();
      const thumbnail = orgEditor.getThumbnail();
      osparc.store.Groups.getInstance().patchOrganization(groupId, name, description, thumbnail)
        .then(() => {
          osparc.FlashMessenger.logAs(name + this.tr(" successfully edited"));
        })
        .catch(err => {
          const msg = this.tr("Something went wrong while editing ") + name;
          osparc.FlashMessenger.logError(err, msg);
        })
        .finally(() => {
          button.setFetching(false);
          orgEditor.close();
        });
    }
  }
});
