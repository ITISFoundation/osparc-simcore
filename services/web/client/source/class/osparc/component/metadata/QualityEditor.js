/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * @asset(form/resource-quality.json)
 * @asset(object-path/object-path-0-11-4.min.js)
 * @asset(ajv/ajv-6-11-0.min.js)
 * @ignore(Ajv)
 */

qx.Class.define("osparc.component.metadata.QualityEditor", {
  extend: qx.ui.core.Widget,

  /**
    * @param resourceData {Object} Object containing the Resource Data
    */
  construct: function(resourceData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    this.__initResourceData(resourceData);
  },

  events: {
    "updateStudy": "qx.event.type.Data",
    "updateTemplate": "qx.event.type.Data",
    "updateService": "qx.event.type.Data"
  },

  properties: {
    mode: {
      check: ["display", "edit"],
      init: "display",
      nullable: false,
      event: "changeMode",
      apply: "__populateForms"
    }
  },

  members: {
    __resourceData: null,
    __copyResourceData: null,
    __schema: null,
    __tsrGrid: null,
    __annotationsGrid: null,

    __initResourceData: function(resourceData) {
      if (!("quality" in resourceData)) {
        osparc.component.message.FlashMessenger.logAs(this.tr("Quality Assessment data not found"), "ERROR");
        return;
      }

      this.__resourceData = resourceData;
      if (!("tsr" in resourceData["quality"])) {
        resourceData["quality"]["tsr"] = osparc.component.metadata.Quality.getDefaultQualityTSR();
      }
      if (!("annotations" in resourceData["quality"])) {
        resourceData["quality"]["annotations"] = osparc.component.metadata.Quality.getDefaultQualityAnnotations();
      }
      this.__copyResourceData = osparc.utils.Resources.isService(resourceData) ? osparc.utils.Utils.deepCloneObject(resourceData) : osparc.data.model.Study.deepCloneStudyObject(resourceData);

      const schemaUrl = "/resource/form/resource-quality.json";
      const data = resourceData["quality"];
      const ajvLoader = new qx.util.DynamicScriptLoader([
        "/resource/ajv/ajv-6-11-0.min.js",
        "/resource/object-path/object-path-0-11-4.min.js"
      ]);
      ajvLoader.addListener("ready", () => {
        this.__ajv = new Ajv();
        osparc.utils.Utils.fetchJSON(schemaUrl)
          .then(schema => {
            if (this.__validate(schema.$schema, schema)) {
              // If schema is valid
              if (this.__validate(schema, data)) {
                // Validate data if present
                this.__resourceData = resourceData;
              }
              return schema;
            }
            return null;
          })
          .then(schema => {
            this.__render(schema);
            this.setMode("display");
          })
          .catch(err => {
            console.error(err);
            this.__render(null);
          });
      }, this);
      ajvLoader.addListener("failed", console.error, this);
      this.__render = this.__render.bind(this);
      ajvLoader.start();
    },

    /**
     * Uses Ajv library to validate data against a schema.
     *
     * @param {Object} schema JSONSchema to validate against
     * @param {Object} data Data to be validated
     * @param {Boolean} showMessage Determines whether an error message is displayed to the user
     */
    __validate: function(schema, data, showMessage=true) {
      this.__ajv.validate(schema, data);
      const errors = this.__ajv.errors;
      if (errors) {
        console.error(errors);
        if (showMessage) {
          let message = `${errors[0].dataPath} ${errors[0].message}`;
          osparc.component.message.FlashMessenger.logAs(message, "ERROR");
        }
        return false;
      }
      return true;
    },

    __render: function(schema) {
      if (schema) {
        this._removeAll();

        this.__schema = schema;
        this.__createTSRSection();
        this.__createAnnotationsSection();

        if (this.__isUserOwner()) {
          this.__createEditBtns();
        }

        this.__populateForms();
      } else {
        osparc.component.message.FlashMessenger.logAs(this.tr("There was an error validating the metadata."), "ERROR");
      }
    },

    __populateForms: function() {
      this.__populateTSR();
      this.__populateAnnotations();
    },

    __createTSRSection: function() {
      const box = new qx.ui.groupbox.GroupBox(this.tr("Ten Simple Rules"));
      box.getChildControl("legend").set({
        font: "title-14"
      });
      box.getChildControl("frame").set({
        backgroundColor: "transparent"
      });
      box.setLayout(new qx.ui.layout.VBox(10));

      const helpText = "[10 Simple Rules with Conformance Rubric](https://www.imagwiki.nibib.nih.gov/content/10-simple-rules-conformance-rubric)";
      const helpTextMD = new osparc.ui.markdown.Markdown(helpText);
      box.add(helpTextMD);

      const grid = new qx.ui.layout.Grid(10, 8);
      grid.setColumnAlign(0, "left", "middle");
      grid.setColumnAlign(1, "left", "middle");
      grid.setColumnAlign(2, "left", "middle");
      grid.setColumnAlign(3, "left", "middle");
      grid.setColumnFlex(2, 1);
      this.__tsrGrid = new qx.ui.container.Composite(grid);
      box.add(this.__tsrGrid, {
        flex: 1
      });

      this._add(box, {
        flex: 1
      });
    },

    __createAnnotationsSection: function() {
      const box = new qx.ui.groupbox.GroupBox(this.tr("Annotations"));
      box.getChildControl("legend").set({
        font: "title-14"
      });
      box.getChildControl("frame").set({
        backgroundColor: "transparent"
      });
      box.setLayout(new qx.ui.layout.VBox(10));

      const grid = new qx.ui.layout.Grid(10, 8);
      grid.setColumnAlign(0, "left", "middle");
      grid.setColumnAlign(1, "left", "middle");
      grid.setColumnAlign(2, "left", "middle");
      grid.setColumnFlex(1, 1);
      this.__annotationsGrid = new qx.ui.container.Composite(grid);
      box.add(this.__annotationsGrid);

      this._add(box);
    },

    __populateTSR: function() {
      this.__tsrGrid.removeAll();
      this.__populateTSRHeaders();
      this.__populateTSRData();
    },

    __populateTSRHeaders: function() {
      const schemaRules = this.__schema["properties"]["tsr"]["properties"];

      const headerTSR = new qx.ui.basic.Label(this.tr("Rules")).set({
        font: "title-14"
      });
      this.__tsrGrid.add(headerTSR, {
        row: 0,
        column: 0
      });
      const headerCL = new qx.ui.basic.Label(this.tr("Conformance Level")).set({
        font: "title-14"
      });
      this.__tsrGrid.add(headerCL, {
        row: 0,
        column: 1
      });
      const headerRef = new qx.ui.basic.Label(this.tr("References")).set({
        font: "title-14"
      });
      this.__tsrGrid.add(headerRef, {
        row: 0,
        column: 2
      });

      let row = 1;
      Object.values(schemaRules).forEach(rule => {
        const label = new qx.ui.basic.Label(rule.title).set({
          marginTop: 5
        });
        const ruleWHint = new osparc.component.form.FieldWHint(null, rule.description, label).set({
          allowGrowX: false
        });
        this.__tsrGrid.add(ruleWHint, {
          row,
          column: 0
        });
        row++;
      });
      const label = new qx.ui.basic.Label("TSR score").set({
        font: "title-13"
      });
      this.__tsrGrid.add(label, {
        row,
        column: 0
      });
      row++;
    },

    __populateTSRData: function() {
      switch (this.getMode()) {
        case "edit":
          this.__populateTSRDataEdit();
          break;
        default:
          this.__populateTSRDataView();
          break;
      }
    },

    __populateTSRDataView: function() {
      const metadataTSR = this.__resourceData["quality"]["tsr"];
      let row = 1;
      Object.values(metadataTSR).forEach(rule => {
        const ruleRating = new osparc.ui.basic.StarsRating();
        ruleRating.set({
          score: rule.level,
          maxScore: 4,
          nStars: 4,
          marginTop: 5
        });
        const confLevel = osparc.component.metadata.Quality.findConformanceLevel(rule.level);
        const hint = confLevel.title + "<br>" + confLevel.description;
        const ruleRatingWHint = new osparc.component.form.FieldWHint(null, hint, ruleRating).set({
          hintPosition: "left"
        });
        this.__tsrGrid.add(ruleRatingWHint, {
          row,
          column: 1
        });

        const referenceMD = new osparc.ui.markdown.Markdown(rule.references);
        this.__tsrGrid.add(referenceMD, {
          row,
          column: 2
        });

        row++;
      });
      const {
        score,
        maxScore
      } = osparc.component.metadata.Quality.computeTSRScore(metadataTSR);
      const tsrRating = new osparc.ui.basic.StarsRating();
      tsrRating.set({
        score,
        maxScore,
        nStars: 4,
        showScore: true,
        marginTop: 5
      });
      this.__tsrGrid.add(tsrRating, {
        row,
        column: 1
      });
    },

    __populateTSRDataEdit: function() {
      const copyMetadataTSR = this.__copyResourceData["quality"]["tsr"];
      const tsrRating = new osparc.ui.basic.StarsRating();
      tsrRating.set({
        nStars: 4,
        showScore: true,
        marginTop: 5,
        mode: "edit"
      });
      const updateTSRScore = () => {
        const {
          score,
          maxScore
        } = osparc.component.metadata.Quality.computeTSRScore(copyMetadataTSR);

        tsrRating.set({
          score,
          maxScore
        });
      };
      updateTSRScore();

      let row = 1;
      Object.keys(copyMetadataTSR).forEach(ruleKey => {
        const rule = copyMetadataTSR[ruleKey];
        const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
          alignY: "middle"
        }));

        const updateLevel = value => {
          layout.removeAll();
          const ruleRating = new osparc.ui.basic.StarsRating();
          ruleRating.set({
            maxScore: 4,
            nStars: 4,
            score: value,
            marginTop: 5,
            mode: "edit"
          });
          ruleRating.addListener("changeScore", e => {
            rule.level = e.getData();
            updateLevel(rule.level);
            updateTSRScore();
          }, this);
          const confLevel = osparc.component.metadata.Quality.findConformanceLevel(value);
          const hint = confLevel.title + "<br>" + confLevel.description;
          const ruleRatingWHint = new osparc.component.form.FieldWHint(null, hint, ruleRating).set({
            hintPosition: "left"
          });
          layout.add(ruleRatingWHint);
        };

        updateLevel(rule.level);

        this.__tsrGrid.add(layout, {
          row,
          column: 1
        });

        const referenceMD = new osparc.ui.markdown.Markdown(rule.references);
        this.__tsrGrid.add(referenceMD, {
          row,
          column: 2
        });

        const button = osparc.utils.Utils.getEditButton();
        button.addListener("execute", () => {
          const title = this.tr("Edit References");
          const subtitle = this.tr("Supports Markdown");
          const textEditor = new osparc.component.widget.TextEditor(rule.references, subtitle, title);
          const win = osparc.ui.window.Window.popUpInWindow(textEditor, title, 400, 300);
          textEditor.addListener("textChanged", e => {
            const newText = e.getData();
            referenceMD.setValue(newText);
            rule.references = newText;
            win.close();
          }, this);
          textEditor.addListener("cancel", () => {
            win.close();
          }, this);
        }, this);
        this.__tsrGrid.add(button, {
          row,
          column: 3
        });

        row++;
      });

      this.__tsrGrid.add(tsrRating, {
        row,
        column: 1
      });
    },

    __populateAnnotations: function() {
      this.__annotationsGrid.removeAll();
      this.__populateAnnotationsHeaders();
      this.__populateAnnotationsData();
    },

    __populateAnnotationsHeaders: function() {
      const schemaAnnotations = this.__schema["properties"]["annotations"]["properties"];

      let row = 0;
      Object.values(schemaAnnotations).forEach(annotation => {
        let header = new qx.ui.basic.Label(annotation.title).set({
          marginTop: 5
        });
        if (annotation.description !== "") {
          header = new osparc.component.form.FieldWHint(null, annotation.description, header).set({
            allowGrowX: false
          });
        }
        this.__annotationsGrid.add(header, {
          row,
          column: 0
        });
        row++;
      });
    },

    __populateAnnotationsData: function() {
      const schemaAnnotations = this.__schema["properties"]["annotations"]["properties"];
      const copyMetadataAnnotations = this.__copyResourceData["quality"]["annotations"];

      const isEditMode = this.getMode() === "edit";

      const certificationBox = new qx.ui.form.SelectBox().set({
        allowGrowX: false,
        enabled: isEditMode
      });
      schemaAnnotations["certificationStatus"]["enum"].forEach(certStatus => {
        const certItem = new qx.ui.form.ListItem(certStatus);
        certificationBox.add(certItem);
        if (copyMetadataAnnotations.certificationStatus === certStatus) {
          certificationBox.setSelection([certItem]);
        }
      });
      certificationBox.addListener("changeSelection", e => {
        copyMetadataAnnotations.certificationStatus = e.getData()[0].getLabel();
      }, this);
      this.__annotationsGrid.add(certificationBox, {
        row: 0,
        column: 1
      });

      let row = 1;
      Object.keys(copyMetadataAnnotations).forEach(annotationKey => {
        if (annotationKey === "certificationStatus") {
          return;
        }
        const annotationMD = new osparc.ui.markdown.Markdown(copyMetadataAnnotations[annotationKey]);
        this.__annotationsGrid.add(annotationMD, {
          row,
          column: 1
        });

        if (isEditMode) {
          const button = osparc.utils.Utils.getEditButton();
          button.addListener("execute", () => {
            const title = this.tr("Edit Annotations");
            const subtitle = this.tr("Supports Markdown");
            const textEditor = new osparc.component.widget.TextEditor(copyMetadataAnnotations[annotationKey], subtitle, title);
            const win = osparc.ui.window.Window.popUpInWindow(textEditor, title, 400, 300);
            textEditor.addListener("textChanged", e => {
              const newText = e.getData();
              annotationMD.setValue(newText);
              copyMetadataAnnotations[annotationKey] = newText;
              win.close();
            }, this);
            textEditor.addListener("cancel", () => {
              win.close();
            }, this);
          }, this);
          this.__annotationsGrid.add(button, {
            row,
            column: 2
          });
        }
        row++;
      });
    },

    __createEditBtns: function() {
      const editButton = new qx.ui.toolbar.Button(this.tr("Edit")).set({
        appearance: "toolbar-md-button"
      });
      this.bind("mode", editButton, "visibility", {
        converter: value => value === "edit" ? "hidden" : "visible"
      });
      editButton.addListener("execute", () => {
        this.setMode("edit");
      }, this);

      const saveButton = new osparc.ui.toolbar.FetchButton(this.tr("Save")).set({
        appearance: "toolbar-md-button"
      });
      this.bind("mode", saveButton, "visibility", {
        converter: value => value === "edit" ? "visible" : "hidden"
      });
      saveButton.addListener("execute", e => {
        this.__save(saveButton);
      }, this);

      const cancelButton = new qx.ui.toolbar.Button(this.tr("Cancel")).set({
        appearance: "toolbar-md-button"
      });
      this.bind("mode", cancelButton, "visibility", {
        converter: value => value === "edit" ? "visible" : "hidden"
      });
      cancelButton.addListener("execute", () => {
        this.setMode("display");
      }, this);

      const buttonsToolbar = new qx.ui.toolbar.ToolBar();
      buttonsToolbar.add(editButton);
      buttonsToolbar.addSpacer();
      buttonsToolbar.add(saveButton);
      buttonsToolbar.add(cancelButton);
      this._add(buttonsToolbar);
    },

    __save: function(btn) {
      const data = {
        "quality" : {}
      };
      data["quality"]["tsr"] = this.__copyResourceData["quality"]["tsr"];
      data["quality"]["annotations"] = this.__copyResourceData["quality"]["annotations"];
      if (this.__validate(this.__schema, data["quality"])) {
        btn.setFetching(true);
        if (osparc.utils.Resources.isService(this.__copyResourceData)) {
          const params = {
            url: osparc.data.Resources.getServiceUrl(
              this.__copyResourceData["key"],
              this.__copyResourceData["version"]
            ),
            data: data
          };
          osparc.data.Resources.fetch("services", "patch", params)
            .then(serviceData => {
              this.__initResourceData(serviceData);
              this.fireDataEvent("updateService", serviceData);
            })
            .catch(err => {
              console.error(err);
              osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while updating the Quality Assessment."), "ERROR");
            })
            .finally(() => {
              btn.setFetching(false);
            });
        } else {
          const isTemplate = osparc.utils.Resources.isTemplate(this.__copyResourceData);
          const params = {
            url: {
              projectId: this.__copyResourceData["uuid"]
            },
            data: this.__copyResourceData
          };
          osparc.data.Resources.fetch(isTemplate ? "templates" : "studies", "put", params)
            .then(resourceData => {
              this.__initResourceData(resourceData);
              this.fireDataEvent(isTemplate ? "updateTemplate" : "updateStudy", resourceData);
            })
            .catch(err => {
              console.error(err);
              osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while updating the Quality Assessment."), "ERROR");
            })
            .finally(() => {
              btn.setFetching(false);
            });
        }
      }
    },

    __isUserOwner: function() {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      if (myGid) {
        if (osparc.utils.Resources.isService(this.__resourceData)) {
          return osparc.component.export.ServicePermissions.canGroupWrite(this.__resourceData["access_rights"], myGid);
        }
        return osparc.component.export.StudyPermissions.canGroupWrite(this.__resourceData["accessRights"], myGid);
      }
      return false;
    }
  }
});
