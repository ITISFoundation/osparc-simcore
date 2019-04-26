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

/**
 * Class that stores Study data. It is also able to serialize itself.
 *
 *                                    -> {EDGES}
 * STUDY -> METADATA + WORKBENCH ->|
 *                                    -> {LINKS}
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let study = new qxapp.data.model.Study(studyData);
 *   let prjEditor = new qxapp.desktop.StudyEditor(study, isNew);
 * </pre>
 */

qx.Class.define("qxapp.data.model.Study", {
  extend: qx.core.Object,

  /**
    * @param studyData {Object} Object containing the serialized Project Data
    */
  construct: function(studyData) {
    this.base(arguments);

    this.set({
      uuid: studyData.uuid === undefined ? this.getUuid() : studyData.uuid,
      name: studyData.name === undefined ? this.getName() : studyData.name,
      description: studyData.description === undefined ? this.getDescription() : studyData.description,
      notes: studyData.notes === undefined ? this.getNotes() : studyData.notes,
      thumbnail: studyData.thumbnail === undefined ? this.getThumbnail() : studyData.thumbnail,
      prjOwner: studyData.prjOwner === undefined ? qxapp.auth.Data.getInstance().getUserName() : studyData.prjOwner,
      collaborators: studyData.collaborators === undefined ? this.getCollaborators() : studyData.collaborators,
      creationDate: studyData.creationDate === undefined ? this.getCreationDate() : new Date(studyData.creationDate),
      lastChangeDate: studyData.lastChangeDate === undefined ? this.getLastChangeDate() : new Date(studyData.lastChangeDate)
    });

    const wbData = studyData.workbench === undefined ? {} : studyData.workbench;
    this.setWorkbench(new qxapp.data.model.Workbench(this, wbData));
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
      init: "New Study",
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

    workbench: {
      check: "qxapp.data.model.Workbench",
      nullable: false
    }
  },

  members: {
    __applyName: function(newName) {
      if (this.isPropertyInitialized("workbench")) {
        this.getWorkbench().setStudyName(newName);
      }
    },

    serializeStudy: function() {
      this.setLastChangeDate(new Date());

      let jsonObject = {};
      let properties = this.constructor.$$properties;
      for (let key in properties) {
        let value = key === "workbench" ? this.getWorkbench().serializeWorkbench() : this.get(key);
        if (value !== null) {
          // only put the value in the payload if there is a value
          jsonObject[key] = value;
        }
      }
      return jsonObject;
    }
  }
});
