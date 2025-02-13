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
      if (anatomicalModelsData && anatomicalModelsData["licensedResources"].length) {
        this.__addModelsInfo(anatomicalModelsData);
        this.__addPricingUnits(anatomicalModelsData);
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

    __addModelsInfo: function(anatomicalModelsData) {
      const modelLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(16));

      const modelsInfo = anatomicalModelsData["licensedResources"];
      if (modelsInfo.length > 1) {
        const sBox = new qx.ui.form.SelectBox().set({
          minWidth: 200,
          allowGrowX: false,
        });
        modelsInfo.forEach(modelInfo => {
          const sbItem = new qx.ui.form.ListItem(modelInfo["source"]["features"]["name"]);
          sbItem.modelId = modelInfo["source"]["id"];
          sBox.add(sbItem);
        });
        this._add(sBox);
        sBox.addListener("changeSelection", e => {
          const selection = e.getData();
          if (selection.length) {
            const idxFound = modelsInfo.findIndex(mdlInfo => mdlInfo["source"]["id"] === selection[0].modelId)
            this.__populateModelInfo(modelLayout, anatomicalModelsData, idxFound);
          }
        }, this);
        this.__populateModelInfo(modelLayout, anatomicalModelsData, 0);
      } else {
        this.__populateModelInfo(modelLayout, anatomicalModelsData, 0);
      }

      this._add(modelLayout);
    },

    __populateModelInfo: function(modelLayout, anatomicalModelsData, idxFound = 0) {
      modelLayout.removeAll();

      const anatomicalModel = anatomicalModelsData["licensedResources"][idxFound]["source"];
      const topGrid = new qx.ui.layout.Grid(8, 8);
      topGrid.setColumnFlex(0, 1);
      const topLayout = new qx.ui.container.Composite(topGrid);
      const description = anatomicalModel["description"] || "";
      const delimiter = " - ";
      let titleAndSubtitle = description.split(delimiter);
      if (titleAndSubtitle.length > 0) {
        const titleLabel = new qx.ui.basic.Label().set({
          value: titleAndSubtitle[0],
          font: "text-16",
          alignY: "middle",
          allowGrowX: true,
          allowGrowY: true,
        });
        topLayout.add(titleLabel, {
          column: 0,
          row: 0,
        });
        titleAndSubtitle.shift();
      }
      if (titleAndSubtitle.length > 0) {
        titleAndSubtitle = titleAndSubtitle.join(delimiter);
        const subtitleLabel = new qx.ui.basic.Label().set({
          value: titleAndSubtitle,
          font: "text-16",
          alignY: "middle",
          allowGrowX: true,
          allowGrowY: true,
        });
        topLayout.add(subtitleLabel, {
          column: 0,
          row: 1,
        });
      }
      if (anatomicalModel["thumbnail"]) {
        const manufacturerData = {};
        if (anatomicalModel["thumbnail"].includes("itis.swiss")) {
          manufacturerData["label"] = "IT'IS Foundation";
          manufacturerData["link"] = "https://itis.swiss/virtual-population/";
          manufacturerData["icon"] = "https://media.licdn.com/dms/image/v2/C4D0BAQE_FGa66IyvrQ/company-logo_200_200/company-logo_200_200/0/1631341490431?e=2147483647&v=beta&t=7f_IK-ArGjPrz-1xuWolAT4S2NdaVH-e_qa8hsKRaAc";
        } else if (anatomicalModel["thumbnail"].includes("speag.swiss")) {
          manufacturerData["label"] = "Speag";
          manufacturerData["link"] = "https://speag.swiss/products/em-phantoms/overview-2/";
          manufacturerData["icon"] = "https://media.licdn.com/dms/image/v2/D4E0BAQG2CYG28KAKbA/company-logo_200_200/company-logo_200_200/0/1700045977122/schmid__partner_engineering_ag_logo?e=2147483647&v=beta&t=6CZb1jjg5TnnzQWkrZBS9R3ebRKesdflg-_xYi4dwD8";
        }
        const manufacturerLink = new qx.ui.basic.Atom().set({
          label: manufacturerData["label"],
          icon: manufacturerData["icon"],
          font: "text-16",
          gap: 10,
          iconPosition: "right",
          cursor: "pointer",
        });
        manufacturerLink.getChildControl("icon").set({
          maxWidth: 32,
          maxHeight: 32,
          scale: true,
          decorator: "rounded",
        });
        manufacturerLink.addListener("tap", () => window.open(manufacturerData["link"]));
        topLayout.add(manufacturerLink, {
          column: 1,
          row: 0,
          rowSpan: 2,
        });
      }
      modelLayout.add(topLayout);


      const middleLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(16));
      const thumbnail = new qx.ui.basic.Image().set({
        source: anatomicalModel["thumbnail"],
        alignY: "middle",
        scale: true,
        allowGrowX: true,
        allowGrowY: true,
        allowShrinkX: true,
        allowShrinkY: true,
        maxWidth: 256,
        maxHeight: 256,
      });
      middleLayout.add(thumbnail);

      const features = anatomicalModel["features"];
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

      if (anatomicalModel["doi"]) {
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

        const doiToLink = doi => {
          const doiLabel = new osparc.ui.basic.LinkLabel("-").set({
            font: "text-14",
            alignX: "left",
            marginTop: 16,
          });
          if (doi) {
            doiLabel.set({
              value: doi,
              url: "https://doi.org/" + doi,
              font: "link-label-14",
            });
          }
          return doiLabel;
        };
        featuresLayout.add(doiToLink(anatomicalModel["doi"]), {
          column: 1,
          row: idx,
        });
      }

      middleLayout.add(featuresLayout);

      const importButton = this.__createImportSection(anatomicalModelsData);
      modelLayout.add(importButton);

      modelLayout.add(middleLayout);
    },

    __addPricingUnits: function(anatomicalModelsData) {
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
                modelId: anatomicalModelsData["licensedResourceData"]["source"]["id"],
                licensedItemId: anatomicalModelsData["licensedItemId"],
                pricingPlanId: anatomicalModelsData["pricingPlanId"],
                pricingUnitId: pricingUnit.getPricingUnitId(),
              });
            }, this);
            pricingUnitsLayout.add(pUnit);
          });
        })
        .catch(err => console.error(err));

      this._add(pricingUnitsLayout);
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
          modelId: anatomicalModelsData["licensedResourceData"]["source"]["id"]
        });
      }, this);
      if (anatomicalModelsData["purchases"].length) {
        importSection.add(importButton);
      }
      return importSection;
    },
  }
});
