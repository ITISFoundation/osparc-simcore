/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *
 */

qx.Class.define("osparc.component.export.Permissions", {
  extend: qx.ui.core.Widget,

  construct: function(study) {
    this.base(arguments);

    this.__study = study;

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildLayout();

    this.__getMyFriends();
  },

  members: {
    __study: null,
    __myself: null,
    __myFrieds: null,

    createWindow: function() {
      return osparc.component.export.ShareResourceBase.createWindow(this.tr("Share with people and organizations"), this);
    },

    __buildLayout: function() {
      const addCollaborator = this.__createAddCollaborator();
      this._add(addCollaborator);

      const collaboratorsList = this.__createCollaboratorsList();
      this._add(collaboratorsList, {
        flex: 1
      });
    },

    __createAddCollaborator: function() {
      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      }));

      const userEmail = new qx.ui.form.TextField().set({
        required: true,
        placeholder: this.tr("Add Collaborators and Organizations")
      });
      userEmail.setRequired(true);
      hBox.add(userEmail, {
        flex: 1
      });

      const inviteBtn = new qx.ui.form.Button(this.tr("Invite"));
      inviteBtn.addListener("execute", function() {
        this.__addCollaborator(userEmail.getValue(), inviteBtn);
      }, this);
      hBox.add(inviteBtn);

      return hBox;
    },

    __createCollaboratorsList: function() {
      const collaboratorsUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        width: 150
      });

      const collaboratorsModel = this.__collaboratorsModel = new qx.data.Array();
      const collaboratorsCtrl = new qx.data.controller.List(collaboratorsModel, collaboratorsUIList, "name");
      collaboratorsCtrl.setDelegate({
        createItem: () => new osparc.dashboard.CollaboratorListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("gid", "model", null, item, id);
          ctrl.bindProperty("gid", "key", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id); // user
          ctrl.bindProperty("label", "title", null, item, id); // organization
          ctrl.bindProperty("login", "subtitle", null, item, id); // user
          ctrl.bindProperty("description", "subtitle", null, item, id); // organization
          ctrl.bindProperty("access_rights", "accessRights", null, item, id);
          ctrl.bindProperty("showOptions", "showOptions", null, item, id);
        },
        configureItem: item => {
          item.getChildControl("thumbnail").getContentElement()
            .setStyles({
              "border-radius": "16px"
            });
        }
      });

      return collaboratorsUIList;
    },

    __getMyFriends: function() {
      this.__myself = {};
      this.__myFrieds = {};
      osparc.data.Resources.get("organizations")
        .then(resp => {
          this.__myself[resp["me"]["gid"]] = resp["me"];
          const orgs = resp["organizations"];
          orgs.forEach(org => {
            this.__myFrieds[org["gid"]] = org;
          });
          this.__reloadCollaboratorsList();
        });
    },

    __reloadCollaboratorsList: function() {
      const aceessRights = this.__study["accessRights"];
      Object.keys(aceessRights).forEach(gid => {
        if (Object.prototype.hasOwnProperty.call(this.__myself, gid)) {
          this.__collaboratorsModel.insertAt(0, this.__myself[gid]);
        }
        if (Object.prototype.hasOwnProperty.call(this.__myFrieds, gid)) {
          this.__collaboratorsModel.append(this.__myFrieds[gid]);
        }
      });
    },

    __addCollaborator: function(gid, btn) {
      btn.setFetching(true);

      const shareWith = {};
      shareWith[gid] = {
        "read": true,
        "write": true,
        "execute": false
      };

      const params = {
        url: {
          "study_id": this._studyId
        },
        data: shareWith
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(template => {
          this.fireDataEvent("finished", template);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Study successfully shared."), "INFO");
          this.__reloadCollaboratorsList();
        })
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while sharing the study."), "ERROR");
        })
        .finally(() => {
          btn.setFetching(false);
        });
    }
  }
});
