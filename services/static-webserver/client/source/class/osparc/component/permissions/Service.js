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
  },

  events: {
    "updateService": "qx.event.type.Data"
  },

  statics: {
    canGroupsWrite: function(accessRights, gIds) {
      let canWrite = false;
      for (let i=0; i<gIds.length && !canWrite; i++) {
        const gid = gIds[i];
        canWrite = (gid in accessRights) ? accessRights[gid]["write_access"] : false;
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
      return delete serializedData["accessRights"][gid];
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
    _canIWrite: function() {
      return osparc.utils.Services.canIWrite(this._serializedData["accessRights"]);
    },

    _addCollaborator: function() {
      const gids = this.__organizationsAndMembers.getSelectedGIDs();
      if (gids.length === 0) {
        return;
      }
      gids.forEach(gid => {
        this._serializedData["accessRights"][gid] = this.self().getCollaboratorAccessRight();
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
      this._serializedData["accessRights"][collaborator["gid"]] = this.self().getOwnerAccessRight();
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
