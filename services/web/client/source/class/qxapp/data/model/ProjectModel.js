qx.Class.define("qxapp.data.model.ProjectModel", {
  extend: qx.core.Object,

  construct: function(prjData) {
    this.base(arguments);

    if (prjData) {
      this.set({
        uuid: prjData.projectUuid || this.getUuid(),
        name: prjData.name || this.getName(),
        description: prjData.description || this.getDescription(),
        notes: prjData.notes || this.getNotes(),
        thumbnail: prjData.thumbnail || this.getThumbnail(),
        collaborators: prjData.collaborators || this.getCollaborators(),
        creationDate: new Date(prjData.creationDate) || this.getCreationDate(),
        lastChangeDate: new Date(prjData.lastChangeDate) || this.getLastChangeDate()
      });
    }

    if (prjData && prjData.workbench) {
      this.setWorkbench(new qxapp.data.model.WorkbenchModel(prjData.workbench));
    } else {
      this.setWorkbench(new qxapp.data.model.WorkbenchModel({}));
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
      init: "New Project"
    },

    description: {
      check: "String",
      nullable: true,
      init: "Empty"
    },

    notes: {
      check: "String",
      nullable: true,
      init: "Empty"
    },

    thumbnail: {
      check: "String",
      nullable: true,
      init: "https://imgplaceholder.com/171x96/cccccc/757575/ion-plus-round"
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

    workbench: {
      check: "qxapp.data.model.WorkbenchModel",
      nullable: false
    }
  },

  members: {
    getJsonObject: function() {
      let jsonObject = {};
      let properties = this.constructor.$$properties;
      for (let key in properties) {
        jsonObject[key] = this.get(key);
      }
      return jsonObject;
    }
  }
});
