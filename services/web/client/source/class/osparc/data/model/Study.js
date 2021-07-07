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
      uuid: studyData.uuid || this.getUuid(),
      name: studyData.name || this.getName(),
      description: studyData.description || this.getDescription(),
      thumbnail: studyData.thumbnail || this.getThumbnail(),
      prjOwner: studyData.prjOwner || this.getPrjOwner(),
      accessRights: studyData.accessRights || this.getAccessRights(),
      creationDate: studyData.creationDate ? new Date(studyData.creationDate) : this.getCreationDate(),
      lastChangeDate: studyData.lastChangeDate ? new Date(studyData.lastChangeDate) : this.getLastChangeDate(),
      classifiers: studyData.classifiers || this.getClassifiers(),
      tags: studyData.tags || this.getTags(),
      state: studyData.state || this.getState(),
      quality: studyData.quality || this.getQuality()
    });

    const wbData = studyData.workbench || this.getWorkbench();
    this.setWorkbench(new osparc.data.model.Workbench(wbData, studyData.ui));
    this.setUi(new osparc.data.model.StudyUI(studyData.ui));

    this.setSweeper(new osparc.data.model.Sweeper(studyData));
  },

  properties: {
    uuid: {
      check: "String",
      nullable: false,
      event: "changeUuid",
      init: ""
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
      apply: "__applyAccessRights",
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

    thumbnail: {
      check: "String",
      nullable: false,
      event: "changeThumbnail",
      init: ""
    },

    workbench: {
      check: "osparc.data.model.Workbench",
      nullable: false,
      init: {}
    },

    ui: {
      check: "osparc.data.model.StudyUI",
      nullable: true
    },

    tags: {
      check: "Array",
      init: [],
      event: "changeTags",
      nullable: true
    },

    classifiers: {
      check: "Array",
      init: [],
      event: "changeClassifiers",
      nullable: true
    },

    sweeper: {
      check: "osparc.data.model.Sweeper",
      nullable: true
    },

    state: {
      check: "Object",
      nullable: true,
      event: "changeState"
    },

    quality: {
      check: "Object",
      init: {},
      event: "changeQuality",
      nullable: true
    },

    readOnly: {
      check: "Boolean",
      nullable: true,
      event: "changeReadOnly",
      init: true
    }
  },

  events: {
    "changeParameters": "qx.event.type.Event"
  },

  statics: {
    createMyNewStudyObject: function() {
      let myNewStudyObject = {};
      const props = qx.util.PropertyUtil.getProperties(osparc.data.model.Study);
      for (let key in props) {
        const prop = props[key];
        if (!prop.nullable) {
          if (typeof prop.init === "object") {
            myNewStudyObject[key] = osparc.utils.Utils.deepCloneObject(prop.init);
          } else {
            myNewStudyObject[key] = prop.init;
          }
        }
      }
      return myNewStudyObject;
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
      return osparc.component.permissions.Study.canGroupDelete(aceessRights, myGid);
    },

    hasSlideshow: function(studyData) {
      if ("ui" in studyData && "slideshow" in studyData["ui"] && Object.keys(studyData["ui"]["slideshow"]).length) {
        return true;
      }
      return false;
    }
  },

  members: {
    initStudy: function() {
      this.getWorkbench().initWorkbench();
    },

    buildWorkbench: function() {
      this.getWorkbench().buildWorkbench();
    },

    isSnapshot: function() {
      const primaryStudyId = this.getSweeper().getPrimaryStudyId();
      return primaryStudyId !== null;
    },

    __applyAccessRights: function(value) {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const orgIDs = osparc.auth.Data.getInstance().getOrgIds();
      orgIDs.push(myGid);

      if (myGid) {
        const canIWrite = osparc.component.permissions.Study.canGroupsWrite(value, orgIDs);
        this.setReadOnly(!canIWrite);
      } else {
        this.setReadOnly(true);
      }
    },

    openStudy: function() {
      const params = {
        url: {
          "studyId": this.getUuid()
        },
        data: osparc.utils.Utils.getClientSessionID()
      };
      return osparc.data.Resources.fetch("studies", "open", params);
    },

    stopStudy: function() {
      this.removeIFrames();
    },

    removeIFrames: function() {
      const nodes = this.getWorkbench().getNodes(true);
      for (const node of Object.values(nodes)) {
        node.removeIFrame();
      }
    },

    getParameters: function() {
      const parameters = [];
      const nodes = this.getWorkbench().getNodes(true);
      Object.values(nodes).forEach(node => {
        if (node.isParameter()) {
          parameters.push(node);
        }
      });
      return parameters;
    },

    getIterators: function() {
      const iterators = [];
      const nodes = this.getWorkbench().getNodes(true);
      Object.values(nodes).forEach(node => {
        if (node.isIterator()) {
          iterators.push(node);
        }
      });
      return iterators;
    },

    serialize: function() {
      let jsonObject = {};
      const propertyKeys = this.self().getProperties();
      propertyKeys.forEach(key => {
        if (["state", "readOnly"].includes(key)) {
          return;
        }
        if (key === "workbench") {
          jsonObject[key] = this.getWorkbench().serialize();
          return;
        }
        if (key === "ui") {
          jsonObject[key] = this.getUi().serialize();
          return;
        }
        if (key === "sweeper") {
          jsonObject["dev"] = {};
          jsonObject["dev"]["sweeper"] = this.getSweeper().serialize();
          return;
        }
        const value = this.get(key);
        if (value !== null) {
          // only put the value in the payload if there is a value
          jsonObject[key] = value;
        }
      });
      return jsonObject;
    },

    updateStudy: function(params, run = false) {
      return new Promise(resolve => {
        osparc.data.Resources.fetch("studies", "put", {
          url: {
            "studyId": this.getUuid(),
            run
          },
          data: {
            ...this.serialize(),
            ...params
          }
        }).then(data => {
          this.__updateModel(data);
          qx.event.message.Bus.getInstance().dispatchByName("updateStudy", data);
          resolve(data);
        });
      });
    },

    __updateModel: function(data) {
      if ("dev" in data) {
        delete data["dev"];
      }
      this.set({
        ...data,
        creationDate: new Date(data.creationDate),
        lastChangeDate: new Date(data.lastChangeDate),
        workbench: this.getWorkbench(),
        ui: this.getUi(),
        sweeper: this.getSweeper()
      });

      const nodes = this.getWorkbench().getNodes(true);
      Object.values(nodes).forEach(node => {
        const nodeId = node.getNodeId();
        if (nodeId in data.workbench) {
          node.populateStates(data.workbench[nodeId]);
        }
      });
    }
  }
});
