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
 *                                    -> {NODES}
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
    * @param studyData {String} uuid if the link. If not provided, a random one will be assigned
  */
  construct: function(studyData) {
    this.base(arguments);

    this.set({
      uuid: studyData.uuid || this.getUuid(),
      name: studyData.name || this.getName(),
      description: studyData.description || this.getDescription(),
      notes: studyData.notes || this.getNotes(),
      thumbnail: studyData.thumbnail || this.getThumbnail(),
      prjOwner: studyData.prjOwner || qxapp.auth.Data.getInstance().getUserName(),
      collaborators: studyData.collaborators || this.getCollaborators(),
      creationDate: studyData.creationDate ? new Date(studyData.creationDate) : this.getCreationDate(),
      lastChangeDate: studyData.lastChangeDate ? new Date(studyData.lastChangeDate) : this.getLastChangeDate()
    });

    if (studyData && studyData.workbench) {
      this.setWorkbench(new qxapp.data.model.Workbench(this.getName(), studyData.workbench));
    } else {
      this.setWorkbench(new qxapp.data.model.Workbench(this.getName(), {}));
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
