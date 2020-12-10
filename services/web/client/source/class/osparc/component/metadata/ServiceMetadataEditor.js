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

    this._setLayout(new qx.ui.layout.VBox());

    if (!("metadataTSR" in serviceData)) {
      osparc.component.message.FlashMessenger.logAs(this.tr("Metadata not found"), "ERROR");
      return;
    }

    this.__serviceData = serviceData;

    const grid = new qx.ui.layout.Grid(10, 8);
    grid.setColumnAlign(0, "left", "middle");
    grid.setColumnAlign(1, "left", "middle");
    this.__tsrGrid = new qx.ui.container.Composite(grid);
    this._add(this.__tsrGrid, {
      flex: 1
    });

    this.__populateTSR();

    if (this.__isUserOwner()) {
      const metadata = this.__serviceData;
      this.__copyMetadata = osparc.utils.Utils.deepCloneObject(metadata);
      this.__createEditBtns();
    }
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

    __populateTSR: function() {
      this.__tsrGrid.removeAll();
      this.__populateTSRHeaders();
      this.__populateTSRData();
    },

    __populateTSRHeaders: function() {
      const rules = osparc.component.metadata.ServiceMetadata.getMetadataTSR();

      const headerTSR = new qx.ui.basic.Label(this.tr("Ten Simple Rules")).set({
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

    __isUserOwner: function() {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      if (myGid && osparc.component.export.ServicePermissions.canGroupWrite(this.__serviceData["access_rights"], myGid)) {
        return true;
      }
      return false;
    }
  }
});
