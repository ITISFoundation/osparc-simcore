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
    An organization is a group of users who can share ") + studiesLabel + this.tr(".<br>\
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
      const sorted = osparc.share.Collaborators.sortByAccessRights(a["accessRights"], b["accessRights"]);
      if (sorted !== 0) {
        return sorted;
      }
      if (("label" in a) && ("label" in b)) {
        return a["label"].localeCompare(b["label"]);
      }
      return 0;
    }
  },

  members: {
    __orgsUIList: null,
    __orgsModel: null,

    getOrgModel: function(orgId) {
      let org = null;
      this.__orgsModel.forEach(orgModel => {
        if (orgModel.getGid() === parseInt(orgId)) {
          org = orgModel;
        }
      });
      return org;
    },

    __getCreateOrganizationSection: function() {
      const createOrgBtn = new qx.ui.form.Button().set({
        appearance: "strong-button",
        label: this.tr("New Organization"),
        alignX: "center",
        icon: "@FontAwesome5Solid/plus/14",
        allowGrowX: false
      });
      createOrgBtn.addListener("execute", function() {
        const newOrg = true;
        const orgEditor = new osparc.editor.OrganizationEditor(newOrg);
        const title = this.tr("Organization Details Editor");
        const win = osparc.ui.window.Window.popUpInWindow(orgEditor, title, 400, 250);
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
        width: 150,
        backgroundColor: "background-main-2"
      });
      orgsUIList.addListener("changeSelection", e => this.__organizationSelected(e.getData()), this);

      const orgsModel = this.__orgsModel = new qx.data.Array();
      const orgsCtrl = new qx.data.controller.List(orgsModel, orgsUIList, "label");
      orgsCtrl.setDelegate({
        createItem: () => new osparc.ui.list.OrganizationListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("gid", "key", null, item, id);
          ctrl.bindProperty("gid", "model", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("label", "title", null, item, id);
          ctrl.bindProperty("description", "subtitle", null, item, id);
          ctrl.bindProperty("nMembers", "contact", null, item, id);
          ctrl.bindProperty("accessRights", "accessRights", null, item, id);
        },
        configureItem: item => {
          item.subscribeToFilterGroup("organizationsList");
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
      if (data && data.length>0) {
        const org = data[0];
        this.fireDataEvent("organizationSelected", org.getModel());
      }
    },

    reloadOrganizations: function() {
      this.__orgsUIList.resetSelection();
      const orgsModel = this.__orgsModel;
      orgsModel.removeAll();

      osparc.data.Resources.get("organizations")
        .then(async respOrgs => {
          const orgs = respOrgs["organizations"];
          const promises = await orgs.map(async org => {
            const params = {
              url: {
                gid: org["gid"]
              }
            };
            const respOrgMembers = await osparc.data.Resources.get("organizationMembers", params);
            org["nMembers"] = Object.keys(respOrgMembers).length + this.tr(" members");
            return org;
          });
          const orgsList = await Promise.all(promises);
          orgsList.sort(this.self().sortOrganizations);
          orgsList.forEach(org => orgsModel.append(qx.data.marshal.Json.createModel(org)));
          this.setOrganizationsLoaded(true);
        });
    },

    __openEditOrganization: function(orgId) {
      const org = this.getOrgModel(orgId);
      if (org === null) {
        return;
      }

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

    __deleteOrganization: function(orgKey) {
      let org = null;
      this.__orgsModel.forEach(orgModel => {
        if (orgModel.getGid() === parseInt(orgKey)) {
          org = orgModel;
        }
      });
      if (org === null) {
        return;
      }

      const name = org.getLabel();
      const msg = this.tr("Are you sure you want to delete ") + name + "?";
      const win = new osparc.ui.window.Confirmation(msg).set({
        confirmText: this.tr("Delete"),
        confirmAction: "delete"
      });
      win.center();
      win.open();
      win.addListener("close", () => {
        if (win.getConfirmed()) {
          const params = {
            url: {
              "gid": orgKey
            }
          };
          osparc.data.Resources.fetch("organizations", "delete", params)
            .then(() => {
              osparc.store.Store.getInstance().reset("organizations");
              // reload "profile", "organizations" are part of the information in this endpoint
              osparc.data.Resources.getOne("profile", {}, null, false)
                .then(() => {
                  this.reloadOrganizations();
                });
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
      osparc.data.Resources.fetch("organizations", "post", params)
        .then(() => {
          osparc.FlashMessenger.getInstance().logAs(name + this.tr(" successfully created"));
          button.setFetching(false);
          osparc.store.Store.getInstance().reset("organizations");
          // reload "profile", "organizations" are part of the information in this endpoint
          osparc.data.Resources.getOne("profile", {}, null, false)
            .then(() => {
              this.reloadOrganizations();
            });
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong creating ") + name, "ERROR");
          button.setFetching(false);
          console.error(err);
        })
        .finally(() => {
          win.close();
        });
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
          this.reloadOrganizations();
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong editing ") + name, "ERROR");
          button.setFetching(false);
          console.error(err);
        });
    }
  }
});
