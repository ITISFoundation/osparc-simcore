qx.Class.define("qxapp.data.model.ProjectModel", {
  extend: qx.core.Object,

  construct: function(prjData) {
    this.base(arguments);

    if (prjData) {
      this.set({
        uuid: prjData.projectUuid,
        name: prjData.name,
        description: prjData.description,
        notes: prjData.notes,
        thumbnail: prjData.thumbnail,
        prjOwner: prjData.owner,
        collaborators: prjData.collaborators,
        creationDate: new Date(prjData.creationDate),
        lastChangeDate: new Date(prjData.lastChangeDate)
      });
    } else {
      this.set({
        prjOwner: qxapp.auth.Data.getInstance().getUserName(),
        creationDate: new Date(),
        lastChangeDate: new Date()
      });
    }

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
