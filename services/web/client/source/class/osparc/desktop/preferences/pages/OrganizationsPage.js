/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

/**
 *  Organization and members in preferences dialog
 *
 */

qx.Class.define("osparc.desktop.preferences.pages.OrganizationsPage", {
  extend: osparc.desktop.preferences.pages.BasePage,

  construct: function() {
    const iconSrc = "@FontAwesome5Solid/sitemap/24";
    const title = this.tr("Organizations");
    this.base(arguments, title, iconSrc);


    this.add(this.__createOrganizations());
    this.add(this.__createMembers(), {
      flex: 1
    });
  },

  members: {
    __membersModel: null,

    __createOrganizations: function() {
      const box = this._createSectionBox(this.tr("Organizations"));

      const orgsUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        height: 150,
        width: 150
      });
      orgsUIList.addListener("changeSelection", e => {
        if (e.getData() && e.getData().length>0) {
          const selectedOrg = e.getData()[0].getModel();
          this.__organizationSelected(selectedOrg);
        }
      }, this);
      box.add(orgsUIList);

      const orgsModel = new qx.data.Array();
      const orgsCtrl = new qx.data.controller.List(orgsModel, orgsUIList, "label");
      orgsCtrl.setDelegate({
        createItem: () => new osparc.dashboard.ServiceBrowserListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("gid", "model", null, item, id);
          ctrl.bindProperty("gid", "key", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("label", "title", null, item, id);
          ctrl.bindProperty("description", "subtitle", null, item, id);
          ctrl.bindProperty("nMembers", "contact", null, item, id);
        },
        configureItem: item => {
          item.getChildControl("thumbnail").getContentElement()
            .setStyles({
              "border-radius": "16px"
            });
        }
      });

      const store = osparc.store.Store.getInstance();
      store.getGroupsOrganizations()
        .then(orgs => {
          orgsModel.removeAll();
          orgs.forEach(org => {
            // fake
            const rNumber = Math.floor((Math.random() * 100));
            org["nMembers"] = rNumber + " members";
            org["thumbnail"] = "https://raw.githubusercontent.com/Radhikadua123/superhero/master/CAX_Superhero_Test/superhero_test_" + rNumber + ".jpg";
            orgsModel.append(qx.data.marshal.Json.createModel(org));
          });
        });

      return box;
    },

    __createMembers: function() {
      const box = this._createSectionBox(this.tr("Members"));

      const memebersUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        width: 150
      });
      box.add(memebersUIList, {
        flex: 1
      });

      const membersModel = this.__membersModel = new qx.data.Array();
      const membersCtrl = new qx.data.controller.List(membersModel, memebersUIList, "name");
      membersCtrl.setDelegate({
        createItem: () => new osparc.dashboard.ServiceBrowserListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("uid", "model", null, item, id);
          ctrl.bindProperty("uid", "key", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id);
          ctrl.bindProperty("role", "subtitle", null, item, id);
          ctrl.bindProperty("email", "contact", null, item, id);
        },
        configureItem: item => {
          item.getChildControl("thumbnail").getContentElement()
            .setStyles({
              "border-radius": "16px"
            });
        }
      });

      return box;
    },

    __organizationSelected: function(orgId) {
      const membersModel = this.__membersModel;
      membersModel.removeAll();
      const store = osparc.store.Store.getInstance();
      store.getOrganizationMembers(orgId)
        .then(members => {
          members.forEach(member => {
            member["thumbnail"] = osparc.utils.Avatar.getUrl(member["email"], 32);
            membersModel.append(qx.data.marshal.Json.createModel(member));
          });
        });
    }
  }
});
