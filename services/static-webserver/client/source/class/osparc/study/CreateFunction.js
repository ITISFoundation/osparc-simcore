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

  statics: {
    createFunctionData: function(projectData, name, description, defaultInputs = {}, exposedInputs = {}, exposedOutputs = {}) {
      const functionData = {
        "projectId": projectData["uuid"],
        "title": name,
        "description": description,
        "function_class": "PROJECT",
        "inputSchema": {
          "schema_class": "application/schema+json",
          "schema_content": {
            "type": "object",
            "properties": {},
            "required": []
          }
        },
        "outputSchema": {
          "schema_class": "application/schema+json",
          "schema_content": {
            "type": "object",
            "properties": {},
            "required": []
          }
        },
        "defaultInputs": {},
      };

      const parameters = osparc.study.Utils.extractFunctionableParameters(projectData["workbench"]);
      parameters.forEach(parameter => {
        const parameterKey = parameter["label"];
        if (exposedInputs[parameterKey]) {
          const parameterMetadata = osparc.store.Services.getMetadata(parameter["key"], parameter["version"]);
          if (parameterMetadata) {
            const type = osparc.service.Utils.getParameterType(parameterMetadata);
            functionData["inputSchema"]["schema_content"]["properties"][parameterKey] = {
              "type": type,
            };
            functionData["inputSchema"]["schema_content"]["required"].push(parameterKey);
          }
        }
        if (parameterKey in defaultInputs) {
          functionData["defaultInputs"][parameterKey] = defaultInputs[parameterKey];
        }
      });

      const probes = osparc.study.Utils.extractFunctionableProbes(projectData["workbench"]);
      probes.forEach(probe => {
        const probeLabel = probe["label"];
        if (exposedOutputs[probeLabel]) {
          const probeMetadata = osparc.store.Services.getMetadata(probe["key"], probe["version"]);
          if (probeMetadata) {
            const type = osparc.service.Utils.getProbeType(probeMetadata);
            functionData["outputSchema"]["schema_content"]["properties"][probeLabel] = {
              "type": type,
            };
            functionData["outputSchema"]["schema_content"]["required"].push(probeLabel);
          }
        }
      });

      return functionData;
    }
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
        value: this.__studyData.description || ""
      });
      form.add(description, this.tr("Description"), null, "description");


      const defaultInputs = {};
      const exposedInputs = {};
      const exposedOutputs = {};

      // INPUTS
      const inGrid = new qx.ui.layout.Grid(12, 6);
      const inputsLayout = new qx.ui.container.Composite(inGrid).set({
        allowGrowX: false,
        alignX: "left",
        alignY: "middle"
      });
      this._add(inputsLayout);

      // header
      let row = 0;
      let column = 0;
      const nameLabel = new qx.ui.basic.Label(this.tr("Input"));
      inputsLayout.add(nameLabel, {
        row,
        column,
      });
      column++;
      const typeLabel = new qx.ui.basic.Label(this.tr("Type"));
      inputsLayout.add(typeLabel, {
        row,
        column,
      });
      column++;
      const exposedLabel = new qx.ui.basic.Label(this.tr("Exposed"));
      inputsLayout.add(exposedLabel, {
        row,
        column,
      });
      column++;
      const defaultValue = new qx.ui.basic.Label(this.tr("Default value"));
      inputsLayout.add(defaultValue, {
        row,
        column,
      });
      column = 0;
      row++;

      const parameters = osparc.study.Utils.extractFunctionableParameters(this.__studyData["workbench"]);
      parameters.forEach(parameter => {
        const parameterKey = parameter["label"];
        const parameterLabel = new qx.ui.basic.Label(parameterKey);
        inputsLayout.add(parameterLabel, {
          row,
          column,
        });
        column++;

        const parameterMetadata = osparc.store.Services.getMetadata(parameter["key"], parameter["version"]);
        if (parameterMetadata) {
          const parameterType = new qx.ui.basic.Label(osparc.service.Utils.getParameterType(parameterMetadata));
          inputsLayout.add(parameterType, {
            row,
            column,
          });
        }
        column++;

        const parameterExposed = new qx.ui.form.CheckBox().set({ value: true });
        inputsLayout.add(parameterExposed, {
          row,
          column,
        });
        exposedInputs[parameterKey] = true;
        parameterExposed.addListener("changeValue", e => exposedInputs[parameterKey] = e.getData());
        column++;

        const paramValue = osparc.service.Utils.getParameterValue(parameter);
        defaultInputs[parameterKey] = paramValue;
        let parameterDefaultValue = null;
        if (parameterMetadata && osparc.service.Utils.getParameterType(parameterMetadata) === "number") {
          parameterDefaultValue = new qx.ui.form.TextField(String(paramValue));
          parameterDefaultValue.addListener("changeValue", e => {
            const newValue = e.getData();
            const oldValue = e.getOldData();
            if (newValue === oldValue) {
              return;
            }
            const curatedValue = (!isNaN(parseFloat(newValue))) ? parseFloat(newValue) : parseFloat(oldValue);
            defaultInputs[parameterKey] = curatedValue;
            parameterDefaultValue.setValue(String(curatedValue));
          });
        } else {
          parameterDefaultValue = new qx.ui.basic.Label(String(paramValue));
        }
        inputsLayout.add(parameterDefaultValue, {
          row,
          column,
        });
        column++;

        column = 0;
        row++;
      });


      // OUTPUTS
      const outGrid = new qx.ui.layout.Grid(10, 6);
      const outputsLayout = new qx.ui.container.Composite(outGrid).set({
        allowGrowX: false,
        alignX: "left",
        alignY: "middle"
      });
      this._add(outputsLayout);

      // header
      row = 0;
      column = 0;
      const nameLabel2 = new qx.ui.basic.Label(this.tr("Output"));
      outputsLayout.add(nameLabel2, {
        row,
        column,
      });
      column++;
      const typeLabel2 = new qx.ui.basic.Label(this.tr("Type"));
      outputsLayout.add(typeLabel2, {
        row,
        column,
      });
      column++;
      const exposedLabel2 = new qx.ui.basic.Label(this.tr("Exposed"));
      outputsLayout.add(exposedLabel2, {
        row,
        column,
      });
      column++;
      column = 0;
      row++;

      const probes = osparc.study.Utils.extractFunctionableProbes(this.__studyData["workbench"]);
      probes.forEach(probe => {
        const parameterLabel = new qx.ui.basic.Label(probe["label"]);
        outputsLayout.add(parameterLabel, {
          row,
          column,
        });
        column++;

        const probeMetadata = osparc.store.Services.getMetadata(probe["key"], probe["version"]);
        if (probeMetadata) {
          const probeType = new qx.ui.basic.Label(osparc.service.Utils.getProbeType(probeMetadata));
          outputsLayout.add(probeType, {
            row,
            column,
          });
        }
        column++;

        const probeExposed = new qx.ui.form.CheckBox().set({ value: true });
        outputsLayout.add(probeExposed, {
          row,
          column,
        });
        exposedOutputs[probe["label"]] = true;
        probeExposed.addListener("changeValue", e => exposedOutputs[probe["label"]] = e.getData());
        column++;

        column = 0;
        row++;
      });

      const createFunctionBtn = this.__createFunctionBtn = new osparc.ui.form.FetchButton().set({
        appearance: "strong-button",
        label: this.tr("Create"),
        allowGrowX: false,
        alignX: "right"
      });
      createFunctionBtn.addListener("execute", () => {
        if (this.__form.validate()) {
          this.__createFunction(defaultInputs, exposedInputs, exposedOutputs);
        }
      }, this);
    },

    __createFunction: function(defaultInputs, exposedInputs, exposedOutputs) {
      this.__createFunctionBtn.setFetching(true);

      // first publish it as a hidden template
      const params = {
        url: {
          "study_id": this.__studyData["uuid"],
          "copy_data": true,
          "hidden": true,
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
            this.__updateTemplateMetadata(templateData);
            this.__registerFunction(templateData, defaultInputs, exposedInputs, exposedOutputs);
          });
        })
        .catch(err => {
          this.__createFunctionBtn.setFetching(false);
          osparc.FlashMessenger.logError(err);
        });
    },

    __updateTemplateMetadata: function(templateData) {
      const metadata = {
        "custom" : {
          "hidden": "Base template for function",
        }
      };
      osparc.store.Study.getInstance().updateMetadata(templateData["uuid"], metadata)
        .catch(err => console.error(err));
    },

    __registerFunction: function(templateData, defaultInputs, exposedInputs, exposedOutputs) {
      const nameField = this.__form.getItem("name");
      const descriptionField = this.__form.getItem("description");

      const functionData = this.self().createFunctionData(templateData, nameField.getValue(), descriptionField.getValue(), defaultInputs, exposedInputs, exposedOutputs);
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
