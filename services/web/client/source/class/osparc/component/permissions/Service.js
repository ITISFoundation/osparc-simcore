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
 * Widget for modifying Service permissions. This is the way for sharing studies
 * - Creates a copy of service data
 * - It allows changing study's access right, so that the study owners can:
 *   - Share it with Organizations and/or Organization Members (Collaborators)
 *   - Make other Collaborators Owner
 *   - Remove collaborators
 */

qx.Class.define("osparc.component.permissions.Service", {
  extend: osparc.component.permissions.Permissions,

  /**
    * @param serviceData {Object} Object containing the Service Data
    */
  construct: function(serviceData) {
    const serializedData = osparc.utils.Utils.deepCloneObject(serviceData);

    const initCollabs = this.self().getEveryoneObj();
    this.base(arguments, serializedData, [initCollabs]);

    // add a dropdown menu for selection the service version
    const versionSelectionSection = this.__createVersionSelectionSection();
    this._addAt(versionSelectionSection, 0);
  },

  events: {
    "updateService": "qx.event.type.Data"
  },

  statics: {
    canGroupWrite: function(accessRights, GID) {
      if (GID in accessRights) {
        return accessRights[GID]["write_access"];
      }
      return false;
    },

    canAnyGroupWrite: function(accessRights, GIDs) {
      let canWrite = false;
      for (let i=0; i<GIDs.length && !canWrite; i++) {
        canWrite = this.self().canGroupWrite(accessRights, GIDs[i]);
      }
      return canWrite;
    },

    getCollaboratorAccessRight: function() {
      return {
        "execute_access": true,
        "write_access": false
      };
    },

    getOwnerAccessRight: function() {
      return {
        "execute_access": true,
        "write_access": true
      };
    },

    removeCollaborator: function(serializedData, gid) {
      return delete serializedData["access_rights"][gid];
    },

    getEveryoneObj: function() {
      return {
        "gid": 1,
        "label": "Everyone",
        "description": "",
        "thumbnail": null,
        "accessRights": this.getCollaboratorAccessRight(),
        "collabType": 0
      };
    }
  },

  members: {
    __versionsBox: null,

    __createVersionSelectionSection: function() {
      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      }));

      const versionLabel = new qx.ui.basic.Label(this.tr("Service Version"));
      hBox.add(versionLabel);
      const versionsBox = this.__versionsBox = new osparc.ui.toolbar.SelectBox();
      hBox.add(versionsBox);

      this.__populateOwnedVersions();

      versionsBox.addListener("changeSelection", () => {
        const selection = versionsBox.getSelection();
        if (selection && selection.length) {
          const serviceVersion = selection[0].getLabel();
          if (serviceVersion !== this._serializedData["version"]) {
            const store = osparc.store.Store.getInstance();
            store.getServicesDAGs(false)
              .then(services => {
                const serviceData = osparc.utils.Services.getFromObject(services, this._serializedData["key"], serviceVersion);
                this._serializedData = osparc.utils.Utils.deepCloneObject(serviceData);
                this.getCollaborators();
              });
          }
        }
      }, this);

      return hBox;
    },

    __populateOwnedVersions: function() {
      const store = osparc.store.Store.getInstance();
      store.getServicesDAGs(false)
        .then(services => {
          const myEmail = osparc.auth.Data.getInstance().getEmail();
          const versions = osparc.utils.Services.getOwnedServices(services, this._serializedData["key"], myEmail);
          const selectBox = this.__versionsBox;
          versions.reverse();
          let item = null;
          versions.forEach(version => {
            item = new qx.ui.form.ListItem(version);
            selectBox.add(item);
            if (this._serializedData["version"] === version) {
              selectBox.setSelection([item]);
            }
          });
        });
    },

    __getSelectedService: function() {
      const selected = this.__serviceBrowser.getSelected();
      const key = selected.getKey();
      let version = this.__versionsBox.getSelection()[0].getLabel().toString();
      if (version == this.self(arguments).LATEST.toString()) {
        version = this.__versionsBox.getChildrenContainer().getSelectables()[1].getLabel();
      }
      return osparc.utils.Services.getFromArray(this.__allServicesList, key, version);
    },

    _isUserOwner: function() {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const aceessRights = this._serializedData["access_rights"];
      if (myGid in aceessRights) {
        return aceessRights[myGid]["write_access"];
      }
      return false;
    },

    _addCollaborator: function() {
      const gids = this.__organizationsAndMembers.getSelectedGIDs();
      if (gids.length === 0) {
        return;
      }
      gids.forEach(gid => {
        this._serializedData["access_rights"][gid] = this.self().getCollaboratorAccessRight();
      });
      const params = {
        url: osparc.data.Resources.getServiceUrl(
          this._serializedData["key"],
          this._serializedData["version"]
        ),
        data: this._serializedData
      };
      osparc.data.Resources.fetch("services", "patch", params)
        .then(serviceData => {
          this.fireDataEvent("updateService", serviceData);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Collaborator(s) successfully added"));
          this.__reloadOrganizationsAndMembers();
          this.__reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went adding collaborator(s)"), "ERROR");
          console.error(err);
        });
    },

    _deleteCollaborator: function(collaborator) {
      const success = this.self().removeCollaborator(this._serializedData, collaborator["gid"]);
      if (!success) {
        osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong removing Collaborator"), "ERROR");
      }

      const params = {
        url: osparc.data.Resources.getServiceUrl(
          this._serializedData["key"],
          this._serializedData["version"]
        ),
        data: this._serializedData
      };
      osparc.data.Resources.fetch("services", "patch", params)
        .then(serviceData => {
          this.fireDataEvent("updateService", serviceData);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Collaborator successfully removed"));
          this.__reloadOrganizationsAndMembers();
          this.__reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong removing Collaborator"), "ERROR");
          console.error(err);
        });
    },

    _makeOwner: function(collaborator) {
      this._serializedData["access_rights"][collaborator["gid"]] = this.self().getOwnerAccessRight();
      const params = {
        url: osparc.data.Resources.getServiceUrl(
          this._serializedData["key"],
          this._serializedData["version"]
        ),
        data: this._serializedData
      };
      osparc.data.Resources.fetch("services", "patch", params)
        .then(serviceData => {
          this.fireDataEvent("updateService", serviceData);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Collaborator successfully made Owner"));
          this.__reloadOrganizationsAndMembers();
          this.__reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong making Collaborator Owner"), "ERROR");
          console.error(err);
        });
    },

    _makeCollaborator: function(collaborator) {
      return;
    },

    _makeViewer: function(collaborator) {
      return;
    }
  }
});
