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

    const layout = new qx.ui.layout.VBox(20);
    this._setLayout(layout);

    this.__poplulateLayout();
  },

  events: {
    "modelLeased": "qx.event.type.Event",
  },

  properties: {
    anatomicalModelsData: {
      check: "Object",
      init: null,
      nullable: true,
      apply: "__poplulateLayout"
    },
  },

  members: {
    __poplulateLayout: function() {
      this._removeAll();

      const anatomicalModelsData = this.getAnatomicalModelsData();
      if (anatomicalModelsData) {
        const modelInfo = this.__createModelInfo(anatomicalModelsData);
        this._add(modelInfo);
        const pricingUnits = this.__createPricingUnits(anatomicalModelsData);
        this._add(pricingUnits);
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

      const description = anatomicalModelsData["description"];
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
        value: anatomicalModelsData["DOI"] ? anatomicalModelsData["DOI"] : "-",
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
      console.log(anatomicalModelsData);
      const pricingUnitsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignX: "center"
      }));

      const params = {
        url: {
          pricingPlanId: anatomicalModelsData["pricingPlanId"]
        }
      };
      osparc.data.Resources.fetch("pricingPlans", "getOne", params)
        .then(data => {
          const pricingUnitsData = data["pricingUnits"];
          pricingUnitsData.forEach(pricingUnitData => {
            const pricingUnit = new osparc.data.model.PricingUnit(pricingUnitData).set({
              classification: "LICENSE"
            });
            const pUnit = new osparc.study.PricingUnitLicense(pricingUnit).set({
              showRentButton: true,
              allowGrowY: false,
            });
            pUnit.addListener("rentPricingUnit", () => this.__rentAnatomicalModel(anatomicalModelsData, pricingUnit));
            pricingUnitsLayout.add(pUnit);
          });
        })
        .catch(err => console.error(err));

      return pricingUnitsLayout;
    },

    __rentAnatomicalModel: function(anatomicalModelsData, pricingUnit) {
      console.log(":purchase", anatomicalModelsData["licensedItemId"], pricingUnit.getPricingUnitId());
    },
  }
});
