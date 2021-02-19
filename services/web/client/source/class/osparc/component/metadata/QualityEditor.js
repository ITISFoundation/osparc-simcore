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

    this._setLayout(new qx.ui.layout.VBox(8));

    this.__initResourceData(resourceData);
  },

  events: {
    "updateQuality": "qx.event.type.Data"
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

  // eslint-disable-next-line qx-rules/no-refs-in-members
  members: {
    __resourceData: null,
    __copyResourceData: null,
    __schema: null,
    __enabledQuality: null,
    __TSRSection: null,
    __annotationsSection: null,
    __tsrGrid: null,
    __annotationsGrid: null,
    __tsrGridPos: {
      rule: 0,
      clCurrent: 1,
      clTarget: 2,
      reference: 3,
      edit: 4
    },

    __initResourceData: function(resourceData) {
      if (!("quality" in resourceData)) {
        osparc.component.message.FlashMessenger.logAs(this.tr("Quality Assessment data not found"), "ERROR");
        return;
      }

      this.__resourceData = resourceData;
      if (!("tsr_current" in resourceData["quality"])) {
        resourceData["quality"]["tsr_current"] = resourceData["quality"]["tsr"] || osparc.component.metadata.Quality.getDefaultCurrentQualityTSR();
      }
      if (!("tsr_target" in resourceData["quality"])) {
        resourceData["quality"]["tsr_target"] = osparc.component.metadata.Quality.getDefaultTargetQualityTSR();
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

        if (this.__isUserOwner()) {
          this.__createEditBtns();
        }

        this.__createEnableSection();
        if (!this.__isUserOwner()) {
          this.__enabledQuality.exclude();
        }

        this.__createTSRSection();
        this.__createAnnotationsSection();

        this.__populateForms();
      } else {
        osparc.component.message.FlashMessenger.logAs(this.tr("There was an error validating the metadata."), "ERROR");
      }
    },

    __populateForms: function() {
      this.__populateEnable();
      this.__populateTSR();
      this.__populateAnnotations();
    },

    __createEnableSection: function() {
      const enabledQuality = this.__enabledQuality = new qx.ui.form.CheckBox(this.tr("Enabled"));
      this.bind("mode", enabledQuality, "enabled", {
        converter: value => value === "edit"
      });
      this._add(enabledQuality);
    },

    __createTSRSection: function() {
      const box = this.__TSRSection = new qx.ui.groupbox.GroupBox(this.tr("Ten Simple Rules"));
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

      const grid = new qx.ui.layout.Grid(10, 6);
      Object.values(this.__tsrGridPos).forEach(gridPos => {
        grid.setColumnAlign(gridPos, "left", "middle");
      });
      grid.setColumnFlex(this.__tsrGridPos.reference, 1);
      this.__tsrGrid = new qx.ui.container.Composite(grid);
      box.add(this.__tsrGrid);

      this._add(box);
    },

    __createAnnotationsSection: function() {
      const box = this.__annotationsSection = new qx.ui.groupbox.GroupBox(this.tr("Annotations"));
      box.getChildControl("legend").set({
        font: "title-14"
      });
      box.getChildControl("frame").set({
        backgroundColor: "transparent"
      });
      box.setLayout(new qx.ui.layout.VBox(10));

      const grid = new qx.ui.layout.Grid(10, 6);
      grid.setColumnAlign(0, "left", "middle");
      grid.setColumnAlign(1, "left", "middle");
      grid.setColumnAlign(2, "left", "middle");
      grid.setColumnFlex(1, 1);
      this.__annotationsGrid = new qx.ui.container.Composite(grid);
      box.add(this.__annotationsGrid);

      this._add(box);
    },

    __populateEnable: function() {
      this.__enabledQuality.setValue(this.__copyResourceData["quality"]["enabled"]);
      this.__enabledQuality.addListener("changeValue", e => {
        const value = e.getData();
        this.__copyResourceData["quality"]["enabled"] = value;
      }, this);
      this.__enabledQuality.bind("value", this.__TSRSection, "visibility", {
        converter: value => value ? "visible" : "excluded"
      });
      this.__enabledQuality.bind("value", this.__annotationsSection, "visibility", {
        converter: value => value ? "visible" : "excluded"
      });
    },

    __populateTSR: function() {
      this.__tsrGrid.removeAll();
      this.__populateTSRHeaders();
      this.__populateTSRData();
    },

    __populateTSRHeaders: function() {
      const schemaRules = this.__schema["properties"]["tsr_current"]["properties"];

      const headerTSR = new qx.ui.basic.Label(this.tr("Rules")).set({
        font: "title-14"
      });
      this.__tsrGrid.add(headerTSR, {
        row: 0,
        column: this.__tsrGridPos.rule
      });

      const headerCL = new qx.ui.basic.Label(this.tr("Conf. Level")).set({
        toolTipText: this.tr("Conformance Level"),
        font: "title-14"
      });
      this.__tsrGrid.add(headerCL, {
        row: 0,
        column: this.__tsrGridPos.clCurrent
      });

      const headerTargetCL = new qx.ui.basic.Label(this.tr("Target")).set({
        toolTipText: this.tr("Conformance Level Target"),
        font: "title-14"
      });
      this.bind("mode", headerTargetCL, "visibility", {
        converter: mode => mode === "edit" ? "visible" : "excluded"
      });
      this.__tsrGrid.add(headerTargetCL, {
        row: 0,
        column: this.__tsrGridPos.clTarget
      });

      const headerRef = new qx.ui.basic.Label(this.tr("References")).set({
        font: "title-14"
      });
      this.__tsrGrid.add(headerRef, {
        row: 0,
        column: this.__tsrGridPos.reference
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
          column: this.__tsrGridPos.rule
        });
        row++;
      });
      const label = new qx.ui.basic.Label("TSR score").set({
        font: "title-13"
      });
      this.__tsrGrid.add(label, {
        row,
        column: this.__tsrGridPos.rule
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
      const currentTSR = this.__copyResourceData["quality"]["tsr_current"];
      const targetTSR = this.__copyResourceData["quality"]["tsr_target"];
      let row = 1;
      Object.entries(currentTSR).forEach(([tsrKey, cTSR]) => {
        const ruleRating = new osparc.ui.basic.StarsRating();
        ruleRating.set({
          score: cTSR.level,
          maxScore: 4,
          nStars: targetTSR[tsrKey].level,
          showEmptyStars: true,
          marginTop: 5
        });
        const confLevel = osparc.component.metadata.Quality.findConformanceLevel(cTSR.level);
        const hint = confLevel.title + "<br>" + confLevel.description;
        const ruleRatingWHint = new osparc.component.form.FieldWHint(null, hint, ruleRating).set({
          hintPosition: "left"
        });
        this.__tsrGrid.add(ruleRatingWHint, {
          row,
          column: this.__tsrGridPos.clCurrent
        });

        const referenceMD = new osparc.ui.markdown.Markdown(cTSR.references);
        this.__tsrGrid.add(referenceMD, {
          row,
          column: this.__tsrGridPos.reference
        });

        row++;
      });

      const tsrRating = new osparc.ui.basic.StarsRating().set({
        nStars: 4,
        showScore: true,
        marginTop: 5
      });
      osparc.ui.basic.StarsRating.scoreToStarsRating(currentTSR, targetTSR, tsrRating);
      this.__tsrGrid.add(tsrRating, {
        row,
        column: this.__tsrGridPos.clCurrent
      });
    },

    __populateTSRDataEdit: function() {
      const copyTSRCurrent = this.__copyResourceData["quality"]["tsr_current"];
      const copyTSRTarget = this.__copyResourceData["quality"]["tsr_target"];
      const tsrTotalRating = new osparc.ui.basic.StarsRating();
      tsrTotalRating.set({
        nStars: 4,
        showScore: true,
        marginTop: 5
      });
      const updateTotalTSR = () => {
        osparc.ui.basic.StarsRating.scoreToStarsRating(copyTSRCurrent, copyTSRTarget, tsrTotalRating);
      };
      updateTotalTSR();

      let row = 1;
      Object.keys(copyTSRCurrent).forEach(ruleKey => {
        const currentRule = copyTSRCurrent[ruleKey];

        const currentRulelayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
          alignY: "middle"
        }));
        const updateCurrentLevel = value => {
          currentRulelayout.removeAll();
          const ruleRating = new osparc.ui.basic.StarsRating();
          ruleRating.set({
            maxScore: 4,
            nStars: copyTSRTarget[ruleKey].level,
            score: value,
            marginTop: 5,
            mode: "edit"
          });
          ruleRating.addListener("changeScore", e => {
            const newScore = e.getData();
            copyTSRCurrent[ruleKey].level = newScore;
            updateCurrentLevel(newScore);
            updateTotalTSR();
          }, this);
          const confLevel = osparc.component.metadata.Quality.findConformanceLevel(value);
          const hint = confLevel.title + "<br>" + confLevel.description;
          const ruleRatingWHint = new osparc.component.form.FieldWHint(null, hint, ruleRating).set({
            hintPosition: "left"
          });
          currentRulelayout.add(ruleRatingWHint);
        };
        updateCurrentLevel(currentRule.level);
        this.__tsrGrid.add(currentRulelayout, {
          row,
          column: this.__tsrGridPos.clCurrent
        });

        const targetRule = copyTSRTarget[ruleKey];
        const targerRulelayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
          alignY: "middle"
        }));
        const updateTargetLevel = value => {
          targerRulelayout.removeAll();
          const ruleRating = new osparc.ui.basic.StarsRating();
          ruleRating.set({
            maxScore: 4,
            nStars: 4,
            score: value,
            marginTop: 5,
            mode: "edit"
          });
          ruleRating.addListener("changeScore", e => {
            const newMaxScore = e.getData();
            copyTSRTarget[ruleKey].level = newMaxScore;
            updateTargetLevel(newMaxScore);
            updateCurrentLevel(Math.min(newMaxScore, copyTSRCurrent[ruleKey].level));
            updateTotalTSR();
          }, this);
          const confLevel = osparc.component.metadata.Quality.findConformanceLevel(value);
          const hint = confLevel.title + "<br>" + confLevel.description;
          const ruleRatingWHint = new osparc.component.form.FieldWHint(null, hint, ruleRating).set({
            hintPosition: "left"
          });
          targerRulelayout.add(ruleRatingWHint);
        };
        updateTargetLevel(targetRule.level);

        this.__tsrGrid.add(targerRulelayout, {
          row,
          column: this.__tsrGridPos.clTarget
        });

        const referenceMD = new osparc.ui.markdown.Markdown(currentRule.references);
        this.__tsrGrid.add(referenceMD, {
          row,
          column: this.__tsrGridPos.reference
        });

        const button = osparc.utils.Utils.getEditButton();
        button.addListener("execute", () => {
          const title = this.tr("Edit References");
          const subtitle = this.tr("Supports Markdown");
          const textEditor = new osparc.component.widget.TextEditor(currentRule.references, subtitle, title);
          const win = osparc.ui.window.Window.popUpInWindow(textEditor, title, 400, 300);
          textEditor.addListener("textChanged", e => {
            const newText = e.getData();
            referenceMD.setValue(newText);
            currentRule.references = newText;
            win.close();
          }, this);
          textEditor.addListener("cancel", () => {
            win.close();
          }, this);
        }, this);
        this.__tsrGrid.add(button, {
          row,
          column: this.__tsrGridPos.edit
        });

        row++;
      });

      this.__tsrGrid.add(tsrTotalRating, {
        row,
        column: this.__tsrGridPos.clCurrent
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
        converter: value => value === "display" ? "visible" : "excluded"
      });
      editButton.addListener("execute", () => {
        this.setMode("edit");
      }, this);

      const saveButton = new osparc.ui.toolbar.FetchButton(this.tr("Save")).set({
        appearance: "toolbar-md-button"
      });
      this.bind("mode", saveButton, "visibility", {
        converter: value => value === "edit" ? "visible" : "excluded"
      });
      saveButton.addListener("execute", e => {
        this.__save(saveButton);
      }, this);

      const cancelButton = new qx.ui.toolbar.Button(this.tr("Cancel")).set({
        appearance: "toolbar-md-button"
      });
      this.bind("mode", cancelButton, "visibility", {
        converter: value => value === "edit" ? "visible" : "excluded"
      });
      cancelButton.addListener("execute", () => {
        this.setMode("display");
      }, this);

      const buttonsToolbar = new qx.ui.toolbar.ToolBar();
      buttonsToolbar.addSpacer();
      buttonsToolbar.add(editButton);
      buttonsToolbar.add(saveButton);
      buttonsToolbar.add(cancelButton);
      this._add(buttonsToolbar);
    },

    __save: function(btn) {
      const data = {
        "quality" : {}
      };
      data["quality"]["enabled"] = this.__copyResourceData["quality"]["enabled"];
      data["quality"]["tsr_current"] = this.__copyResourceData["quality"]["tsr_current"];
      data["quality"]["tsr_target"] = this.__copyResourceData["quality"]["tsr_target"];
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
              this.fireDataEvent("updateQuality", serviceData);
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
              this.fireDataEvent("updateQuality", resourceData);
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
          return osparc.component.permissions.Service.canGroupWrite(this.__resourceData["access_rights"], myGid);
        }
        return osparc.component.permissions.Study.canGroupWrite(this.__resourceData["accessRights"], myGid);
      }
      return false;
    }
  }
});
