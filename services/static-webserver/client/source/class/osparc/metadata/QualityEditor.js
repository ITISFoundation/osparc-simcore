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

qx.Class.define("osparc.metadata.QualityEditor", {
  extend: qx.ui.core.Widget,

  /**
    * @param resourceData {Object} Object containing the Resource Data
    */
  construct: function(resourceData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(8));

    this.set({
      height: 600
    });

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
      event: "changeMode"
    }
  },

  statics: {
    GridPos: {
      rule: 0,
      clCurrent: 1,
      clTarget: 2,
      reference: 3,
      edit: 4
    }
  },

  members: {
    __resourceData: null,
    __copyQualityData: null,
    __schema: null,
    __enabledQuality: null,
    __TSRSection: null,
    __tsrGrid: null,

    __initResourceData: function(resourceData) {
      if (!("quality" in resourceData)) {
        osparc.FlashMessenger.logError(this.tr("Quality Assessment data not found"));
        return;
      }

      this.__resourceData = resourceData;
      this.__copyQualityData = osparc.utils.Utils.deepCloneObject(resourceData["quality"]);

      const ajvLoader = new qx.util.DynamicScriptLoader([
        "/resource/ajv/ajv-6-11-0.min.js",
        "/resource/object-path/object-path-0-11-4.min.js"
      ]);
      ajvLoader.addListener("ready", () => {
        this.__ajv = new Ajv();
        const schemaUrl = "/resource/form/resource-quality.json";
        osparc.utils.Utils.fetchJSON(schemaUrl)
          .then(schema => {
            if (this.__validate(schema.$schema, schema)) {
              // Schema is valid
              const data = resourceData["quality"];
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
          const message = `${errors[0].dataPath} ${errors[0].message}`;
          osparc.FlashMessenger.logError(message);
        }
        return false;
      }
      return true;
    },

    __render: function(schema) {
      if (schema) {
        this._removeAll();

        this.__schema = schema;

        if (this.__canIWrite()) {
          this.__createEditButtons();
        }

        this.__createTSRSection();

        this.__createEnableSection();
        if (!this.__canIWrite()) {
          this.__enabledQuality.exclude();
        }

        this.__populateForms();
      } else {
        osparc.FlashMessenger.logError(this.tr("There was an issue validating the metadata."));
      }
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
        font: "text-14"
      });
      box.getChildControl("frame").set({
        backgroundColor: "transparent"
      });
      box.setLayout(new qx.ui.layout.VBox(10));

      const helpText = "[10 Simple Rules with Conformance Rubric](https://www.imagwiki.nibib.nih.gov/content/10-simple-rules-conformance-rubric)";
      const helpTextMD = new osparc.ui.markdown.Markdown(helpText).set({
        noMargin: true,
      });
      box.add(helpTextMD);

      const grid = new qx.ui.layout.Grid(10, 6);
      Object.values(this.self().GridPos).forEach(gridPos => {
        grid.setColumnAlign(gridPos, "left", "middle");
      });
      grid.setColumnFlex(this.self().GridPos.reference, 1);
      this.__tsrGrid = new qx.ui.container.Composite(grid);
      box.add(this.__tsrGrid);

      this._add(box);
    },

    __populateForms: function() {
      this.__populateEnable();
      this.__populateTSR();
    },

    __populateEnable: function() {
      this.__enabledQuality.setValue(this.__copyQualityData["enabled"]);
      this.__enabledQuality.addListener("changeValue", e => {
        const value = e.getData();
        this.__copyQualityData["enabled"] = value;
      }, this);
      this.__enabledQuality.bind("value", this.__TSRSection, "visibility", {
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
        font: "text-14"
      });
      this.__tsrGrid.add(headerTSR, {
        row: 0,
        column: this.self().GridPos.rule
      });

      const headerCL = new qx.ui.basic.Label(this.tr("Conformance Level")).set({
        font: "text-14"
      });
      this.__tsrGrid.add(headerCL, {
        row: 0,
        column: this.self().GridPos.clCurrent
      });

      const headerTargetCL = new qx.ui.basic.Label(this.tr("Target")).set({
        toolTipText: this.tr("Conformance Level Target"),
        font: "text-14"
      });
      this.bind("mode", headerTargetCL, "visibility", {
        converter: mode => mode === "edit" ? "visible" : "excluded"
      });
      this.__tsrGrid.add(headerTargetCL, {
        row: 0,
        column: this.self().GridPos.clTarget
      });

      const headerRef = new qx.ui.basic.Label(this.tr("References")).set({
        font: "text-14"
      });
      this.__tsrGrid.add(headerRef, {
        row: 0,
        column: this.self().GridPos.reference
      });

      let row = 1;
      Object.values(schemaRules).forEach(rule => {
        const label = new qx.ui.basic.Label(rule.title).set({
          marginTop: 5
        });
        const ruleWHint = new osparc.form.FieldWHint(null, rule.description, label).set({
          allowGrowX: false
        });
        this.__tsrGrid.add(ruleWHint, {
          row,
          column: this.self().GridPos.rule
        });
        row++;
      });
      const label = new qx.ui.basic.Label(this.tr("TSR SCORE")).set({
        font: "text-14"
      });
      this.__tsrGrid.add(label, {
        row,
        column: this.self().GridPos.rule
      });
      row++;
    },

    __populateTSRData: function() {
      const copyTSRCurrent = this.__copyQualityData["tsr_current"];
      const copyTSRTarget = this.__copyQualityData["tsr_target"];
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
      const schemaRules = this.__schema["properties"]["tsr_current"]["properties"];
      Object.keys(schemaRules).forEach(ruleKey => {
        const currentRule = copyTSRCurrent[ruleKey];

        // current
        const currentRuleLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
          alignY: "middle"
        }));
        const updateCurrentLevel = value => {
          currentRuleLayout.removeAll();
          const ruleRating = new osparc.ui.basic.StarsRating();
          ruleRating.set({
            maxScore: copyTSRTarget[ruleKey].level,
            nStars: copyTSRTarget[ruleKey].level,
            score: value,
            marginTop: 5,
            showEmptyStars: true
          });
          this.bind("mode", ruleRating, "mode");
          ruleRating.addListener("changeScore", e => {
            const newScore = e.getData();
            copyTSRCurrent[ruleKey].level = newScore;
            updateCurrentLevel(newScore);
            updateTotalTSR();
          }, this);
          const confLevel = osparc.metadata.Quality.findConformanceLevel(value);
          let hint = confLevel.title + "<br>" + confLevel.description;
          if (copyTSRTarget[ruleKey].level === 0) {
            hint = this.tr("Not Applicable");
          }
          const ruleRatingWHint = new osparc.form.FieldWHint(null, hint, ruleRating).set({
            hintPosition: "left"
          });
          currentRuleLayout.add(ruleRatingWHint);
        };
        if (currentRule.level !== undefined) {
          updateCurrentLevel(currentRule.level);
          this.__tsrGrid.add(currentRuleLayout, {
            row,
            column: this.self().GridPos.clCurrent
          });
        }

        // target
        const targetRule = copyTSRTarget[ruleKey];
        if (targetRule.level !== undefined) {
          const targetsBox = new qx.ui.form.SelectBox();
          const conformanceLevels = osparc.metadata.Quality.getConformanceLevel();
          Object.values(conformanceLevels).forEach(conformanceLevel => {
            let text = `${conformanceLevel.level} - `;
            if (conformanceLevel.level === 0) {
              text += "Not Applicable";
            } else {
              text += conformanceLevel.title;
            }
            const targetItem = new qx.ui.form.ListItem(text);
            targetItem.level = conformanceLevel.level;
            targetsBox.add(targetItem);
            if (targetRule.level === conformanceLevel.level) {
              targetsBox.setSelection([targetItem]);
            }
          });
          targetsBox.addListener("changeSelection", e => {
            const selection = e.getData();
            if (selection.length) {
              const newMaxScore = selection[0].level;
              copyTSRTarget[ruleKey].level = newMaxScore;
              copyTSRCurrent[ruleKey].level = Math.min(newMaxScore, copyTSRCurrent[ruleKey].level);
              updateCurrentLevel(copyTSRCurrent[ruleKey].level);
              updateTotalTSR();
            }
          }, this);
          this.bind("mode", targetsBox, "visibility", {
            converter: mode => mode === "edit" ? "visible" : "excluded"
          });
          this.__tsrGrid.add(targetsBox, {
            row,
            column: this.self().GridPos.clTarget
          });
        }

        // reference
        if (currentRule.references !== undefined) {
          const referenceMD = new osparc.ui.markdown.Markdown(currentRule.references).set({
            noMargin: true,
          });
          this.__tsrGrid.add(referenceMD, {
            row,
            column: this.self().GridPos.reference
          });

          const button = osparc.utils.Utils.getEditButton();
          button.addListener("execute", () => {
            const title = this.tr("Edit References");
            const textEditor = new osparc.editor.MarkdownEditor(currentRule.references);
            textEditor.getChildControl("accept-button").setLabel(this.tr("Accept"));
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
          this.bind("mode", button, "visibility", {
            converter: mode => mode === "edit" ? "visible" : "excluded"
          });
          this.__tsrGrid.add(button, {
            row,
            column: this.self().GridPos.edit
          });
        }

        row++;
      });

      this.__tsrGrid.add(tsrTotalRating, {
        row,
        column: this.self().GridPos.clCurrent
      });
    },

    __createEditButtons: function() {
      const editButton = new qx.ui.form.Button(this.tr("Edit"));
      this.bind("mode", editButton, "visibility", {
        converter: value => value === "display" ? "visible" : "excluded"
      });
      editButton.addListener("execute", () => this.setMode("edit"), this);

      const saveButton = new osparc.ui.form.FetchButton(this.tr("Save")).set({
        appearance: "form-button"
      });
      this.bind("mode", saveButton, "visibility", {
        converter: value => value === "edit" ? "visible" : "excluded"
      });
      saveButton.addListener("execute", () => this.__save(saveButton), this);

      const cancelButton = new qx.ui.form.Button(this.tr("Cancel")).set({
        appearance: "form-button-text"
      });
      this.bind("mode", cancelButton, "visibility", {
        converter: value => value === "edit" ? "visible" : "excluded"
      });
      cancelButton.addListener("execute", () => this.setMode("display"), this);

      const buttonsToolbar = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      buttonsToolbar.add(cancelButton);
      buttonsToolbar.add(editButton);
      buttonsToolbar.add(saveButton);
      this._add(buttonsToolbar);
    },

    __save: function(btn) {
      const newQuality = {
        "enabled": this.__copyQualityData["enabled"],
        "tsr_current": this.__copyQualityData["tsr_current"],
        "tsr_target": this.__copyQualityData["tsr_target"]
      };
      const patchData = {
        "quality": newQuality
      };
      if (this.__validate(this.__schema, patchData["quality"])) {
        btn.setFetching(true);
        if (osparc.utils.Resources.isService(this.__resourceData)) {
          const serviceDataCopy = osparc.utils.Utils.deepCloneObject(this.__resourceData);
          osparc.store.Services.patchServiceData(serviceDataCopy, "quality", newQuality)
            .then(() => {
              this.__initResourceData(serviceDataCopy);
              this.fireDataEvent("updateQuality", serviceDataCopy);
            })
            .catch(err => osparc.FlashMessenger.logError(err, this.tr("There was an issue while updating the Quality Assessment.")))
            .finally(() => btn.setFetching(false));
        } else {
          osparc.store.Study.getInstance().patchStudyData(this.__resourceData, "quality", newQuality)
            .then(() => {
              this.__initResourceData(this.__resourceData);
              this.fireDataEvent("updateQuality", this.__resourceData);
            })
            .catch(err => osparc.FlashMessenger.logError(err, this.tr("There was an issue while updating the Quality Assessment.")))
            .finally(() => btn.setFetching(false));
        }
      }
    },

    __canIWrite: function() {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      if (myGid) {
        if (osparc.utils.Resources.isService(this.__resourceData)) {
          return osparc.service.Utils.canIWrite(this.__resourceData["accessRights"]);
        }
        return osparc.data.model.Study.canIWrite(this.__resourceData["accessRights"]);
      }
      return false;
    }
  }
});
