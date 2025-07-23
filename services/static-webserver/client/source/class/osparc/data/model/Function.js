/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Class that stores Function data.
 */

qx.Class.define("osparc.data.model.Function", {
  extend: qx.core.Object,

  /**
   * @param functionData {Object} Object containing the serialized Function Data
   * @param templateData {Object} Object containing the underlying serialized Template Data
   */
  construct: function(functionData, templateData = null) {
    this.base(arguments);

    this.set({
      uuid: functionData.uuid,
      functionClass: functionData.functionClass,
      title: functionData.title,
      description: functionData.description,
      inputSchema: functionData.inputSchema || this.getInputSchema(),
      outputSchema: functionData.outputSchema || this.getOutputSchema(),
      defaultInputs: functionData.defaultInputs || this.getDefaultInputs(),
      accessRights: functionData.accessRights || this.getAccessRights(),
      creationDate: functionData.creationDate ? new Date(functionData.creationDate) : this.getCreationDate(),
      lastChangeDate: functionData.lastChangeDate ? new Date(functionData.lastChangeDate) : this.getLastChangeDate(),
      thumbnail: functionData.thumbnail || this.getThumbnail(),
      templateId: functionData.templateId || this.getTemplateId(),
    });

    if (templateData) {
      const template = new osparc.data.model.Study(templateData);
      this.setTemplate(template);
    }
  },

  properties: {
    uuid: {
      check: "String",
      nullable: false,
      event: "changeUuid",
      init: ""
    },

    functionClass: {
      check: [
        "PROJECT",     // osparc.data.model.Function.FUNCTION_CLASS.PROJECT
        "SOLVER",      // osparc.data.model.Function.FUNCTION_CLASS.SOLVER
        "PYTHON_CODE", // osparc.data.model.Function.FUNCTION_CLASS.PYTHON
      ],
      nullable: false,
      event: "changeFunctionClass",
      init: null
    },

    title: {
      check: "String",
      nullable: false,
      event: "changeTitle",
      init: "Function"
    },

    description: {
      check: "String",
      nullable: true,
      event: "changeDescription",
      init: null
    },

    inputSchema: {
      check: "Object",
      nullable: false,
      event: "changeInputSchema",
      init: {}
    },

    outputSchema: {
      check: "Object",
      nullable: false,
      event: "changeOutputSchema",
      init: {}
    },

    defaultInputs: {
      check: "Object",
      nullable: false,
      event: "changeDefaultInputs",
      init: {}
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

    thumbnail: {
      check: "String",
      nullable: true,
      event: "changeThumbnail",
      init: null
    },

    templateId: {
      check: "String",
      nullable: true,
      init: null,
    },

    template: {
      check: "osparc.data.model.Study",
      nullable: true,
      init: null,
    },
  },

  statics: {
    FUNCTION_CLASS: {
      PROJECT: "PROJECT",
      SOLVER: "SOLVER",
      PYTHON_CODE: "PYTHON_CODE"
    },

    getProperties: function() {
      return Object.keys(qx.util.PropertyUtil.getProperties(osparc.data.model.Function));
    },
  },

  members: {
    serialize: function() {
      let jsonObject = {};
      const propertyKeys = this.self().getProperties();
      propertyKeys.forEach(key => {
        if (key === "template") {
          return; // template is not serialized
        }
        jsonObject[key] = this.get(key);
      });
      return jsonObject;
    },

    canIWrite: function() {
      return Boolean(this.getAccessRights()["write"]);
    },

    patchFunction: function(functionChanges) {
      return osparc.store.Functions.patchFunction(this.getUuid(), functionChanges)
        .then(functionData => {
          Object.keys(functionChanges).forEach(fieldKey => {
            const upKey = qx.lang.String.firstUp(fieldKey);
            const setter = "set" + upKey;
            this[setter](functionChanges[fieldKey]);
          });
          this.set({
            lastChangeDate: new Date(functionData.lastChangeDate)
          });
          return functionData;
        });
    },
  }
});
