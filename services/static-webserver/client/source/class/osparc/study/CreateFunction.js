/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.study.CreateFunction", {
  extend: qx.ui.core.Widget,

  /**
   * @param studyData {Object} Object containing part or the entire serialized Study Data
   */
  construct: function(studyData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(20));

    this.__studyData = studyData;

    this.__buildLayout();
  },

  members: {
    __studyData: null,
    __form: null,
    __createFunctionBtn: null,

    __buildLayout: function() {
      const form = this.__form = new qx.ui.form.Form();
      this._add(new qx.ui.form.renderer.Single(form));

      const title = new qx.ui.form.TextField().set({
        required: true,
        value: this.__studyData.name,
      });
      this.addListener("appear", () => {
        title.focus();
        title.activate();
      });
      form.add(title, this.tr("Name"), null, "name");

      const description = new qx.ui.form.TextField().set({
        required: false,
      });
      form.add(description, this.tr("Description"), null, "description");

      const createFunctionBtn = this.__createFunctionBtn = new osparc.ui.form.FetchButton().set({
        appearance: "strong-button",
        label: this.tr("Create"),
        allowGrowX: false,
        alignX: "right"
      });
      createFunctionBtn.addListener("execute", () => {
        if (this.__form.validate()) {
          this.__createFunction();
        }
      }, this);
      this._add(createFunctionBtn);
    },

    __createFunction: function() {
      this.__createFunctionBtn.setFetching(true);

      // first publish it as a template
      const params = {
        url: {
          "study_id": this.__studyData["uuid"],
          "copy_data": true,
        },
      };
      const options = {
        pollTask: true
      };
      const fetchPromise = osparc.data.Resources.fetch("studies", "postToTemplate", params, options);
      const pollTasks = osparc.store.PollTasks.getInstance();
      pollTasks.createPollingTask(fetchPromise)
        .then(task => {
          task.addListener("resultReceived", e => {
            const templateData = e.getData();
            this.__doCreateFunction(templateData);
          });
        })
        .catch(err => {
          this.__createFunctionBtn.setFetching(false);
          osparc.FlashMessenger.logError(err);
        });
    },

    __doCreateFunction: function(templateData) {
      const nameField = this.__form.getItem("name");
      const descriptionField = this.__form.getItem("description");

      const functionData = {
        "name": nameField.getValue(),
        "description": descriptionField.getValue(),
        "project_id": templateData["uuid"],
        "function_class": "project",
        "input_schema": {
          "schema_dict": {
            "type": "object",
            "properties": {}
          }
        },
        "output_schema": {
          "schema_dict": {
            "type": "object",
            "properties": {}
          }
        },
        "default_inputs": {},
      };

      const filePickers = osparc.study.Utils.extractFilePickers(templateData["workbench"]);
      filePickers.forEach(filePicker => {
        const fpName = filePicker["name"];
        functionData["input_schema"]["schema_dict"]["properties"][fpName] = {
          "type": "FileID",
        };
        functionData["default_inputs"][fpName] = "asdfasdf";
      });

      const parameters = osparc.study.Utils.extractParameters(templateData["workbench"]);
      parameters.forEach(parameter => {
        const parameterName = parameter["name"];
        const parameterMetadata = osparc.store.Services.getMetadata(parameter["key"], parameter["version"]);
        if (parameterMetadata) {
          functionData["input_schema"]["schema_dict"]["properties"][parameterName] = {
            "type": osparc.service.Utils.getParameterType(parameterMetadata),
          };
        }
        functionData["default_inputs"][parameterName] = parameter["outputs"]["out_1"];
      });

      const probes = osparc.study.Utils.extractProbes(templateData["workbench"]);
      probes.forEach(probe => {
        const probeName = probe["name"];
        const probeMetadata = osparc.store.Services.getMetadata(probe["key"], probe["version"]);
        if (probeMetadata) {
          functionData["output_schema"]["schema_dict"]["properties"][probeName] = {
            "type": osparc.service.Utils.getProbeType(probeMetadata),
          };
        }
      });

      console.log("functionData", functionData);

      const params = {
        data: functionData,
      };
      osparc.data.Resources.fetch("functions", "create", params)
        .then(() => osparc.FlashMessenger.logAs(this.tr("Function created"), "INFO"))
        .catch(err => osparc.FlashMessenger.logError(err))
        .finally(() => this.__createFunctionBtn.setFetching(false));
    },

    getCreateFunctionButton: function() {
      return this.__createFunctionBtn;
    }
  }
});
