qx.Class.define("qxapp.data.model.Project", {
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
        lastChangeDate: new Date(prjData.lastChangeDate) || this.getLastChangeDate(),
        workbench: prjData.workbench || this.getWorkbench()
      });
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
      check: "Object",
      nullable: true,
      event: "changeWorkbench",
      init: {}
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
    },

    toStringOld: function() {
      // return qx.dev.Debug.debugProperties(this, 3, false, 2);
      let newLine = "\n";
      let indent = 4;
      let html = false;
      const maxLevel = 5;
      let message = "";

      let properties = this.constructor.$$properties;
      for (let key in properties) {
        message += newLine;
        // print out the indentation
        for (var j = 0; j < indent; j++) {
          message += "-";
        }
        message += " " + key + ": " + this.toString(
          this["get" + qx.lang.String.firstUp(key)](), maxLevel - 1, html, indent + 1
        );
      }
      return message;
    }
  }
});
