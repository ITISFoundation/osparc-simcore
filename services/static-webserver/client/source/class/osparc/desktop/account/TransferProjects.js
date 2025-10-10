/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.account.TransferProjects", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments, this.tr("Transfer Projects"));

    this._setLayout(new qx.ui.layout.VBox(15));

    this.__buildLayout();
  },

  events: {
    "transferred": "qx.event.type.Event",
    "cancel": "qx.event.type.Event"
  },

  properties: {
    targetUser: {
      check: "osparc.data.model.User",
      init: null,
      nullable: true,
      event: "changeTargetUser",
    },
  },

  members: {
    _createChildControlImpl: function(id) {
      let control = null;
      switch (id) {
        case "intro-text": {
          const text = this.tr(`\
            You are about to transfer all your projects to another user.<br>
            There are two ways to do so:<br>
            - Share all your projects with the target user and keep the co-ownership. <br>
            - Share all your projects with the target user and remove yourself as co-owner. <br>
          `);
          control = new qx.ui.basic.Label().set({
            value: text,
            font: "text-14",
            rich: true,
            wrap: true
          });
          this._add(control);
          break;
        }
        case "target-user-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignY: "middle",
          }));
          const label = new qx.ui.basic.Label(this.tr("Target user:")).set({
            font: "text-14"
          });
          control.add(label);
          this._add(control);
          break;
        }
        case "target-user-button":
          control = new qx.ui.form.Button(this.tr("Select user")).set({
            appearance: "strong-button",
            allowGrowX: false,
          });
          this.bind("targetUser", control, "label", {
            converter: targetUser => targetUser ? targetUser.getUserName() : this.tr("Select user")
          });
          control.addListener("execute", () => this.__selectTargetUserTapped(), this);
          this.getChildControl("target-user-layout").add(control);
          break;
        case "buttons-container":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
            alignX: "right"
          }));
          this._add(control);
          break;
        case "cancel-button":
          control = new qx.ui.form.Button(this.tr("Cancel")).set({
            appearance: "form-button-text",
            allowGrowX: false,
          });
          control.addListener("execute", () => this.fireEvent("cancel"), this);
          this.getChildControl("buttons-container").add(control);
          break;
        case "share-and-keep-button":
          control = new osparc.ui.form.FetchButton(this.tr("Share and keep ownership")).set({
            appearance: "strong-button",
            allowGrowX: false,
          });
          this.bind("targetUser", control, "enabled", {
            converter: targetUser => targetUser !== null
          });
          control.addListener("execute", () => this.__shareAndKeepOwnership(), this);
          this.getChildControl("buttons-container").add(control);
          break;
        case "share-and-leave-button": {
          control = new osparc.ui.form.FetchButton(this.tr("Share and remove my ownership")).set({
            appearance: "danger-button",
            allowGrowX: false,
          });
          this.bind("targetUser", control, "enabled", {
            converter: targetUser => targetUser !== null
          });
          control.addListener("execute", () => this.__shareAndLeaveOwnership(), this);
          this.getChildControl("buttons-container").add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("intro-text");
      this.getChildControl("target-user-button");
      this.getChildControl("cancel-button");
      this.getChildControl("share-and-keep-button");
      this.getChildControl("share-and-leave-button");
    },

    __selectTargetUserTapped: function() {
      const collaboratorsManager = new osparc.share.NewCollaboratorsManager({}, false, false).set({
        acceptOnlyOne: true
      });
      collaboratorsManager.getChildControl("intro-text").set({
        value: this.tr("Select the user you want to transfer all your projects to.")
      });
      collaboratorsManager.setCaption(this.tr("Select target user"));
      collaboratorsManager.addListener("addCollaborators", e => {
        collaboratorsManager.close();
        const selectedUsers = e.getData();
        if (
          selectedUsers &&
          selectedUsers["selectedGids"] &&
          selectedUsers["selectedGids"].length === 1
        ) {
          osparc.store.Users.getInstance().getUser(selectedUsers["selectedGids"][0])
            .then(user => {
              if (user.getGroupId() !== osparc.store.Groups.getInstance().getMyGroupId()) {
                this.setTargetUser(user);
              } else {
                osparc.FlashMessenger.logAs(this.tr("You cannot transfer projects to yourself"), "ERROR");
              }
            });
        }
      }, this);
    },

    __shareAndKeepOwnership: function() {
      this.setEnabled(false);
      this.getChildControl("share-and-keep-button").setFetching(true);
      this.__shareAllProjects()
        .then(() => {
          const msg = this.tr("All projects have been shared with the target user. You still own them.");
          osparc.FlashMessenger.logAs(msg, "INFO", 10000);
          this.fireEvent("transferred");
        })
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.logError(err);
        })
        .finally(() => {
          this.setEnabled(true);
          this.getChildControl("share-and-keep-button").setFetching(false);
        });
    },

    __shareAndLeaveOwnership: function() {
      osparc.FlashMessenger.logAs(this.tr("This option is not yet enabled."), "WARNING", 10000);
      return;

      this.setEnabled(false);
      this.getChildControl("share-and-leave-button").setFetching(true);
      this.__shareAllProjects()
        .then(allMyStudies => {
          return this.__removeMyOwnerships(allMyStudies);
        })
        .then(() => {
          const msg = this.tr("All projects have been shared with the target user and you have been removed as co-owner.");
          osparc.FlashMessenger.logAs(msg, "INFO", 10000);
          this.fireEvent("transferred");
        })
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.logError(err);
        })
        .finally(() => {
          this.setEnabled(true);
          this.getChildControl("share-and-leave-button").setFetching(false);
        });
    },

    __filterMyOwnedStudies: function(allMyReadStudies) {
      // filter those that I don't own (no delete right)
      const myGroupId = osparc.store.Groups.getInstance().getMyGroupId();
      const ownerAccess = osparc.data.Roles.STUDY["delete"].accessRights;
      const allMyStudies = allMyReadStudies.filter(studyData => {
        return (
          myGroupId in studyData["accessRights"] &&
          JSON.stringify(studyData["accessRights"][myGroupId]) === JSON.stringify(ownerAccess)
        )
      });
      return allMyStudies;
    },

    __shareAllProjects: function() {
      const targetUser = this.getTargetUser();
      if (targetUser === null) {
        return;
      }
      const targetGroupId = targetUser.getGroupId();

      return osparc.store.Study.getInstance().getAllMyStudies()
        .then(allMyReadStudies => {
          // filter those that I don't own (no delete right)
          const allMyStudies = this.__filterMyOwnedStudies(allMyReadStudies);
          const ownerAccess = osparc.data.Roles.STUDY["delete"].accessRights;
          const newAccessRights = {
            [targetGroupId]: ownerAccess
          };
          const promises = [];
          allMyStudies.forEach(studyData => {
            // first check it's not already shared with the target user
            if (targetGroupId in studyData["accessRights"]) {
              if (JSON.stringify(studyData["accessRights"][targetGroupId]) !== JSON.stringify(ownerAccess)) {
                // update access rights to owner
                promises.push(osparc.store.Study.getInstance().updateCollaborator(studyData, targetGroupId, ownerAccess));
              }
            } else {
              // add as new collaborator with owner rights
              promises.push(osparc.store.Study.getInstance().addCollaborators(studyData, newAccessRights));
            }
          });
          // return only those projects that were shared
          return Promise.all(promises)
            .then(() => {
              return allMyStudies;
            })
            .catch(err => {
              console.error("Error sharing projects:", err);
            });
        });
    },

    __removeMyOwnerships: function(studies) {
      const myGroupId = osparc.store.Groups.getInstance().getMyGroupId();
      const promises = studies.map(study => {
        return osparc.store.Study.getInstance().removeCollaborator(study, myGroupId);
      });
      return Promise.all(promises);
    },
  }
});
