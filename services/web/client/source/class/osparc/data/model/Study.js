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
 *   let study = new osparc.data.model.Study(studyData);
 *   let prjEditor = new osparc.desktop.StudyEditor(study);
 * </pre>
 */

qx.Class.define("osparc.data.model.Study", {
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
      thumbnail: studyData.thumbnail === undefined ? this.getThumbnail() : studyData.thumbnail,
      prjOwner: studyData.prjOwner === undefined ? osparc.auth.Data.getInstance().getUserName() : studyData.prjOwner,
      creationDate: studyData.creationDate === undefined ? this.getCreationDate() : new Date(studyData.creationDate),
      lastChangeDate: studyData.lastChangeDate === undefined ? this.getLastChangeDate() : new Date(studyData.lastChangeDate)
    });

    const wbData = studyData.workbench === undefined ? {} : studyData.workbench;
    this.setWorkbench(new osparc.data.model.Workbench(wbData));
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
        creationDate: new Date(),
        lastChangeDate: new Date(),
        workbench: {}
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
        data: sessionStorage.getItem("clientsessionid")
      };
      osparc.data.Resources.fetch("studies", "open", params)
        .then(data => this.getWorkbench().initWorkbench())
        .catch(err => console.error(err));
    },

    closeStudy: function() {
      const params = {
        url: {
          projectId: this.getUuid()
        },
        data: sessionStorage.getItem("clientsessionid")
      };
      osparc.data.Resources.fetch("studies", "close", params)
        .catch(err => console.error(err));

      // remove iFrames
      const nodes = this.getWorkbench().getNodes(true);
      for (const node of Object.values(nodes)) {
        node.removeIFrame();
      }
    },

    serializeStudy: function() {
      let jsonObject = {};
      const properties = this.constructor.$$properties;
      for (let key in properties) {
        const value = key === "workbench" ? this.getWorkbench().serializeWorkbench() : this.get(key);
        if (value !== null) {
          // only put the value in the payload if there is a value
          jsonObject[key] = value;
        }
      }
      return jsonObject;
    },

    updateStudy: function(params) {
      return this.self().updateStudy({
        ...this.serializeStudy(),
        ...params
      })
        .then(data => {
          this.set({
            ...data,
            creationDate: new Date(data.creationDate),
            lastChangeDate: new Date(data.lastChangeDate),
            workbench: this.getWorkbench()
          });
          // this.setWorkbench(new osparc.data.model.Workbench(data.workbench));
          return data;
        });
    }
  }
});
