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


      const exposedInputs = {};
      const exposedOutputs = {};

      // INPUTS
      const inGrid = new qx.ui.layout.Grid(10, 6);
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

      const filePickers = osparc.study.Utils.extractFilePickers(this.__studyData["workbench"]);
      filePickers.forEach(filePicker => {
        const fpLabel = new qx.ui.basic.Label(filePicker["label"]);
        inputsLayout.add(fpLabel, {
          row,
          column,
        });
        column++;

        const fpType = new qx.ui.basic.Label("FileID");
        inputsLayout.add(fpType, {
          row,
          column,
        });
        column++;

        const fpExposed = new qx.ui.form.CheckBox().set({ value: true });
        inputsLayout.add(fpExposed, {
          row,
          column,
        });
        exposedInputs[filePicker["label"]] = true;
        fpExposed.addListener("changeValue", e => exposedInputs[filePicker["label"]] = e.getData());
        column++;

        const outputValue = osparc.file.FilePicker.getOutput(filePicker);
        const fpDefaultValue = new qx.ui.basic.Label(outputValue && outputValue["path"] ? outputValue["path"] : "");
        inputsLayout.add(fpDefaultValue, {
          row,
          column,
        });
        column++;

        column = 0;
        row++;
      });

      const parameters = osparc.study.Utils.extractParameters(this.__studyData["workbench"]);
      parameters.forEach(parameter => {
        const parameterLabel = new qx.ui.basic.Label(parameter["label"]);
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
        exposedInputs[parameter["label"]] = true;
        parameterExposed.addListener("changeValue", e => exposedInputs[parameter["label"]] = e.getData());
        column++;

        const parameterDefaultValue = new qx.ui.basic.Label(String(osparc.service.Utils.getParameterValue(parameter)));
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

      const probes = osparc.study.Utils.extractProbes(this.__studyData["workbench"]);
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
          this.__createFunction(exposedInputs, exposedOutputs);
        }
      }, this);
    },

    __createFunction: function(exposedInputs, exposedOutputs) {
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
            this.__doCreateFunction(templateData, exposedInputs, exposedOutputs);
          });
        })
        .catch(err => {
          this.__createFunctionBtn.setFetching(false);
          osparc.FlashMessenger.logError(err);
        });
    },

    __doCreateFunction: function(templateData, exposedInputs, exposedOutputs) {
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
        const fpLabel = filePicker["label"];
        if (exposedInputs[fpLabel]) {
          functionData["input_schema"]["schema_dict"]["properties"][fpLabel] = {
            "type": "FileID",
          };
          const outputValue = osparc.file.FilePicker.getOutput(filePicker);
          functionData["default_inputs"][fpLabel] = outputValue && outputValue["path"] ? outputValue["path"] : null;
        }
      });

      const parameters = osparc.study.Utils.extractParameters(templateData["workbench"]);
      parameters.forEach(parameter => {
        const parameterLabel = parameter["label"];
        if (exposedInputs[parameterLabel]) {
          const parameterMetadata = osparc.store.Services.getMetadata(parameter["key"], parameter["version"]);
          if (parameterMetadata) {
            functionData["input_schema"]["schema_dict"]["properties"][parameterLabel] = {
              "type": osparc.service.Utils.getParameterType(parameterMetadata),
            };
          }
          functionData["default_inputs"][parameterLabel] = osparc.service.Utils.getParameterValue(parameter);
        }
      });

      const probes = osparc.study.Utils.extractProbes(templateData["workbench"]);
      probes.forEach(probe => {
        const probeLabel = probe["label"];
        if (exposedOutputs[probeLabel]) {
          const probeMetadata = osparc.store.Services.getMetadata(probe["key"], probe["version"]);
          if (probeMetadata) {
            functionData["output_schema"]["schema_dict"]["properties"][probeLabel] = {
              "type": osparc.service.Utils.getProbeType(probeMetadata),
            };
          }
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
