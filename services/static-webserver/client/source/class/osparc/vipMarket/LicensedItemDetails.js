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

qx.Class.define("osparc.vipMarket.LicensedItemDetails", {
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
    __modelsInfoStack: null,

    __populateLayout: function() {
      this._removeAll();

      const licensedItem = this.getAnatomicalModelsData();
      if (licensedItem && licensedItem.getLicensedResources().length) {
        this.__addModelsInfo();
        this.__addSeatsSection();
        this.__addPricing();
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
      const modelBundleLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(6));

      const stack = this.__modelsInfoStack = new qx.ui.container.Stack();
      this._add(stack, {
        flex: 1
      });
      modelBundleLayout.add(this.__modelsInfoStack);

      this.__populateModelsInfo();

      const licensedItem = this.getAnatomicalModelsData();
      const licensedResources = licensedItem.getLicensedResources();
      if (licensedResources.length > 1) {
        const modelSelectionLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(4));
        const titleLabel = new qx.ui.basic.Label(this.tr("This bundle contains:"));
        modelSelectionLayout.add(titleLabel);
        const modelsLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(4));
        modelSelectionLayout.add(modelsLayout);

        const modelSelected = idx => {
          if (this.__modelsInfoStack.getSelectables().length > idx) {
            this.__modelsInfoStack.setSelection([stack.getSelectables()[idx]]);
          }

          const selectedBorderColor = qx.theme.manager.Color.getInstance().resolve("strong-main");
          const unselectedBorderColor = "transparent";
          modelsLayout.getChildren().forEach((thumbnailAndTitle, index) => {
            const thumbnail = thumbnailAndTitle.getChildren()[0];
            osparc.utils.Utils.updateBorderColor(thumbnail, index === idx ? selectedBorderColor : unselectedBorderColor);
          });
        }

        licensedResources.forEach((licensedResource, idx) => {
          const modelLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(4)).set({
            allowGrowX: false,
          });
          const miniThumbnail = this.self().createThumbnail(licensedResource["thumbnail"], 32);
          osparc.utils.Utils.addBorder(miniThumbnail);
          modelLayout.add(miniThumbnail);
          const title = new qx.ui.basic.Label().set({
            value: osparc.data.model.LicensedItem.licensedResourceTitle(licensedResource),
            alignY: "middle"
          });
          modelLayout.add(title);
          modelLayout.setCursor("pointer");
          modelLayout.addListener("tap", () => modelSelected(idx));
          modelsLayout.add(modelLayout);
        });
        modelBundleLayout.add(modelSelectionLayout);

        modelSelected(0);
      }

      this._add(modelBundleLayout);
    },

    __populateModelsInfo: function() {
      this.__modelsInfoStack.removeAll();

      const licensedItem = this.getAnatomicalModelsData();
      const licensedResources = licensedItem.getLicensedResources();
      licensedResources.forEach((licensedResource, index) => {
        const modelInfoLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(4));

        const topGrid = new qx.ui.layout.Grid(8, 6);
        topGrid.setColumnFlex(0, 1);
        const headerLayout = new qx.ui.container.Composite(topGrid);
        let description = licensedResource["description"] || "";
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
          headerLayout.add(titleLabel, {
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
          headerLayout.add(subtitleLabel, {
            column: 0,
            row: 1,
          });
        }
        if (licensedResource["thumbnail"]) {
          const manufacturerData = {};
          if (licensedResource["thumbnail"].includes("itis.swiss")) {
            manufacturerData["label"] = "IT'IS Foundation";
            manufacturerData["link"] = "https://itis.swiss/virtual-population/";
            manufacturerData["icon"] = "https://media.licdn.com/dms/image/v2/C4D0BAQE_FGa66IyvrQ/company-logo_200_200/company-logo_200_200/0/1631341490431?e=2147483647&v=beta&t=7f_IK-ArGjPrz-1xuWolAT4S2NdaVH-e_qa8hsKRaAc";
          } else if (licensedResource["thumbnail"].includes("speag.swiss")) {
            manufacturerData["label"] = "Speag";
            manufacturerData["link"] = "https://speag.swiss/products/em-phantoms/overview-2/";
            manufacturerData["icon"] = "https://media.licdn.com/dms/image/v2/D4E0BAQG2CYG28KAKbA/company-logo_200_200/company-logo_200_200/0/1700045977122/schmid__partner_engineering_ag_logo?e=2147483647&v=beta&t=6CZb1jjg5TnnzQWkrZBS9R3ebRKesdflg-_xYi4dwD8";
          }
          if (Object.keys(manufacturerData).length) {
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
            headerLayout.add(manufacturerLink, {
              column: 1,
              row: 0,
              rowSpan: 2,
            });
          }
        }
        modelInfoLayout.add(headerLayout);


        const middleLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(16));
        const thumbnail = this.self().createThumbnail(licensedResource["thumbnail"], 256);
        middleLayout.add(thumbnail);

        const features = licensedResource["features"];
        const featuresGrid = new qx.ui.layout.Grid(8, 8);
        const featuresLayout = new qx.ui.container.Composite(featuresGrid);
        let idx = 0;
        const capitalizeField = [
          "Sex",
          "Species",
          "Ethnicity",
          "Functionality",
        ];
        [
          "Name",
          "Version",
          "Date",
          "Species",
          "Sex",
          "Age",
          "Weight",
          "Height",
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

            const value = features[key.toLowerCase()];
            const featureValue = capitalizeField.includes(key) ? osparc.utils.Utils.capitalize(value) : value;
            const nameLabel = new qx.ui.basic.Label().set({
              value: featureValue,
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

        if (licensedResource["doi"]) {
          const doiTitle = new qx.ui.basic.Label().set({
            value: "DOI",
            font: "text-14",
            alignX: "right",
            marginTop: 10,
          });
          featuresLayout.add(doiTitle, {
            column: 0,
            row: idx,
          });

          const doiToLink = doi => {
            const doiLabel = new osparc.ui.basic.LinkLabel("-").set({
              font: "text-14",
              alignX: "left",
              marginTop: 10,
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
          featuresLayout.add(doiToLink(licensedResource["doi"]), {
            column: 1,
            row: idx,
          });
          idx++;
        }

        if (licensedItem["termsOfUseUrl"] || licensedResource["termsOfUseUrl"]) { // remove the first one when this info goes down to the model
          const tAndC = new qx.ui.basic.Label().set({
            font: "text-14",
            value: this.tr("<u>Terms and Conditions</u>"),
            rich: true,
            anonymous: false,
            cursor: "pointer",
          });
          tAndC.addListener("tap", () => this.__openLicense(licensedItem["termsOfUseUrl"] || licensedResource["termsOfUseUrl"]));
          featuresLayout.add(tAndC, {
            column: 1,
            row: idx,
          });
          idx++;
        }

        middleLayout.add(featuresLayout);

        modelInfoLayout.add(middleLayout);

        const importSection = this.__createImportSection(licensedItem, index);
        modelInfoLayout.add(importSection);

        this.__modelsInfoStack.add(modelInfoLayout);
      })
    },

    __openLicense: function(rawLink) {
      if (rawLink.includes("github")) {
        // make sure the raw version of the link is shown
        rawLink += "?raw=true";
      }
      const mdWindow = new osparc.ui.markdown.MarkdownWindow(rawLink).set({
        caption: this.tr("Terms and Conditions"),
        width: 800,
        height: 600,
      });
      mdWindow.open();
    },

    __createImportSection: function(anatomicalModelsData, selectedIdx) {
      const importSection = new qx.ui.container.Composite(new qx.ui.layout.VBox().set({
        alignX: "center"
      }));

      const importButton = new qx.ui.form.Button().set({
        label: this.tr("Import"),
        appearance: "strong-button",
        center: true,
        maxWidth: 200,
        alignX: "center",
        marginTop: 10,
      });
      this.bind("openBy", importButton, "visibility", {
        converter: openBy => openBy ? "visible" : "excluded"
      });
      importButton.addListener("execute", () => {
        this.fireDataEvent("modelImportRequested", {
          modelId: anatomicalModelsData.getLicensedResources()[selectedIdx]["id"],
          categoryId: anatomicalModelsData.getCategoryId(),
        });
      }, this);

      osparc.store.Pricing.getInstance().fetchPricingUnits(anatomicalModelsData.getPricingPlanId())
        .then(pricingUnits => {
          if (
            anatomicalModelsData.getSeats().length ||
            (pricingUnits.length === 1 && pricingUnits[0].getCost() === 0)
          ) {
            importSection.add(importButton);
          }
        });

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
      const licensedItem = this.getAnatomicalModelsData();
      osparc.store.Pricing.getInstance().fetchPricingUnits(licensedItem.getPricingPlanId())
        .then(pricingUnits => {
          if (pricingUnits.length === 1 && pricingUnits[0].getCost() === 0) {
            const availableForImporting = new qx.ui.basic.Label().set({
              font: "text-14",
              value: this.tr("Available for Importing"),
              padding: 10,
            });
            pricingUnitsLayout.add(availableForImporting);
            // hide the text if Import button is there
            this.bind("openBy", pricingLayout, "visibility", {
              converter: openBy => openBy ? "excluded" : "visible"
            });
          } else {
            pricingUnits.forEach(pricingUnit => {
              pricingUnit.set({
                classification: "LICENSE"
              });
              const pUnit = new osparc.study.PricingUnitLicense(pricingUnit).set({
                showRentButton: true,
              });
              pUnit.addListener("rentPricingUnit", () => {
                this.fireDataEvent("modelPurchaseRequested", {
                  licensedItemId: licensedItem.getLicensedItemId(),
                  pricingPlanId: licensedItem.getPricingPlanId(),
                  pricingUnitId: pricingUnit.getPricingUnitId(),
                });
              }, this);
              pricingUnitsLayout.add(pUnit);
            });
          }
        })
        .catch(err => console.error(err));
      this._add(pricingUnitsLayout);
      pricingLayout.add(pricingUnitsLayout);

      this._add(layout);
    },

    __addSeatsSection: function() {
      const licensedItem = this.getAnatomicalModelsData();
      if (licensedItem.getSeats().length === 0) {
        return;
      }
      const seatsSection = new qx.ui.container.Composite(new qx.ui.layout.VBox(5).set({
        alignX: "left",
      }));

      licensedItem.getSeats().forEach(purchase => {
        const nSeats = purchase["numOfSeats"];
        const seatsText = "seat" + (nSeats > 1 ? "s" : "");
        const entry = new qx.ui.basic.Label().set({
          value: `${nSeats} ${seatsText} available until ${osparc.utils.Utils.formatDate(purchase["expireAt"])}`,
          font: "text-14",
        });
        seatsSection.add(entry);
      });

      this._add(seatsSection);
    },
  }
});
