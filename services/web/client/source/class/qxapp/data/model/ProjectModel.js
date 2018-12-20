/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("qxapp.data.model.ProjectModel", {
  extend: qx.core.Object,

  construct: function(prjData) {
    this.base(arguments);

    this.set({
      uuid: prjData.uuid || this.getUuid(),
      name: prjData.name || this.getName(),
      description: prjData.description || this.getDescription(),
      notes: prjData.notes || this.getNotes(),
      thumbnail: prjData.thumbnail || this.getThumbnail(),
      prjOwner: prjData.prjOwner || qxapp.auth.Data.getInstance().getUserName(),
      collaborators: prjData.collaborators || this.getCollaborators(),
      creationDate: prjData.creationDate ? new Date(prjData.creationDate) : this.getCreationDate(),
      lastChangeDate: prjData.lastChangeDate ? new Date(prjData.lastChangeDate) : this.getLastChangeDate()
    });

    if (prjData && prjData.workbench) {
      this.setWorkbenchModel(new qxapp.data.model.WorkbenchModel(this.getName(), prjData.workbench));
    } else {
      this.setWorkbenchModel(new qxapp.data.model.WorkbenchModel(this.getName(), {}));
    }
  },

  properties: {
    uuid: {
      check: "String",
      nullable: false,
      init: qxapp.utils.Utils.uuidv4()
    },

    name: {
      check: "String",
      nullable: false,
      init: "New Project",
      event: "changeName",
      apply : "__applyName"
    },

    description: {
      check: "String",
      nullable: true,
      init: ""
    },

    notes: {
      check: "String",
      nullable: true,
      init: ""
    },

    thumbnail: {
      check: "String",
      nullable: true,
      init: ""
    },

    prjOwner: {
      check: "String",
      nullable: true,
      init: ""
    },

    collaborators: {
      check: "Object",
      nullable: true,
      init: {}
    },

    creationDate: {
      check: "Date",
      nullable: true,
      init: new Date()
    },

    lastChangeDate: {
      check: "Date",
      nullable: true,
      init: new Date()
    },

    workbenchModel: {
      check: "qxapp.data.model.WorkbenchModel",
      nullable: false
    }
  },

  members: {
    __applyName: function(newName) {
      if (this.isPropertyInitialized("workbenchModel")) {
        this.getWorkbenchModel().setProjectName(newName);
      }
    },

    serializeProject: function() {
      this.setLastChangeDate(new Date());

      let jsonObject = {};
      let properties = this.constructor.$$properties;
      for (let key in properties) {
        if (key === "workbenchModel") {
          jsonObject["workbench"] = this.getWorkbenchModel().serializeWorkbench();
        } else {
          jsonObject[key] = this.get(key);
        }
      }
      return jsonObject;
    }
  }
});
