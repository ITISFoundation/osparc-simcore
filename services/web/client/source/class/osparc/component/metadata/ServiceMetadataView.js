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

qx.Class.define("osparc.component.metadata.ServiceMetadataView", {
  extend: qx.ui.core.Widget,

  /**
    * @param serviceData {Object} Object containing the Service Data
    */
  construct: function(serviceData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.__serviceData = serviceData;

    const grid = new qx.ui.layout.Grid(10, 8);
    grid.setColumnAlign(0, "left", "middle");
    grid.setColumnAlign(1, "left", "middle");
    this.__tsrGrid = new qx.ui.container.Composite(grid);
    this._add(this.__tsrGrid);

    this.__populateTSR();
  },

  properties: {
    mode: {
      check: ["display", "edit"],
      init: "edit",
      nullable: false,
      apply: "__populateTSR"
    }
  },

  members: {
    __serviceData: null,
    __tsrGrid: null,

    __populateTSR: function() {
      this.__tsrGrid.removeAll();
      this.__populateTSRHeaders();
      this.__populateTSRData();
    },

    __populateTSRHeaders: function() {
      const rules = osparc.component.metadata.ServiceMetadata.getMetadataTSR();

      const header0 = new qx.ui.basic.Label(this.tr("Ten Simple Rules")).set({
        font: "title-14"
      });
      this.__tsrGrid.add(header0, {
        row: 0,
        column: 0
      });
      const header1 = new qx.ui.basic.Label(this.tr("Conformance Level")).set({
        font: "title-14"
      });
      this.__tsrGrid.add(header1, {
        row: 0,
        column: 1
      });

      let row = 1;
      Object.values(rules).forEach(rule => {
        const label = new qx.ui.basic.Label(rule.title);
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
          nStars: 4
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
        showScore: true
      });
      this.__tsrGrid.add(tsrRating, {
        row,
        column: 1
      });
    },

    __populateTSRDataEdit: function() {
      const metadataTSR = this.__serviceData["metadataTSR"];
      let row = 1;
      Object.values(metadataTSR).forEach(rule => {
        const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

        const slider = new qx.ui.form.Slider().set({
          width: 150,
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
            score: value
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
          updateLevel(e.getData());
        }, this);

        this.__tsrGrid.add(layout, {
          row,
          column: 1
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
        showScore: true
      });
      this.__tsrGrid.add(tsrRating, {
        row,
        column: 1
      });
    }
  }
});
