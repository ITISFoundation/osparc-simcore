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
    this.add(this.__createMembersSection(), {
      flex: 1
    });
  },

  members: {
    __memberInvitation: null,
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
            if (org["gid"] === 100) {
              org["thumbnail"] = "https://user-images.githubusercontent.com/33152403/82996091-baa65e00-a004-11ea-9695-206d005fdf54.png";
            } else {
              org["thumbnail"] = "https://raw.githubusercontent.com/Radhikadua123/superhero/master/CAX_Superhero_Test/superhero_test_" + rNumber + ".jpg";
            }
            orgsModel.append(qx.data.marshal.Json.createModel(org));
          });
        });

      return box;
    },

    __createMembersSection: function() {
      const box = this._createSectionBox(this.tr("Members"));
      box.add(this.__createMemberInvitation());
      box.add(this.__createMembersList(), {
        flex: 1
      });
      return box;
    },

    __createMemberInvitation: function() {
      const hBox = this.__memberInvitation = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      }));
      hBox.exclude();

      const emailLabel = new qx.ui.basic.Label(this.tr("Email")).set({
        allowGrowX: true
      });
      hBox.add(emailLabel);

      const userEmail = new qx.ui.form.TextField();
      userEmail.setRequired(true);
      hBox.add(userEmail, {
        flex: 1
      });

      const validator = new qx.ui.form.validation.Manager();
      validator.add(userEmail, qx.util.Validate.email());

      const inviteBtn = new qx.ui.form.Button(this.tr("Invite"));
      inviteBtn.addListener("execute", function() {
        if (validator.validate()) {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Invitation sent to ") + userEmail.getValue());
        }
      }, this);
      hBox.add(inviteBtn);

      return hBox;
    },

    __createMembersList: function() {
      const memebersUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        width: 150
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

      return memebersUIList;
    },

    __organizationSelected: function(orgId) {
      this.__memberInvitation.exclude();
      const membersModel = this.__membersModel;
      membersModel.removeAll();

      const params = {
        url: {
          gid: orgId
        }
      };
      osparc.data.Resources.get("organizationMembers", params)
        .then(members => {
          members.forEach(member => {
            if (member["role"] === "Manager" && member["email"] === osparc.auth.Data.getInstance().getEmail()) {
              this.__memberInvitation.show();
            }
            member["thumbnail"] = osparc.utils.Avatar.getUrl(member["email"], 32);
            membersModel.append(qx.data.marshal.Json.createModel(member));
          });
        });
    }
  }
});
