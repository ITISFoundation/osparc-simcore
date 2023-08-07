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

qx.Class.define("osparc.desktop.wallets.MembersList", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this._add(this.__createIntroText());
    this._add(this.__getMemberInvitation());
    this._add(this.__getRolesToolbar());
    this._add(this.__getMembersFilter());
    this._add(this.__getMembersList(), {
      flex: 1
    });
  },

  statics: {
    getNoReadAccess: function() {
      return {
        "read": false,
        "write": false,
        "delete": false
      };
    },

    getReadAccess: function() {
      return {
        "read": true,
        "write": false,
        "delete": false
      };
    },

    getWriteAccess: function() {
      return {
        "read": true,
        "write": true,
        "delete": false
      };
    },

    getDeleteAccess: function() {
      return {
        "read": true,
        "write": true,
        "delete": true
      };
    },

    sortWalletMembers: function(a, b) {
      const sorted = osparc.component.share.Collaborators.sortByAccessRights(a["accessRights"], b["accessRights"]);
      if (sorted !== 0) {
        return sorted;
      }
      if (("login" in a) && ("login" in b)) {
        return a["login"].localeCompare(b["login"]);
      }
      return 0;
    }
  },

  members: {
    __currentModel: null,
    __memberInvitation: null,
    __membersModel: null,

    setWallet: function(model) {
      if (model === null) {
        return;
      }

      this.__currentModel = model;

      this.__memberInvitation.setVisibility(this.__canIWrite() ? "visible" : "excluded");

      this.__reloadWalletMembers();
    },

    __canIWrite: function() {
      const wallet = this.__currentModel;
      if (wallet) {
        const myAcessRights = wallet.getMyAccessRights();
        if (myAcessRights) {
          return myAcessRights["write"];
        }
      }
      return false;
    },

    __createIntroText: function() {
      const msg = this.tr("Only Accountants of an organization can share a wallet with the entire organization and members.");
      const intro = new qx.ui.basic.Label().set({
        value: msg,
        alignX: "left",
        rich: true,
        font: "text-13"
      });
      return intro;
    },

    __getMemberInvitation: function() {
      const vBox = this.__memberInvitation = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      vBox.exclude();

      const label = new qx.ui.basic.Label(this.tr("Select from the list below and click Share"));
      vBox.add(label);

      const addMemberBtn = new qx.ui.form.Button(this.tr("Add Members...")).set({
        appearance: "strong-button",
        allowGrowX: false
      });
      addMemberBtn.addListener("execute", () => {
        const collaboratorsManager = new osparc.component.share.NewCollaboratorsManager(this._serializedData);
        collaboratorsManager.addListener("addCollaborators", e => {
          const cb = () => collaboratorsManager.close();
          this.__addMembers(e.getData(), cb);
        }, this);
      }, this);
      vBox.add(addMemberBtn);

      return vBox;
    },

    __getRolesToolbar: function() {
      return osparc.data.Roles.createRolesWalleltInfo();
    },

    __getMembersFilter: function() {
      const filter = new osparc.component.filter.TextFilter("text", "walletMembersList").set({
        allowStretchX: true,
        margin: [0, 10, 5, 10]
      });
      return filter;
    },

    __getMembersList: function() {
      const memebersUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        width: 150,
        backgroundColor: "background-main-2"
      });

      const membersModel = this.__membersModel = new qx.data.Array();
      const membersCtrl = new qx.data.controller.List(membersModel, memebersUIList, "name");
      membersCtrl.setDelegate({
        createItem: () => new osparc.desktop.wallets.MemberListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("id", "model", null, item, id);
          ctrl.bindProperty("id", "key", null, item, id);
          ctrl.bindProperty("gid", "gid", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id);
          ctrl.bindProperty("accessRights", "accessRights", null, item, id);
          ctrl.bindProperty("login", "subtitleMD", null, item, id);
          ctrl.bindProperty("showOptions", "showOptions", null, item, id);
        },
        configureItem: item => {
          item.subscribeToFilterGroup("organizationMembersList");
          item.getChildControl("thumbnail").getContentElement()
            .setStyles({
              "border-radius": "16px"
            });
          item.addListener("promoteToAccountant", e => {
            const walletMember = e.getData();
            this.__promoteToAccountant(walletMember);
          });
          item.addListener("demoteToMember", e => {
            const walletMember = e.getData();
            this.__demoteToMember(walletMember);
          });
          item.addListener("removeMember", e => {
            const walletMember = e.getData();
            this.__deleteMember(walletMember);
          });
        }
      });

      return memebersUIList;
    },

    __reloadWalletMembers: async function() {
      const membersModel = this.__membersModel;
      membersModel.removeAll();

      const wallet = this.__currentModel;
      if (wallet === null) {
        return;
      }

      const membersList = [];
      const potentialCollaborators = await osparc.store.Store.getInstance().getPotentialCollaborators();
      const params = {
        url: {
          "walletId": wallet.getWalletId()
        }
      };
      osparc.data.Resources.fetch("wallets", "getAccessRights", params)
        .then(accessRightss => {
          accessRightss.forEach(accessRights => {
            const gid = accessRights["gid"];
            if (Object.prototype.hasOwnProperty.call(potentialCollaborators, parseInt(gid))) {
              const collab = potentialCollaborators[parseInt(gid)];
              // Do not override collaborator object
              const collaborator = osparc.utils.Utils.deepCloneObject(collab);
              if ("first_name" in collaborator) {
                collaborator["thumbnail"] = osparc.utils.Avatar.getUrl(collaborator["login"], 32);
                collaborator["name"] = osparc.utils.Utils.firstsUp(collaborator["first_name"], collaborator["last_name"]);
              }
              collaborator["accessRights"] = accessRights;
              collaborator["showOptions"] = this.__canIWrite();
              membersList.push(collaborator);
            }
          });
          membersList.sort(this.self().sortWalletMembers);
          membersList.forEach(member => membersModel.append(qx.data.marshal.Json.createModel(member)));
        });
    },

    __addMembers: function(gids, cb) {
      if (gids.length === 0) {
        return;
      }
      const wallet = this.__currentModel;
      if (wallet === null) {
        return;
      }

      const promises = [];
      gids.forEach(gid => {
        const params = {
          url: {
            "walletId": wallet.getWalletId(),
            "groupId": gid
          },
          data: this.self().getReadAccess()
        };
        promises.push(osparc.data.Resources.fetch("wallets", "postAccessRights", params));
      });
      Promise.all(promises)
        .then(() => {
          this.__reloadWalletMembers();
          if (cb) {
            cb();
          }
        });
    },

    __promoteToAccountant: function(walletMember) {
      const wallet = this.__currentModel;
      if (wallet === null) {
        return;
      }

      const newAccessRights = osparc.utils.Utils.deepCloneObject(wallet.getAccessRights());
      if (walletMember["gid"] in newAccessRights) {
        newAccessRights[walletMember["gid"]] = this.self().getWriteAccess();
        wallet.setAccessRights(newAccessRights);
        this.__reloadWalletMembers();
      }
    },

    __demoteToMember: function(walletMember) {
      const wallet = this.__currentModel;
      if (wallet === null) {
        return;
      }

      const newAccessRights = osparc.utils.Utils.deepCloneObject(wallet.getAccessRights());
      if (walletMember["gid"] in newAccessRights) {
        newAccessRights[walletMember["gid"]] = this.self().getReadAccess();
        wallet.setAccessRights(newAccessRights);
        this.__reloadWalletMembers();
      }
    },

    __deleteMember: function(walletMember) {
      const wallet = this.__currentModel;
      if (wallet === null) {
        return;
      }

      const newAccessRights = osparc.utils.Utils.deepCloneObject(wallet.getAccessRights());
      if (walletMember["gid"] in newAccessRights) {
        delete newAccessRights[walletMember["gid"]];
        wallet.setAccessRights(newAccessRights);
        this.__reloadWalletMembers();
      }
    }
  }
});
