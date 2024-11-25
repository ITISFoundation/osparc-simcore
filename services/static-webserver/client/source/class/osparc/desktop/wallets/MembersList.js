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
      const sorted = osparc.share.Collaborators.sortByAccessRights(a["accessRights"], b["accessRights"]);
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
        const myAccessRights = wallet.getMyAccessRights();
        if (myAccessRights) {
          return myAccessRights["write"];
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
        const serializedData = this.__currentModel.serialize();
        serializedData["resourceType"] = "wallet";
        const showOrganizations = false;
        const collaboratorsManager = new osparc.share.NewCollaboratorsManager(serializedData, showOrganizations);
        collaboratorsManager.addListener("addCollaborators", e => {
          const cb = () => collaboratorsManager.close();
          this.__addMembers(e.getData(), cb);
        }, this);
      }, this);
      vBox.add(addMemberBtn);

      return vBox;
    },

    __getRolesToolbar: function() {
      return osparc.data.Roles.createRolesWalletInfo();
    },

    __getMembersFilter: function() {
      const filter = new osparc.filter.TextFilter("text", "walletMembersList").set({
        allowStretchX: true,
        margin: [0, 10, 5, 10]
      });
      return filter;
    },

    __getMembersList: function() {
      const membersUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        width: 150
      });

      const membersModel = this.__membersModel = new qx.data.Array();
      const membersCtrl = new qx.data.controller.List(membersModel, membersUIList, "name");
      membersCtrl.setDelegate({
        createItem: () => new osparc.desktop.wallets.MemberListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("userId", "model", null, item, id);
          ctrl.bindProperty("userId", "key", null, item, id);
          ctrl.bindProperty("groupId", "gid", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id);
          ctrl.bindProperty("accessRights", "accessRights", null, item, id);
          ctrl.bindProperty("login", "subtitleMD", null, item, id);
          ctrl.bindProperty("options", "options", null, item, id);
          ctrl.bindProperty("showOptions", "showOptions", null, item, id);
        },
        configureItem: item => {
          item.subscribeToFilterGroup("walletMembersList");
          item.getChildControl("thumbnail").getContentElement()
            .setStyles({
              "border-radius": "16px"
            });
          item.addListener("promoteToAccountant", e => {
            const listedMember = e.getData();
            this.__promoteToAccountant(listedMember);
          });
          item.addListener("demoteToMember", e => {
            const listedMember = e.getData();
            this.__demoteToMember(listedMember);
          });
          item.addListener("removeMember", e => {
            const listedMember = e.getData();
            this.__deleteMember(listedMember);
          });
        }
      });

      return membersUIList;
    },

    __reloadWalletMembers: async function() {
      const membersModel = this.__membersModel;
      membersModel.removeAll();

      const wallet = this.__currentModel;
      if (wallet === null) {
        return;
      }

      const myGroupId = osparc.auth.Data.getInstance().getGroupId();
      const membersList = [];
      const potentialCollaborators = osparc.store.Groups.getInstance().getPotentialCollaborators(true);
      const canIWrite = wallet.getMyAccessRights()["write"];
      wallet.getAccessRights().forEach(accessRights => {
        const gid = parseInt(accessRights["gid"]);
        if (Object.prototype.hasOwnProperty.call(potentialCollaborators, gid)) {
          // only users or groupMe
          const collab = potentialCollaborators[gid];
          const collaborator = {};
          collaborator["userId"] = gid === myGroupId ? osparc.auth.Data.getInstance().getUserId() : collab.getUserId();
          collaborator["groupId"] = collab.getGroupId();
          collaborator["thumbnail"] = collab.getThumbnail();
          collaborator["name"] = collab.getLabel();
          collaborator["login"] = gid === myGroupId ? osparc.auth.Data.getInstance().getEmail() : collab.getLogin();
          collaborator["accessRights"] = {
            read: accessRights["read"],
            write: accessRights["write"],
            delete: accessRights["delete"],
          };
          let options = [];
          if (canIWrite) {
            // accountant...
            if (gid === myGroupId) {
              // it's me
              options = [];
            } else if (collaborator["accessRights"]["write"]) {
              // ...on accountant
              options = [
                // "demoteToMember", // only allow one Accountant per Wallet, we shouldn't get here
                "removeMember"
              ];
            } else if (collaborator["accessRights"]["read"]) {
              // ...on member
              options = [
                // "promoteToAccountant", // only allow one Accountant per Wallet
                "removeMember"
              ];
            }
          }
          collaborator["options"] = options;
          collaborator["showOptions"] = Boolean(options.length);
          membersList.push(collaborator);
        }
      });
      membersList.sort(this.self().sortWalletMembers);
      membersList.forEach(member => membersModel.append(qx.data.marshal.Json.createModel(member)));
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
          osparc.store.Store.getInstance().reloadWalletAccessRights(wallet)
            .then(() => {
              this.__reloadWalletMembers();
              if (cb) {
                cb();
              }
            });

          // push 'WALLET_SHARED' notification
          const potentialCollaborators = osparc.store.Groups.getInstance().getPotentialCollaborators();
          gids.forEach(gid => {
            if (gid in potentialCollaborators && "getUserId" in potentialCollaborators[gid]) {
              // it's a user, not an organization
              const uid = potentialCollaborators[gid].getUserId();
              osparc.notification.Notifications.postNewWallet(uid, wallet.getWalletId());
            }
          });
        });
    },

    __promoteToAccountant: function(listedMember) {
      const wallet = this.__currentModel;
      if (wallet === null) {
        return;
      }

      const params = {
        url: {
          "walletId": wallet.getWalletId(),
          "groupId": listedMember["gid"],
        },
        data: this.self().getWriteAccess()
      };
      osparc.data.Resources.fetch("wallets", "putAccessRights", params)
        .then(() => {
          osparc.store.Store.getInstance().reloadWalletAccessRights(wallet)
            .then(() => this.__reloadWalletMembers());
        });
    },

    __demoteToMember: function(listedMember) {
      const wallet = this.__currentModel;
      if (wallet === null) {
        return;
      }

      const params = {
        url: {
          "walletId": wallet.getWalletId(),
          "groupId": listedMember["gid"],
        },
        data: this.self().getReadAccess()
      };
      osparc.data.Resources.fetch("wallets", "putAccessRights", params)
        .then(() => {
          osparc.store.Store.getInstance().reloadWalletAccessRights(wallet)
            .then(() => this.__reloadWalletMembers());
        });
    },

    __deleteMember: function(listedMember) {
      const wallet = this.__currentModel;
      if (wallet === null) {
        return;
      }

      const params = {
        url: {
          "walletId": wallet.getWalletId(),
          "groupId": listedMember["gid"],
        }
      };
      osparc.data.Resources.fetch("wallets", "deleteAccessRights", params)
        .then(() => {
          osparc.store.Store.getInstance().reloadWalletAccessRights(wallet)
            .then(() => this.__reloadWalletMembers());
        });
    }
  }
});
