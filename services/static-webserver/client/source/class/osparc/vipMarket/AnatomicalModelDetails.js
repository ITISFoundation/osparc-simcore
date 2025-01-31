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

qx.Class.define("osparc.vipMarket.AnatomicalModelDetails", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    const layout = new qx.ui.layout.VBox(15);
    this._setLayout(layout);

    this.__populateLayout();
  },

  events: {
    "modelPurchaseRequested": "qx.event.type.Data",
    "modelImportRequested": "qx.event.type.Data",
  },

  properties: {
    openBy: {
      check: "String",
      init: null,
      nullable: true,
      event: "changeOpenBy",
    },

    anatomicalModelsData: {
      check: "Object",
      init: null,
      nullable: true,
      apply: "__populateLayout"
    },
  },

  members: {
    __populateLayout: function() {
      this._removeAll();

      const anatomicalModelsData = this.getAnatomicalModelsData();
      if (anatomicalModelsData) {
        const modelInfo = this.__createModelInfo(anatomicalModelsData["licensedResourceData"]);
        const pricingUnits = this.__createPricingUnits(anatomicalModelsData);
        const importButton = this.__createImportSection(anatomicalModelsData);
        this._add(modelInfo);
        this._add(pricingUnits);
        this._add(importButton);
      } else {
        const selectModelLabel = new qx.ui.basic.Label().set({
          value: this.tr("Select a model for more details"),
          font: "text-16",
          alignX: "center",
          alignY: "middle",
          allowGrowX: true,
          allowGrowY: true,
        });
        this._add(selectModelLabel);
      }
    },

    __createModelInfo: function(anatomicalModelsData) {
      const cardGrid = new qx.ui.layout.Grid(16, 16);
      const cardLayout = new qx.ui.container.Composite(cardGrid);

      const description = anatomicalModelsData["description"] || "";
      description.split(" - ").forEach((desc, idx) => {
        const titleLabel = new qx.ui.basic.Label().set({
          value: desc,
          font: "text-16",
          alignX: "center",
          alignY: "middle",
          allowGrowX: true,
          allowGrowY: true,
        });
        cardLayout.add(titleLabel, {
          column: 0,
          row: idx,
          colSpan: 2,
        });
      });

      const thumbnail = new qx.ui.basic.Image().set({
        source: anatomicalModelsData["thumbnail"],
        alignY: "middle",
        scale: true,
        allowGrowX: true,
        allowGrowY: true,
        allowShrinkX: true,
        allowShrinkY: true,
        maxWidth: 256,
        maxHeight: 256,
      });
      cardLayout.add(thumbnail, {
        column: 0,
        row: 2,
      });

      const features = anatomicalModelsData["features"];
      const featuresGrid = new qx.ui.layout.Grid(8, 8);
      const featuresLayout = new qx.ui.container.Composite(featuresGrid);
      let idx = 0;
      [
        "Name",
        "Version",
        "Sex",
        "Age",
        "Weight",
        "Height",
        "Date",
        "Ethnicity",
        "Functionality",
      ].forEach(key => {
        if (key.toLowerCase() in features) {
          const titleLabel = new qx.ui.basic.Label().set({
            value: key,
            font: "text-14",
            alignX: "right",
          });
          featuresLayout.add(titleLabel, {
            column: 0,
            row: idx,
          });

          const nameLabel = new qx.ui.basic.Label().set({
            value: features[key.toLowerCase()],
            font: "text-14",
            alignX: "left",
          });
          featuresLayout.add(nameLabel, {
            column: 1,
            row: idx,
          });

          idx++;
        }
      });

      const doiTitle = new qx.ui.basic.Label().set({
        value: "DOI",
        font: "text-14",
        alignX: "right",
        marginTop: 16,
      });
      featuresLayout.add(doiTitle, {
        column: 0,
        row: idx,
      });

      const doiValue = new qx.ui.basic.Label().set({
        value: anatomicalModelsData["doi"] ? anatomicalModelsData["doi"] : "-",
        font: "text-14",
        alignX: "left",
        marginTop: 16,
      });
      featuresLayout.add(doiValue, {
        column: 1,
        row: idx,
      });

      cardLayout.add(featuresLayout, {
        column: 1,
        row: 2,
      });

      return cardLayout;
    },

    __createPricingUnits: function(anatomicalModelsData) {
      const pricingUnitsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignX: "center"
      }));

      osparc.store.Pricing.getInstance().fetchPricingUnits(anatomicalModelsData["pricingPlanId"])
        .then(pricingUnits => {
          pricingUnits.forEach(pricingUnit => {
            pricingUnit.set({
              classification: "LICENSE"
            });
            const pUnit = new osparc.study.PricingUnitLicense(pricingUnit).set({
              showRentButton: true,
            });
            pUnit.addListener("rentPricingUnit", () => {
              this.fireDataEvent("modelPurchaseRequested", {
                modelId: anatomicalModelsData["modelId"],
                licensedItemId: anatomicalModelsData["licensedItemId"],
                pricingPlanId: anatomicalModelsData["pricingPlanId"],
                pricingUnitId: pricingUnit.getPricingUnitId(),
              });
            }, this);
            pricingUnitsLayout.add(pUnit);
          });
        })
        .catch(err => console.error(err));

      return pricingUnitsLayout;
    },

    __createImportSection: function(anatomicalModelsData) {
      const importSection = new qx.ui.container.Composite(new qx.ui.layout.VBox(5).set({
        alignX: "center"
      }));

      anatomicalModelsData["purchases"].forEach(purchase => {
        const seatsText = "seat" + (purchase["numberOfSeats"] > 1 ? "s" : "");
        const entry = new qx.ui.basic.Label().set({
          value: `${purchase["numberOfSeats"]} ${seatsText} available until ${osparc.utils.Utils.formatDate(purchase["expiresAt"])}`,
          font: "text-14",
        });
        importSection.add(entry);
      });

      const importButton = new qx.ui.form.Button().set({
        label: this.tr("Import"),
        appearance: "strong-button",
        center: true,
        maxWidth: 200,
        alignX: "center",
      });
      this.bind("openBy", importButton, "visibility", {
        converter: openBy => openBy ? "visible" : "excluded"
      });
      importButton.addListener("execute", () => {
        this.fireDataEvent("modelImportRequested", {
          modelId: anatomicalModelsData["modelId"]
        });
      }, this);
      if (anatomicalModelsData["purchases"].length) {
        importSection.add(importButton);
      }
      return importSection;
    },
  }
});
