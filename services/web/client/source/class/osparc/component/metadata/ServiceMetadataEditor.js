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

qx.Class.define("osparc.component.metadata.ServiceMetadataEditor", {
  extend: qx.ui.core.Widget,

  /**
    * @param serviceData {Object} Object containing the Service Data
    */
  construct: function(serviceData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    if (!("metadataTSR" in serviceData)) {
      osparc.component.message.FlashMessenger.logAs(this.tr("Metadata not found"), "ERROR");
      return;
    }

    this.__serviceData = serviceData;

    this.__createTSRSection();
    this.__createAnnotationsSection();

    if (this.__isUserOwner()) {
      const metadata = this.__serviceData;
      this.__copyMetadata = osparc.utils.Utils.deepCloneObject(metadata);
      this.__createEditBtns();
    }
  },

  events: {
    "updateService": "qx.event.type.Data"
  },

  properties: {
    mode: {
      check: ["display", "edit"],
      init: "display",
      nullable: false,
      apply: "__populateTSR"
    }
  },

  members: {
    __serviceData: null,
    __copyMetadata: null,
    __tsrGrid: null,
    __annotationsGrid: null,

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
      this.__tsrGrid = new qx.ui.container.Composite(grid);
      box.add(this.__tsrGrid, {
        flex: 1
      });

      this._add(box, {
        flex: 1
      });

      this.__populateTSR();
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
      this.__annotationsGrid = new qx.ui.container.Composite(grid);
      box.add(this.__annotationsGrid);

      this._add(box);

      this.__populateAnnotations();
    },

    __populateTSR: function() {
      this.__tsrGrid.removeAll();
      this.__populateTSRHeaders();
      this.__populateTSRData();
    },

    __populateTSRHeaders: function() {
      const rules = osparc.component.metadata.ServiceMetadata.getMetadataTSR();

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
      Object.values(rules).forEach(rule => {
        const label = new qx.ui.basic.Label(rule.title).set({
          marginTop: 5
        });
        const ruleWHint = new osparc.component.form.FieldWHint(null, rule.description, label).set({
          hintPosition: "left"
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
      const metadataTSR = this.__serviceData["metadataTSR"];
      let row = 1;
      Object.values(metadataTSR).forEach(rule => {
        const ruleRating = new osparc.ui.basic.StarsRating();
        ruleRating.set({
          score: rule.level,
          maxScore: 4,
          nStars: 4,
          marginTop: 5
        });
        const confLevel = osparc.component.metadata.ServiceMetadata.findConformanceLevel(rule.level);
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
      } = osparc.component.metadata.ServiceMetadata.computeTSRScore(metadataTSR);
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
      const copyMetadataTSR = this.__copyMetadata["metadataTSR"];
      const tsrRating = new osparc.ui.basic.StarsRating();
      tsrRating.set({
        nStars: 4,
        showScore: true,
        marginTop: 5
      });
      const updateTSRScore = () => {
        const {
          score,
          maxScore
        } = osparc.component.metadata.ServiceMetadata.computeTSRScore(copyMetadataTSR);

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

        const slider = new qx.ui.form.Slider().set({
          width: 150,
          maxHeight: 20,
          minimum: 0,
          maximum: 4,
          singleStep: 1,
          value: rule.level
        });
        layout.add(slider);

        const updateLevel = value => {
          // remove all but slider
          while (layout.getChildren().length > 1) {
            layout.removeAt(1);
          }
          const ruleRating = new osparc.ui.basic.StarsRating();
          ruleRating.set({
            maxScore: 4,
            nStars: 4,
            score: value,
            marginTop: 5
          });
          const confLevel = osparc.component.metadata.ServiceMetadata.findConformanceLevel(value);
          const hint = confLevel.title + "<br>" + confLevel.description;
          const ruleRatingWHint = new osparc.component.form.FieldWHint(null, hint, ruleRating).set({
            hintPosition: "left"
          });
          layout.add(ruleRatingWHint);
        };

        updateLevel(rule.level);
        slider.addListener("changeValue", e => {
          rule.level = e.getData();
          updateLevel(rule.level);
          updateTSRScore();
        }, this);

        this.__tsrGrid.add(layout, {
          row,
          column: 1
        });

        const references = new qx.ui.form.TextArea(rule.references).set({
          minimalLineHeight: 1
        });
        this.__tsrGrid.add(references, {
          row,
          column: 2
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
      let row = 0;
      const header0 = new qx.ui.basic.Label(this.tr("Certification status"));
      this.__annotationsGrid.add(header0, {
        row: row++,
        column: 0
      });

      const header1 = new qx.ui.basic.Label(this.tr("Certification link"));
      this.__annotationsGrid.add(header1, {
        row: row++,
        column: 0
      });

      const header2 = new qx.ui.basic.Label(this.tr("Intended purpose/context"));
      this.__annotationsGrid.add(header2, {
        row: row++,
        column: 0
      });

      const header3 = new qx.ui.basic.Label(this.tr("Verification & Validation"));
      this.__annotationsGrid.add(header3, {
        row: row++,
        column: 0
      });

      const header4 = new qx.ui.basic.Label(this.tr("Known limitations"));
      this.__annotationsGrid.add(header4, {
        row: row++,
        column: 0
      });

      const header5 = new qx.ui.basic.Label(this.tr("Documentation"));
      this.__annotationsGrid.add(header5, {
        row: row++,
        column: 0
      });

      const header6 = new qx.ui.basic.Label(this.tr("Relevant standards"));
      this.__annotationsGrid.add(header6, {
        row: row++,
        column: 0
      });
    },

    __populateAnnotationsData: function() {
      const editMode = this.getMode() === "edit";

      let row = 0;
      const certification = new qx.ui.form.SelectBox().set({
        enabled: editMode
      });
      certification.add(new qx.ui.form.ListItem("Uncertified"));
      certification.add(new qx.ui.form.ListItem("Independently reviewed"));
      certification.add(new qx.ui.form.ListItem("Regulatory grade"));
      this.__annotationsGrid.add(certification, {
        row: row++,
        column: 1
      });

      const certificationLink = new osparc.ui.markdown.Markdown();
      this.__annotationsGrid.add(certificationLink, {
        row: row++,
        column: 1
      });

      const purpose = new osparc.ui.markdown.Markdown();
      this.__annotationsGrid.add(purpose, {
        row: row++,
        column: 1
      });

      const vandv = new osparc.ui.markdown.Markdown();
      this.__annotationsGrid.add(vandv, {
        row: row++,
        column: 1
      });

      const limitations = new osparc.ui.markdown.Markdown();
      this.__annotationsGrid.add(limitations, {
        row: row++,
        column: 1
      });

      const documentation = new osparc.ui.markdown.Markdown();
      this.__annotationsGrid.add(documentation, {
        row: row++,
        column: 1
      });

      const standards = new osparc.ui.markdown.Markdown();
      this.__annotationsGrid.add(standards, {
        row: row++,
        column: 1
      });
    },

    __createEditBtns: function() {
      const editButton = new qx.ui.toolbar.Button(this.tr("Edit")).set({
        appearance: "toolbar-md-button"
      });
      editButton.addListener("execute", () => {
        this.setMode("edit");
      }, this);

      const saveButton = new qx.ui.toolbar.Button(this.tr("Save")).set({
        appearance: "toolbar-md-button"
      });
      saveButton.addListener("execute", e => {
        this.__save(saveButton);
      }, this);
      const cancelButton = new qx.ui.toolbar.Button(this.tr("Cancel")).set({
        appearance: "toolbar-md-button"
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
      const data = {};
      data["metadataTSR"] = this.__copyMetadata["metadataTSR"];
      const params = {
        url: osparc.data.Resources.getServiceUrl(
          this.__copyMetadata["key"],
          this.__copyMetadata["version"]
        ),
        data: data
      };
      osparc.data.Resources.fetch("services", "patch", params)
        .then(serviceData => {
          this.fireDataEvent("updateService", serviceData);
        })
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while updating the metadata."), "ERROR");
        })
        .finally(() => {
          btn.resetIcon();
          btn.getChildControl("icon").getContentElement()
            .removeClass("rotate");
        });
    },

    __isUserOwner: function() {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      if (myGid && osparc.component.export.ServicePermissions.canGroupWrite(this.__serviceData["access_rights"], myGid)) {
        return true;
      }
      return false;
    }
  }
});
