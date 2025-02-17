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

    const layout = new qx.ui.layout.VBox(10);
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

  statics: {
    createThumbnail: function(source, size) {
      return new qx.ui.basic.Image().set({
        source: source,
        alignY: "middle",
        scale: true,
        allowGrowX: true,
        allowGrowY: true,
        allowShrinkX: true,
        allowShrinkY: true,
        maxWidth: size,
        maxHeight: size,
      });
    },
  },

  members: {
    __populateLayout: function() {
      this._removeAll();

      const anatomicalModelsData = this.getAnatomicalModelsData();
      if (anatomicalModelsData && anatomicalModelsData["licensedResources"].length) {
        this.__addModelsInfo();
        this.__addPricing();
        this.__addSeatsSection();
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

    __addModelsInfo: function() {
      const modelLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(6));

      const anatomicalModelsData = this.getAnatomicalModelsData();
      const modelsInfo = anatomicalModelsData["licensedResources"];
      if (modelsInfo.length > 1) {
        const modelSelectionLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(4));
        const titleLabel = new qx.ui.basic.Label(this.tr("This bundle contains:"));
        modelSelectionLayout.add(titleLabel);
        const thumbnailsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(2));
        modelSelectionLayout.add(thumbnailsLayout);
        const thumbnailTapped = idx => {
          this.__populateModelInfo(modelLayout, anatomicalModelsData, idx);
          const selectedBorderColor = qx.theme.manager.Color.getInstance().resolve("strong-main");
          const unselectedBorderColor = "transparent";
          thumbnailsLayout.getChildren().forEach((thumbnail, index) => {
            osparc.utils.Utils.updateBorderColor(thumbnail, index === idx ? selectedBorderColor : unselectedBorderColor);
          });
        }
        modelsInfo.forEach((modelInfo, idx) => {
          const miniThumbnail = this.self().createThumbnail(modelInfo["source"]["thumbnail"], 32);
          miniThumbnail.set({
            toolTipText: modelInfo["source"]["features"]["name"]
          });
          osparc.utils.Utils.addBorder(miniThumbnail);
          miniThumbnail.addListener("tap", () => thumbnailTapped(idx));
          thumbnailsLayout.add(miniThumbnail);
        });
        this._add(modelSelectionLayout);
        thumbnailTapped(0);

        this.__populateModelInfo(modelLayout, anatomicalModelsData, 0);
      } else {
        this.__populateModelInfo(modelLayout, anatomicalModelsData, 0);
      }

      this._addAt(modelLayout, 0);
    },

    __populateModelInfo: function(modelLayout, anatomicalModelsData, selectedIdx = 0) {
      modelLayout.removeAll();

      const anatomicalModel = anatomicalModelsData["licensedResources"][selectedIdx]["source"];
      const topGrid = new qx.ui.layout.Grid(8, 6);
      topGrid.setColumnFlex(0, 1);
      const topLayout = new qx.ui.container.Composite(topGrid);
      let description = anatomicalModel["description"] || "";
      description = description.replace(/SPEAG/g, " "); // remove SPEAG substring
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
      const thumbnail = this.self().createThumbnail(anatomicalModel["thumbnail"], 256);
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

      modelLayout.add(middleLayout);

      const importButton = this.__createImportSection(anatomicalModelsData, selectedIdx);
      modelLayout.add(importButton);
    },

    __createImportSection: function(anatomicalModelsData, selectedIdx) {
      const importSection = new qx.ui.container.Composite(new qx.ui.layout.VBox(5).set({
        alignX: "center"
      }));

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
          modelId: anatomicalModelsData["licensedResources"][selectedIdx]["source"]["id"]
        });
      }, this);
      if (anatomicalModelsData["seats"].length) {
        importSection.add(importButton);
      }
      return importSection;
    },

    __addPricing: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox().set({
        alignX: "center"
      }))

      const pricingLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox()).set({
        allowGrowX: false,
        decorator: "border",
      });
      layout.add(pricingLayout)

      const pricingUnitsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignX: "center"
      }));
      const licensedItemData = this.getAnatomicalModelsData();
      osparc.store.Pricing.getInstance().fetchPricingUnits(licensedItemData["pricingPlanId"])
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
                licensedItemId: licensedItemData["licensedItemId"],
                pricingPlanId: licensedItemData["pricingPlanId"],
                pricingUnitId: pricingUnit.getPricingUnitId(),
              });
            }, this);
            pricingUnitsLayout.add(pUnit);
          });
        })
        .catch(err => console.error(err));
      this._add(pricingUnitsLayout);
      pricingLayout.add(pricingUnitsLayout)

      const poweredByLabel = new qx.ui.basic.Label().set({
        font: "text-14",
        padding: 10,
        rich: true,
        alignX: "center",
      });
      osparc.store.LicensedItems.getInstance().getLicensedItems()
        .then(licensedItems => {
          const lowerLicensedItems = osparc.store.LicensedItems.getLowerLicensedItems(licensedItems, licensedItemData["key"], licensedItemData["version"])
          if (licensedItemData["licensedResources"].length > 1 || lowerLicensedItems.length) {
            let text = this.tr("This bundle gives you access to:") + "<br>";
            licensedItemData["licensedResources"].forEach(licensedResource => {
              text += `- ${osparc.store.LicensedItems.licensedResourceNameAndVersion(licensedResource)}<br>`;
            });
            lowerLicensedItems.forEach(lowerLicensedItem => {
              lowerLicensedItem["licensedResources"].forEach(licensedResource => {
                text += `- ${osparc.store.LicensedItems.licensedResourceNameAndVersion(licensedResource)} <br>`;
              });
            })
            poweredByLabel.setValue(text);
            pricingLayout.add(poweredByLabel);
          }
        });

      this._add(layout);
    },

    __addSeatsSection: function() {
      const licensedItemData = this.getAnatomicalModelsData();
      if (licensedItemData["seats"].length === 0) {
        return;
      }

      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox().set({
        alignX: "center",
      }));

      osparc.store.LicensedItems.getInstance().getLicensedItems()
        .then(licensedItems => {
          const grid = new qx.ui.layout.Grid(15, 5);
          grid.setColumnAlign(0, "left", "middle");
          grid.setColumnAlign(1, "center", "middle");
          grid.setColumnAlign(2, "right", "middle");
          const seatsSection = new qx.ui.container.Composite(grid).set({
            allowGrowX: false,
            decorator: "border",
            padding: 10,
          });

          let rowIdx = 0;
          seatsSection.add(new qx.ui.basic.Label("Models Rented").set({font: "title-14"}), {
            column: 0,
            row: rowIdx,
          });
          seatsSection.add(new qx.ui.basic.Label("Seats").set({font: "title-14"}), {
            column: 1,
            row: rowIdx,
          });
          seatsSection.add(new qx.ui.basic.Label("Until").set({font: "title-14"}), {
            column: 2,
            row: rowIdx,
          });
          rowIdx++;

          const entryToGrid = (licensedResource, seat, row) => {
            const title = osparc.store.LicensedItems.licensedResourceNameAndVersion(licensedResource);
            seatsSection.add(new qx.ui.basic.Label(title).set({font: "text-14"}), {
              column: 0,
              row,
            });
            seatsSection.add(new qx.ui.basic.Label(seat["numOfSeats"].toString()).set({font: "text-14"}), {
              column: 1,
              row,
            });
            seatsSection.add(new qx.ui.basic.Label(osparc.utils.Utils.formatDate(seat["expireAt"])).set({font: "text-14"}), {
              column: 2,
              row,
            });
          };

          licensedItemData["seats"].forEach(seat => {
            licensedItemData["licensedResources"].forEach(licensedResource => {
              entryToGrid(licensedResource, seat, rowIdx);
              rowIdx++;
            });
          });

          const lowerLicensedItems = osparc.store.LicensedItems.getLowerLicensedItems(licensedItems, licensedItemData["key"], licensedItemData["version"])
          lowerLicensedItems.forEach(lowerLicensedItem => {
            lowerLicensedItem["seats"].forEach(seat => {
              lowerLicensedItem["licensedResources"].forEach(licensedResource => {
                entryToGrid(licensedResource, seat, rowIdx);
                rowIdx++;
              });
            });
          });

          layout.add(seatsSection);
          this._add(layout);
        });
    },
  }
});
