/* ************************************************************************

   osparc - the simcore frontend

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
 *   const study = new osparc.data.model.Study(studyData);
 *   const studyEditor = new osparc.desktop.StudyEditor();
 *   studyEditor.setStudy(study);
 * </pre>
 */

qx.Class.define("osparc.data.model.Study", {
  extend: qx.core.Object,

  /**
   * @param studyData {Object} Object containing the serialized Study Data
   */
  construct: function(studyData) {
    this.base(arguments);

    this.set({
      uuid: studyData.uuid === undefined ? this.getUuid() : studyData.uuid,
      name: studyData.name === undefined ? this.getName() : studyData.name,
      description: studyData.description === undefined ? this.getDescription() : studyData.description,
      thumbnail: studyData.thumbnail === undefined ? this.getThumbnail() : studyData.thumbnail,
      prjOwner: studyData.prjOwner === undefined ? osparc.auth.Data.getInstance().getUserName() : studyData.prjOwner,
      accessRights: studyData.accessRights === undefined ? this.getAccessRights() : studyData.accessRights,
      creationDate: studyData.creationDate === undefined ? this.getCreationDate() : new Date(studyData.creationDate),
      lastChangeDate: studyData.lastChangeDate === undefined ? this.getLastChangeDate() : new Date(studyData.lastChangeDate),
      classifiers: studyData.classifiers && studyData.classifiers ? studyData.classifiers : [],
      tags: studyData.tags || []
    });

    const wbData = studyData.workbench === undefined ? {} : studyData.workbench;
    this.setWorkbench(new osparc.data.model.Workbench(wbData, studyData.ui));
    this.setUi(new osparc.data.model.StudyUI(studyData.ui));

    this.setSweeper(new osparc.data.model.Sweeper(studyData));
  },

  properties: {
    uuid: {
      check: "String",
      nullable: false,
      init: osparc.utils.Utils.uuidv4()
    },

    name: {
      check: "String",
      nullable: false,
      event: "changeName",
      init: "New Study"
    },

    description: {
      check: "String",
      nullable: false,
      event: "changeDescription",
      init: ""
    },

    thumbnail: {
      check: "String",
      nullable: true,
      event: "changeThumbnail",
      init: ""
    },

    prjOwner: {
      check: "String",
      nullable: false,
      event: "changePrjOwner",
      init: ""
    },

    accessRights: {
      check: "Object",
      nullable: false,
      event: "changeAccessRights",
      init: {}
    },

    creationDate: {
      check: "Date",
      nullable: false,
      event: "changeCreationDate",
      init: new Date()
    },

    lastChangeDate: {
      check: "Date",
      nullable: false,
      event: "changeLastChangeDate",
      init: new Date()
    },

    workbench: {
      check: "osparc.data.model.Workbench",
      nullable: false
    },

    ui: {
      check: "osparc.data.model.StudyUI",
      nullable: false
    },

    classifiers: {
      check: "Array",
      init: []
    },

    tags: {
      check: "Array",
      init: []
    },

    sweeper: {
      check: "osparc.data.model.Sweeper",
      nullable: false
    }
  },

  statics: {
    createMinimumStudyObject: function() {
      // TODO: Check if this can be automatically generated from schema
      return {
        uuid: "",
        name: "",
        description: "",
        thumbnail: "",
        prjOwner: "",
        accessRights: {},
        creationDate: new Date(),
        lastChangeDate: new Date(),
        workbench: {},
        tags: []
      };
    },

    updateStudy: function(params) {
      return osparc.data.Resources.fetch("studies", "put", {
        url: {
          projectId: params.uuid
        },
        data: params
      }).then(data => {
        qx.event.message.Bus.getInstance().dispatchByName("updateStudy", data);
        return data;
      });
    },

    getProperties: function() {
      return Object.keys(qx.util.PropertyUtil.getProperties(osparc.data.model.Study));
    },

    // deep clones object with study-only properties
    deepCloneStudyObject: function(src) {
      const studyObject = osparc.utils.Utils.deepCloneObject(src);
      const studyPropKeys = osparc.data.model.Study.getProperties();
      Object.keys(studyObject).forEach(key => {
        if (!studyPropKeys.includes(key)) {
          delete studyObject[key];
        }
      });
      return studyObject;
    },

    isStudySecondary: function(studyData) {
      if ("dev" in studyData && "sweeper" in studyData["dev"] && "primaryStudyId" in studyData["dev"]["sweeper"]) {
        return true;
      }
      return false;
    },

    isOwner: function(studyData) {
      if (studyData instanceof osparc.data.model.Study) {
        const myEmail = osparc.auth.Data.getInstance().getEmail();
        return studyData.getPrjOwner() === myEmail;
      }
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const aceessRights = studyData["accessRights"];
      if (myGid in aceessRights) {
        return aceessRights[myGid]["delete"];
      }
      return false;
    },

    hasSlideshow: function(studyData) {
      if ("ui" in studyData && "slideshow" in studyData["ui"] && Object.keys(studyData["ui"]["slideshow"]).length) {
        return true;
      }
      return false;
    }
  },

  members: {
    buildWorkbench: function() {
      this.getWorkbench().buildWorkbench();
    },

    openStudy: function() {
      const params = {
        url: {
          projectId: this.getUuid()
        },
        data: osparc.utils.Utils.getClientSessionID()
      };
      return osparc.data.Resources.fetch("studies", "open", params);
    },

    closeStudy: function() {
      this.removeIFrames();

      const params = {
        url: {
          projectId: this.getUuid()
        },
        data: osparc.utils.Utils.getClientSessionID()
      };
      osparc.data.Resources.fetch("studies", "close", params)
        .catch(err => console.error(err));
    },

    removeIFrames: function() {
      const nodes = this.getWorkbench().getNodes(true);
      for (const node of Object.values(nodes)) {
        node.removeIFrame();
      }
    },

    serialize: function() {
      let jsonObject = {};
      const propertyKeys = this.self().getProperties();
      propertyKeys.forEach(key => {
        if (key === "sweeper") {
          jsonObject["dev"] = {};
          jsonObject["dev"]["sweeper"] = this.getSweeper().serialize();
          return;
        }
        if (key === "ui") {
          jsonObject["ui"] = this.getUi().serialize();
          return;
        }
        let value = key === "workbench" ? this.getWorkbench().serialize() : this.get(key);
        if (value !== null) {
          // only put the value in the payload if there is a value
          jsonObject[key] = value;
        }
      });
      return jsonObject;
    },

    updateStudy: function(params) {
      return this.self().updateStudy({
        ...this.serialize(),
        ...params
      })
        .then(data => {
          // TODO OM: Hacky
          if ("dev" in data) {
            delete data["dev"];
          }
          this.set({
            ...data,
            creationDate: new Date(data.creationDate),
            lastChangeDate: new Date(data.lastChangeDate),
            workbench: this.getWorkbench(),
            sweeper: this.getSweeper()
          });
          return data;
        });
    }
  }
});
